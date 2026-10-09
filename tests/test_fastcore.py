"""The C core (tetris/fastcore.c) must play exactly like the Python engine."""

import pytest

from tetris import fastcore
from tetris.play import play_game
from tetris.policy import Policy

pytestmark = pytest.mark.skipif(not fastcore.available(), reason='no C compiler')

SIX = {'height': -0.18, 'lines': 0.0, 'holes': -7.7, 'bumpiness': -0.97, 'wells': -0.96, 'hole_depth': -0.1}
FOUR = {'height': -0.39, 'lines': 1.09, 'holes': -7.8, 'bumpiness': -2.0}


def regime(t_holes=5, t_height=12):
    return Policy(
        [{'name': 'repair', 'stat': 'holes', 'op': '>=', 'threshold': t_holes},
         {'name': 'danger', 'stat': 'max_height', 'op': '>=', 'threshold': t_height},
         {'name': 'normal'}],
        {'repair': dict(SIX, holes=-9.0), 'danger': dict(FOUR, height=-1.7), 'normal': SIX},
    )


@pytest.mark.parametrize('policy', [Policy.single(FOUR), Policy.single(SIX), regime(), regime(2, 6)],
                         ids=['single4', 'single6', 'regime', 'regime_low_thresholds'])
@pytest.mark.parametrize('seed,randomizer,lookahead,height,cap', [
    (1, 'random', False, 20, 2000),
    (2, 'bag', False, 20, 2000),
    (3, 'random', True, 20, 120),
    (4, 'random', False, 10, 2000),
    (5, 'random', False, 13, 2000),
])
def test_c_matches_python(policy, seed, randomizer, lookahead, height, cap):
    kwargs = dict(seed=seed, max_pieces=cap, lookahead=lookahead, randomizer=randomizer, height=height)
    assert play_game(policy, engine='c', **kwargs) == play_game(policy, engine='python', **kwargs)


def test_c_handles_chunk_boundaries_and_caps():
    # longer than one piece chunk, cap not a multiple of the chunk size
    p = Policy.single(SIX)
    cap = fastcore.CHUNK * 2 + 37
    a = play_game(p, seed=9, max_pieces=cap, engine='c')
    b = play_game(p, seed=9, max_pieces=cap, engine='python')
    assert a == b and a['pieces'] == cap


def test_record_game_matches_python_recorder():
    """The hybrid recorder (C core + Python replay of the end) logs the same game as pure Python."""
    from tetris.play import GameRecorder, record_game
    letters = str.maketrans('IOTSZJL', 'XXXXXXX')
    for policy in (Policy.single(FOUR), regime()):
        a = play_game(policy, seed=5, max_pieces=5000, recorder=GameRecorder(50, 100), engine='python')
        b = record_game(policy, seed=5, max_pieces=5000, keep_last=50, snapshot_every=100)
        assert (a['lines'], a['pieces'], a['capped']) == (b['lines'], b['pieces'], b['capped'])
        ra, rb = a['record'], b['record']
        assert [s['n'] for s in ra['snapshots']] == [s['n'] for s in rb['snapshots']]
        if not a['capped']:
            assert ra['killer_piece'] == rb['killer_piece']
            assert ra['pieces_since_seen'] == rb['pieces_since_seen']
            assert [(r['n'], r['piece'], r['rotation'], r['col'], r['regime'], r['cleared'],
                     [row.translate(letters) for row in r['board']]) for r in ra['recent']] == \
                   [(r['n'], r['piece'], r['rotation'], r['col'], r['regime'], r['cleared'],
                     [row.translate(letters) for row in r['board']]) for r in rb['recent']]


def test_play_from_recovers_and_matches_python():
    """A crisis episode from a given board plays the same moves as the Python engine."""
    from tetris.game import TetrisGame
    from tetris.play import PieceStream
    board = ['.' * 10] * 12 + ['XXXXXXXXX.'] * 2 + ['X.XXXXXXXX'] * 6
    policy = Policy.single(SIX)
    r = fastcore.play_from(policy, board, seed=9, max_pieces=1000)

    game = TetrisGame()
    game.board = [[('X' if ch != '.' else 0) for ch in row] for row in board]
    stream = PieceStream('random', 9)
    from tetris.features import regime_stats
    recovered = False
    while not game.game_over and game.pieces_placed < 1000:
        move = policy.get_best_move(game, stream.current)
        if move is None:
            break
        game.place_piece(stream.current, *move)
        stream.advance()
        s = regime_stats(game)
        if s['holes'] == 0 and s['max_height'] <= 8:
            recovered = True
            break
    assert (r['recovered'], r['pieces'], r['lines']) == (recovered, game.pieces_placed, game.lines_cleared)
    assert fastcore.play_from(policy, ['.' * 10] * 20, seed=1)['pieces'] == 1   # already healthy


def test_crisis_ga_smoke():
    from training.ga import GeneticAlgorithm
    board = fastcore.board_rows(['.' * 10] * 14 + ['X.XXXXXXXX'] * 6)
    crisis = {'train': [{'rows': board}] * 5, 'validation': [{'rows': board}] * 3}
    ga = GeneticAlgorithm('repair', population_size=6, games=4, max_pieces=200, init_policy=Policy.single(SIX),
                          rng_seed=0, freeze=['normal'], crisis=crisis, candidates=2)
    results = ga.play_many(ga.initial_population(), ga.train_episodes(1))
    assert all(r['fitness'] in (0.0, 1.0) for res in results for r in res)
    assert len(ga.validation_episodes()) == 3
