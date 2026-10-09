"""Policies: move selection, regime switching, serialization, reproducible games, GA genome."""

import random

import pytest

from tetris.game import TetrisGame
from tetris.pieces import ALL_PIECES, I_PIECE
from tetris.play import play_game
from tetris.policy import Policy, TEMPLATES
from training.ga import gene_spec, genome_from_policy, genome_to_policy

W = {'height': -0.51, 'lines': 0.76, 'holes': -0.36, 'bumpiness': -0.18}


def regime_policy(normal=W, danger=W, repair=W, t_holes=3, t_height=12):
    return Policy(
        [{'name': 'repair', 'stat': 'holes', 'op': '>=', 'threshold': t_holes},
         {'name': 'danger', 'stat': 'max_height', 'op': '>=', 'threshold': t_height},
         {'name': 'normal'}],
        {'normal': dict(normal), 'danger': dict(danger), 'repair': dict(repair)},
    )


def test_ai_finds_valid_move_for_every_piece():
    game = TetrisGame()
    policy = Policy.single(W)
    for piece in ALL_PIECES:
        rotation, col = policy.get_best_move(game, piece)
        assert game.get_drop_row(piece, rotation, col) >= 0


def test_regime_selection():
    policy = regime_policy()
    game = TetrisGame()
    assert policy.select_regime(game) == 'normal'

    game.board[7][0] = 'X'  # column height 13, and 12 holes beneath it
    assert policy.select_regime(game) == 'repair'  # first matching rule wins

    clean_tall = TetrisGame()
    for row in range(7, 20):
        clean_tall.board[row][0] = 'X'
    assert policy.select_regime(clean_tall) == 'danger'


def test_regime_with_identical_weights_matches_single():
    """A regime model whose regimes all share one weight set must play exactly like the single model."""
    single = play_game(Policy.single(W), seed=11, max_pieces=300)
    regime = play_game(regime_policy(), seed=11, max_pieces=300)
    assert single['lines'] == regime['lines']
    assert single['pieces'] == regime['pieces']
    assert sum(regime['regime_counts'].values()) == regime['pieces']


def test_regime_weights_are_actually_used():
    lines_only = {'height': 0.0, 'lines': 1.0, 'holes': 0.0, 'bumpiness': 0.0}
    holes_only = {'height': 0.0, 'lines': 0.0, 'holes': -1.0, 'bumpiness': 0.0}
    game = TetrisGame()
    for col in range(9):
        game.board[19][col] = 'X'
    # normal regime prefers the line clear; force 'repair' (holes >= 0) which ignores lines
    p = regime_policy(normal=lines_only, danger=lines_only, repair=holes_only, t_holes=0)
    assert p.select_regime(game) == 'repair'
    p2 = regime_policy(normal=lines_only, danger=lines_only, repair=holes_only, t_holes=5)
    move = p2.get_best_move(game, I_PIECE)
    assert game.simulate_move(I_PIECE, *move).lines_cleared == 1


def test_same_seed_same_game():
    a = play_game(Policy.single(W), seed=3, max_pieces=400)
    b = play_game(Policy.single(W), seed=3, max_pieces=400)
    assert a == b


def test_lookahead_game_runs():
    r = play_game(Policy.single(W), seed=1, max_pieces=20, lookahead=True)
    assert r['pieces'] == 20


def test_save_load_roundtrip(tmp_path):
    p = regime_policy(t_holes=4, t_height=9)
    path = tmp_path / 'm.json'
    p.save(path)
    q = Policy.load(path)
    assert q.rules == p.rules and q.weights == p.weights


def test_load_legacy_best_model(tmp_path):
    path = tmp_path / 'best_model.json'
    path.write_text('{"fitness": 10, "weights": {"height": -1, "lines": 1, "holes": -1, "bumpiness": -1}}')
    p = Policy.load(path)
    assert p.is_single and p.meta['fitness'] == 10


def test_last_rule_must_be_default():
    with pytest.raises(ValueError):
        Policy([{'name': 'a', 'stat': 'holes', 'op': '>=', 'threshold': 1}], {'a': W})


def test_genome_sizes_and_roundtrip():
    four = ('height', 'lines', 'holes', 'bumpiness')
    assert len(gene_spec(TEMPLATES['single'], four)) == 4
    assert len(gene_spec(TEMPLATES['regime'], four)) == 14
    assert len(gene_spec(TEMPLATES['single'])) == 9
    spec = gene_spec(TEMPLATES['regime'])
    assert len(spec) == 29

    # A single model copied into the regime template keeps its weights in every regime
    rng = random.Random(0)
    genome = genome_from_policy(TEMPLATES['regime'], spec, Policy.single(W), rng)
    policy = genome_to_policy(TEMPLATES['regime'], genome)
    for name in ('normal', 'danger', 'repair'):
        assert policy.weights[name] == dict(W, wells=0.0, hole_depth=0.0, landing_height=0.0,
                                            eroded_cells=0.0, sz_fit=0.0)
    for rule in policy.rules[:-1]:
        low, high, _ = spec[f"{rule['name']}.threshold"]
        assert low <= rule['threshold'] <= high and isinstance(rule['threshold'], int)


def test_old_models_get_zero_weights_for_new_features():
    p = Policy.single(W)
    assert p.weights['default']['wells'] == 0.0 and p.weights['default']['hole_depth'] == 0.0


def test_unused_feature_genes_are_fixed_at_zero():
    spec = gene_spec(TEMPLATES['single'], ('height', 'holes'))
    policy = genome_to_policy(TEMPLATES['single'], {k: -1.0 for k in spec})
    assert policy.weights['default'] == {'height': -1.0, 'lines': 0.0, 'holes': -1.0, 'bumpiness': 0.0,
                                         'wells': 0.0, 'hole_depth': 0.0, 'landing_height': 0.0,
                                         'eroded_cells': 0.0, 'sz_fit': 0.0}


def test_frozen_regime_never_changes():
    from training.ga import GeneticAlgorithm
    ga = GeneticAlgorithm('repair', population_size=12, init_policy=Policy.single(W), rng_seed=1,
                          freeze=['normal'])
    population = ga.initial_population()
    for _ in range(5):
        population = ga.next_generation(population, [ga.rng.random() for _ in population])
    for genome in population:
        for f in ('height', 'lines', 'holes', 'bumpiness'):
            assert genome[f'normal.{f}'] == W[f]
    assert len({g['repair.holes'] for g in population}) > 1   # repair still evolves
