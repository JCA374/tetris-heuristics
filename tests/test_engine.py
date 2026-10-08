"""Game engine: placement, line clearing, scoring, simulation, move generation."""

import random

from tetris.game import TetrisGame
from tetris.pieces import (ALL_PIECES, I_PIECE, O_PIECE, T_PIECE, make_generator)


def test_game_simulation_does_not_modify_original():
    game = TetrisGame()
    game.place_piece(I_PIECE, 0, 0)
    board_before = [row[:] for row in game.board]

    sim = game.simulate_move(O_PIECE, 0, 5)

    assert game.pieces_placed == 1
    assert game.board == board_before
    assert sim.pieces_placed == 2
    assert sim.board != board_before


def test_line_clearing():
    game = TetrisGame()
    for col in range(10):
        game.board[19][col] = 'X'
    assert game.clear_lines() == 1
    assert all(cell == 0 for cell in game.board[19])


def test_multiple_line_clears():
    game = TetrisGame()
    for row in range(16, 20):
        for col in range(10):
            game.board[row][col] = 'X'
    game.board[15][3] = 'X'  # survives and drops to the bottom

    assert game.clear_lines() == 4
    assert game.board[19][3] == 'X'
    assert sum(cell != 0 for row in game.board for cell in row) == 1


def test_scoring():
    game = TetrisGame()
    for col in range(6):
        game.board[19][col] = 'X'
    game.place_piece(I_PIECE, 0, 6)
    assert game.score == 40
    assert game.lines_cleared == 1


def test_game_over_when_board_full():
    game = TetrisGame()
    for row in range(20):
        for col in range(10):
            game.board[row][col] = 'X'
    assert game.place_piece(I_PIECE, 0, 0) is False
    assert game.game_over is True


def test_move_generation_on_empty_board():
    game = TetrisGame()
    expected = {'I': 7 + 10, 'O': 9, 'T': 8 + 9 + 8 + 9, 'S': 8 + 9, 'Z': 8 + 9,
                'J': 8 + 9 + 8 + 9, 'L': 8 + 9 + 8 + 9}
    for piece in ALL_PIECES:
        assert len(game.get_all_possible_moves(piece)) == expected[piece.name], piece.name


def test_moves_stay_in_bounds():
    game = TetrisGame()
    assert game.place_piece(I_PIECE, 0, 0)
    game.reset()
    assert game.place_piece(O_PIECE, 0, 8)
    for piece in ALL_PIECES:
        for rotation, col in game.get_all_possible_moves(piece):
            for r, c in piece.get_rotation(rotation):
                assert 0 <= c + col < game.width


def test_fast_drop_matches_scan_on_random_boards():
    """get_drop_row (column-top shortcut) must agree with the reference row scan."""
    rng = random.Random(42)
    for _ in range(300):
        game = TetrisGame()
        fill = rng.random()
        for row in range(rng.randint(0, 20), 20):
            for col in range(10):
                if rng.random() < fill:
                    game.board[row][col] = 'X'
        for piece in ALL_PIECES:
            for rotation in range(piece.num_rotations()):
                for col in range(-1, 11):
                    expected = game._scan_drop_row(piece, rotation, col)
                    assert game.get_drop_row(piece, rotation, col) == expected


def test_seeded_generators_are_reproducible():
    for randomizer in ('random', 'bag'):
        a = make_generator(randomizer, seed=5)
        b = make_generator(randomizer, seed=5)
        assert [a.get_next_piece().name for _ in range(100)] == [b.get_next_piece().name for _ in range(100)]


def test_seven_bag_contains_each_piece_once():
    gen = make_generator('bag', seed=1)
    for _ in range(5):
        assert sorted(gen.get_next_piece().name for _ in range(7)) == sorted('IOTSZJL')


def test_t_piece_lands_on_floor():
    game = TetrisGame()
    assert game.place_piece(T_PIECE, 0, 0)
    assert game.get_column_heights()[:3] == [1, 2, 1]
