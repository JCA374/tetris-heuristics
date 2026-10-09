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
