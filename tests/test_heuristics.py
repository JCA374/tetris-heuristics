"""
Unit Tests for Tetris AI Heuristics

Tests the heuristic evaluation functions to ensure they work correctly.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tetris_game import TetrisGame
from tetris_ai import TetrisAI
from tetris_pieces import I_PIECE, O_PIECE, T_PIECE, J_PIECE


def test_empty_board():
    """Test heuristics on an empty board."""
    print("Testing empty board...")
    game = TetrisGame()
    ai = TetrisAI()

    assert ai.calculate_aggregate_height(game) == 0, "Empty board should have 0 height"
    assert ai.calculate_holes(game) == 0, "Empty board should have 0 holes"
    assert ai.calculate_bumpiness(game) == 0, "Empty board should have 0 bumpiness"
    assert ai.calculate_complete_lines(game) == 0, "Empty board should have 0 complete lines"

    print("  ✓ All empty board tests passed")


def test_aggregate_height():
    """Test aggregate height calculation."""
    print("Testing aggregate height...")
    game = TetrisGame()
    ai = TetrisAI()

    # Place piece at bottom
    game.place_piece(I_PIECE, 0, 0)  # Horizontal I at bottom
    height = ai.calculate_aggregate_height(game)
    assert height == 4, f"Expected height 4, got {height}"

    # Place another piece
    game.place_piece(O_PIECE, 0, 5)  # O piece
    height = ai.calculate_aggregate_height(game)
    assert height >= 4, f"Height should increase or stay same, got {height}"

    print("  ✓ Aggregate height tests passed")


def test_holes():
    """Test hole detection."""
    print("Testing hole detection...")
    game = TetrisGame()
    ai = TetrisAI()

    # Create a hole manually (hole = empty cell with filled cell above in same column)
    game.board[19][1] = 'X'  # Bottom of column 1
    game.board[18][1] = 0    # Hole in column 1
    game.board[17][1] = 'X'  # Block above the hole in column 1

    holes = ai.calculate_holes(game)
    assert holes >= 1, f"Should detect at least 1 hole, got {holes}"

    print("  ✓ Hole detection tests passed")


def test_bumpiness():
    """Test bumpiness calculation."""
    print("Testing bumpiness...")
    game = TetrisGame()
    ai = TetrisAI()

    # Flat surface - should have 0 bumpiness
    for col in range(10):
        game.board[19][col] = 'X'

    bumpiness = ai.calculate_bumpiness(game)
    assert bumpiness == 0, f"Flat surface should have 0 bumpiness, got {bumpiness}"

    # Create uneven surface
    game.board[18][0] = 'X'
    game.board[17][0] = 'X'

    bumpiness = ai.calculate_bumpiness(game)
    assert bumpiness > 0, f"Uneven surface should have bumpiness > 0, got {bumpiness}"

    print("  ✓ Bumpiness tests passed")


def test_complete_lines():
    """Test complete line detection."""
    print("Testing complete line detection...")
    game = TetrisGame()
    ai = TetrisAI()

    # Fill one row completely
    for col in range(10):
        game.board[19][col] = 'X'

    lines = ai.calculate_complete_lines(game)
    assert lines == 1, f"Should detect 1 complete line, got {lines}"

    # Fill another row
    for col in range(10):
        game.board[18][col] = 'X'

    lines = ai.calculate_complete_lines(game)
    assert lines == 2, f"Should detect 2 complete lines, got {lines}"

    print("  ✓ Complete line detection tests passed")


def test_ai_move_selection():
    """Test that AI can select valid moves."""
    print("Testing AI move selection...")
    game = TetrisGame()
    ai = TetrisAI()

    # Get best move for I piece
    move = ai.get_best_move(game, I_PIECE)
    assert move is not None, "AI should find a valid move"
    rotation, col = move
    assert 0 <= rotation < I_PIECE.num_rotations(), "Rotation should be valid"
    assert 0 <= col < game.width, "Column should be valid"

    # Verify move is actually valid
    assert game.get_drop_row(I_PIECE, rotation, col) >= 0, "Selected move should be valid"

    print("  ✓ AI move selection tests passed")


def test_game_simulation():
    """Test game simulation doesn't affect original."""
    print("Testing game simulation...")
    game = TetrisGame()

    # Place a piece
    game.place_piece(I_PIECE, 0, 0)
    original_pieces = game.pieces_placed

    # Simulate another move
    sim_game = game.simulate_move(O_PIECE, 0, 5)

    assert game.pieces_placed == original_pieces, "Original game should be unchanged"
    assert sim_game.pieces_placed == original_pieces + 1, "Simulated game should have one more piece"

    print("  ✓ Game simulation tests passed")


def test_line_clearing():
    """Test that line clearing works correctly."""
    print("Testing line clearing...")
    game = TetrisGame()

    # Fill bottom row except one cell
    for col in range(9):
        game.board[19][col] = 'X'

    # Place piece that completes the line
    game.board[19][9] = 'X'

    lines = game.clear_lines()
    assert lines == 1, f"Should clear 1 line, cleared {lines}"
    assert all(cell == 0 for cell in game.board[19]), "Bottom row should be empty after clearing"

    print("  ✓ Line clearing tests passed")


def run_all_tests():
    """Run all unit tests."""
    print("\n" + "=" * 50)
    print("Running Tetris AI Unit Tests")
    print("=" * 50 + "\n")

    tests = [
        test_empty_board,
        test_aggregate_height,
        test_holes,
        test_bumpiness,
        test_complete_lines,
        test_ai_move_selection,
        test_game_simulation,
        test_line_clearing
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 50)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
