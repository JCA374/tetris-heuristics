"""Heuristic features."""

from tetris.features import compute_features, regime_stats
from tetris.game import TetrisGame
from tetris.pieces import I_PIECE, O_PIECE
from tetris.policy import Policy


def test_empty_board():
    f = compute_features(TetrisGame())
    assert f == {'height': 0, 'lines': 0, 'holes': 0, 'bumpiness': 0}


def test_aggregate_height():
    game = TetrisGame()
    game.place_piece(I_PIECE, 0, 0)
    assert compute_features(game)['height'] == 4
    game.place_piece(O_PIECE, 0, 5)
    assert compute_features(game)['height'] == 8


def test_holes():
    game = TetrisGame()
    game.board[19][1] = 'X'
    game.board[17][1] = 'X'  # row 18 in column 1 is now a hole
    assert compute_features(game)['holes'] == 1


def test_multiple_holes():
    game = TetrisGame()
    for col in (1, 3, 5):
        game.board[19][col] = 'X'
        game.board[17][col] = 'X'
    assert compute_features(game)['holes'] == 3


def test_deep_hole_counts_every_empty_cell_below_top():
    game = TetrisGame()
    game.board[10][0] = 'X'
    assert compute_features(game)['holes'] == 9


def test_bumpiness():
    game = TetrisGame()
    for col in range(10):
        game.board[19][col] = 'X'
    assert compute_features(game)['bumpiness'] == 0
    game.board[18][0] = 'X'
    game.board[17][0] = 'X'
    assert compute_features(game)['bumpiness'] == 2


def test_lines_feature_sees_cleared_lines():
    """Regression: the old evaluator counted full rows *after* they were cleared (always 0)."""
    game = TetrisGame()
    for col in range(9):
        game.board[19][col] = 'X'
    # Policy that only cares about lines must take the clearing move (vertical I in column 9)
    policy = Policy.single({'height': 0.0, 'lines': 1.0, 'holes': 0.0, 'bumpiness': 0.0})
    rotation, col = policy.get_best_move(game, I_PIECE)
    sim = game.simulate_move(I_PIECE, rotation, col)
    assert sim.lines_cleared == 1


def test_regime_stats():
    game = TetrisGame()
    game.board[10][0] = 'X'
    game.board[19][5] = 'X'
    s = regime_stats(game)
    assert s['max_height'] == 10
    assert s['holes'] == 9
    assert s['agg_height'] == 11
