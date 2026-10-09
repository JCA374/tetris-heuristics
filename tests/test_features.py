"""Heuristic features."""

from tetris.features import compute_features, regime_stats
from tetris.game import TetrisGame
from tetris.pieces import I_PIECE, O_PIECE
from tetris.policy import Policy


def test_empty_board():
    f = compute_features(TetrisGame())
    assert f == {'height': 0, 'lines': 0, 'holes': 0, 'bumpiness': 0, 'wells': 0, 'hole_depth': 0,
                 'landing_height': 0, 'eroded_cells': 0, 'sz_fit': 0}


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


def test_wells():
    game = TetrisGame()
    for col in range(10):
        if col != 4:
            for row in range(17, 20):
                game.board[row][col] = 'X'
    # column 4 is a 3-deep well: 1 + 2 + 3 = 6; flat edges against the walls are not wells
    assert compute_features(game)['wells'] == 6


def test_wall_well():
    game = TetrisGame()
    for col in range(1, 10):
        game.board[19][col] = 'X'
        game.board[18][col] = 'X'
    # column 0 sits 2 below its neighbour and the wall counts as infinitely high: 1 + 2 = 3
    assert compute_features(game)['wells'] == 3


def test_hole_depth():
    game = TetrisGame()
    game.board[19][0] = 'X'
    game.board[16][0] = 'X'
    game.board[15][0] = 'X'
    # rows 17 and 18 are holes, each under 2 filled cells
    f = compute_features(game)
    assert f['holes'] == 2
    assert f['hole_depth'] == 4


def test_hole_depth_counts_only_cells_above():
    game = TetrisGame()
    game.board[19][0] = 'X'   # filled below the hole doesn't count
    game.board[17][0] = 'X'   # one cell above the hole at row 18
    assert compute_features(game)['hole_depth'] == 1


def test_landing_height_and_eroded_cells():
    game = TetrisGame()
    for col in range(9):
        game.board[19][col] = 'X'
    game.place_piece(I_PIECE, 1, 9)          # vertical I in the last column: completes row 19
    # the I covered rows 16-19 (bottom on the floor, 4 high): landing = 0 + 3/2
    assert game.last_landing == 1.5
    assert game.last_eroded == 1 * 1         # one row completed, one of the I's cells in it
    game.place_piece(O_PIECE, 0, 0)          # O on the floor of an emptied board: no clear
    assert game.last_landing == 0.5 and game.last_eroded == 0


def test_sz_fit():
    from tetris.features import sz_fit
    assert sz_fit([0] * 10) == 0              # flat: S and Z both leave a hole
    assert sz_fit([1, 0] + [0] * 8) == 2      # step down then flat: S upright and Z flat both fit
    assert sz_fit([0, 1] + [1] * 8) == 1      # step up to the right: Z fits (vertical)
    assert sz_fit([1, 0, 1] + [1] * 7) == 2


def test_new_feature_weights_change_moves_only_when_nonzero():
    """Zero weights for the new features must leave scores bit-identical (old models unchanged)."""
    from tetris.features import evaluate
    game = TetrisGame()
    game.place_piece(O_PIECE, 0, 3)
    w = {'height': -0.5, 'lines': 0.7, 'holes': -3.0, 'bumpiness': -0.2, 'wells': -0.4, 'hole_depth': -0.1,
         'landing_height': 0.0, 'eroded_cells': 0.0, 'sz_fit': 0.0}
    base = evaluate(game, 0, w)
    assert evaluate(game, 0, dict(w, landing_height=-1.0)) == base - game.last_landing
