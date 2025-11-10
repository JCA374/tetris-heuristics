"""
Tetris Game Engine

Core game logic including board management, piece placement,
collision detection, and line clearing.
"""

import copy
from tetris_pieces import get_random_piece


class TetrisGame:
    """Manages the Tetris game state and rules."""

    def __init__(self, width=10, height=20):
        """
        Initialize a new Tetris game.

        Args:
            width: Board width (default 10)
            height: Board height (default 20)
        """
        self.width = width
        self.height = height
        self.board = [[0 for _ in range(width)] for _ in range(height)]
        self.score = 0
        self.lines_cleared = 0
        self.pieces_placed = 0
        self.game_over = False
        self.current_piece = None

    def reset(self):
        """Reset the game to initial state."""
        self.board = [[0 for _ in range(self.width)] for _ in range(self.height)]
        self.score = 0
        self.lines_cleared = 0
        self.pieces_placed = 0
        self.game_over = False
        self.current_piece = None

    def copy(self):
        """Create a deep copy of the game state."""
        new_game = TetrisGame(self.width, self.height)
        new_game.board = copy.deepcopy(self.board)
        new_game.score = self.score
        new_game.lines_cleared = self.lines_cleared
        new_game.pieces_placed = self.pieces_placed
        new_game.game_over = self.game_over
        new_game.current_piece = self.current_piece
        return new_game

    def is_valid_position(self, piece, rotation, col_offset, row_offset=0):
        """
        Check if a piece can be placed at the given position.

        Args:
            piece: TetrisPiece object
            rotation: Rotation index
            col_offset: Column offset for placement
            row_offset: Row offset for placement (default 0)

        Returns:
            True if position is valid, False otherwise
        """
        coords = piece.get_rotation(rotation)

        for row, col in coords:
            new_row = row + row_offset
            new_col = col + col_offset

            # Check boundaries
            if new_row < 0 or new_row >= self.height:
                return False
            if new_col < 0 or new_col >= self.width:
                return False

            # Check collision with existing pieces
            if self.board[new_row][new_col] != 0:
                return False

        return True

    def get_drop_row(self, piece, rotation, col_offset):
        """
        Find the row where a piece will land when dropped.

        Args:
            piece: TetrisPiece object
            rotation: Rotation index
            col_offset: Column offset

        Returns:
            Row index where piece lands, or -1 if invalid placement
        """
        # Start from top and move down until collision
        row = 0
        while row < self.height:
            if not self.is_valid_position(piece, rotation, col_offset, row):
                return row - 1
            row += 1
        return self.height - 1

    def place_piece(self, piece, rotation, col_offset):
        """
        Place a piece on the board at the specified position.

        Args:
            piece: TetrisPiece object
            rotation: Rotation index
            col_offset: Column offset

        Returns:
            True if piece placed successfully, False if invalid
        """
        # Find where piece will land
        row_offset = self.get_drop_row(piece, rotation, col_offset)

        if row_offset < 0:
            # Cannot place piece - game over
            self.game_over = True
            return False

        # Place the piece
        coords = piece.get_rotation(rotation)
        for row, col in coords:
            new_row = row + row_offset
            new_col = col + col_offset
            self.board[new_row][new_col] = piece.color

        self.pieces_placed += 1

        # Clear any completed lines
        lines = self.clear_lines()
        self.lines_cleared += lines
        self.score += self.calculate_score(lines)

        return True

    def clear_lines(self):
        """
        Clear all completed lines from the board.

        Returns:
            Number of lines cleared
        """
        lines_to_clear = []

        # Find completed lines
        for row in range(self.height):
            if all(cell != 0 for cell in self.board[row]):
                lines_to_clear.append(row)

        # Remove completed lines and add empty ones at top
        for row in lines_to_clear:
            del self.board[row]
            self.board.insert(0, [0 for _ in range(self.width)])

        return len(lines_to_clear)

    def calculate_score(self, lines_cleared):
        """
        Calculate score based on lines cleared.

        Args:
            lines_cleared: Number of lines cleared

        Returns:
            Score to add
        """
        # Standard Tetris scoring: 1 line = 40, 2 = 100, 3 = 300, 4 = 1200
        scores = {0: 0, 1: 40, 2: 100, 3: 300, 4: 1200}
        return scores.get(lines_cleared, lines_cleared * 400)

    def get_column_heights(self):
        """
        Get the height of each column (distance from bottom to highest filled cell).

        Returns:
            List of column heights
        """
        heights = []
        for col in range(self.width):
            height = 0
            for row in range(self.height):
                if self.board[row][col] != 0:
                    height = self.height - row
                    break
            heights.append(height)
        return heights

    def simulate_move(self, piece, rotation, col_offset):
        """
        Simulate placing a piece without modifying the current game.

        Args:
            piece: TetrisPiece object
            rotation: Rotation index
            col_offset: Column offset

        Returns:
            Copy of game state after the move, or None if invalid
        """
        sim_game = self.copy()
        if sim_game.place_piece(piece, rotation, col_offset):
            return sim_game
        return None

    def get_all_possible_moves(self, piece):
        """
        Get all valid (rotation, column) pairs for a piece.

        Args:
            piece: TetrisPiece object

        Returns:
            List of (rotation, column) tuples
        """
        moves = []

        for rotation in range(piece.num_rotations()):
            for col in range(self.width):
                # Check if this placement is valid
                if self.get_drop_row(piece, rotation, col) >= 0:
                    moves.append((rotation, col))

        return moves

    def display(self):
        """Return a string representation of the board."""
        lines = ['┌' + '─' * self.width + '┐']

        for row in self.board:
            line = '│'
            for cell in row:
                if cell == 0:
                    line += '.'
                else:
                    line += '█'
            line += '│'
            lines.append(line)

        lines.append('└' + '─' * self.width + '┘')
        lines.append(f'Lines: {self.lines_cleared} | Pieces: {self.pieces_placed} | Score: {self.score}')

        return '\n'.join(lines)

    def __str__(self):
        """String representation of the game."""
        return self.display()


if __name__ == '__main__':
    # Test the game engine
    print("Tetris Game Engine Test")
    print("=" * 40)

    game = TetrisGame()
    print("Empty board:")
    print(game.display())

    # Test placing some pieces
    from tetris_pieces import I_PIECE, O_PIECE, T_PIECE

    print("\n\nPlacing I piece at column 0, rotation 0:")
    game.place_piece(I_PIECE, 0, 0)
    print(game.display())

    print("\n\nPlacing O piece at column 5:")
    game.place_piece(O_PIECE, 0, 5)
    print(game.display())

    print("\n\nPlacing T piece at column 3:")
    game.place_piece(T_PIECE, 0, 3)
    print(game.display())

    # Test line clearing
    print("\n\nFilling bottom row:")
    for col in range(10):
        game.board[19][col] = '#'
    print(game.display())

    print("\n\nAfter placing piece (should clear line):")
    game.place_piece(I_PIECE, 1, 0)
    print(game.display())

    # Test possible moves
    print(f"\n\nPossible moves for I piece: {len(game.get_all_possible_moves(I_PIECE))}")
    print(f"Possible moves for O piece: {len(game.get_all_possible_moves(O_PIECE))}")
    print(f"Possible moves for T piece: {len(game.get_all_possible_moves(T_PIECE))}")

    print("\n✓ Game engine tests completed")
