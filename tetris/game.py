"""
Tetris Game Engine

Core game logic including board management, piece placement,
collision detection, and line clearing.

Board representation: list of rows (row 0 = top), each a list of cells where
0 = empty and anything else (the piece's color/name) = filled.
"""


class TetrisGame:
    """Manages the Tetris game state and rules."""

    LINE_SCORES = {0: 0, 1: 40, 2: 100, 3: 300, 4: 1200}

    def __init__(self, width=10, height=20):
        """
        Initialize a new Tetris game.

        Args:
            width: Board width (default 10)
            height: Board height (default 20)
        """
        self.width = width
        self.height = height
        self.reset()

    def reset(self):
        """Reset the game to initial state."""
        self.board = [[0] * self.width for _ in range(self.height)]
        self.score = 0
        self.lines_cleared = 0
        self.pieces_placed = 0
        self.game_over = False

    def copy(self):
        """Create an independent copy of the game state."""
        new_game = TetrisGame.__new__(TetrisGame)
        new_game.width = self.width
        new_game.height = self.height
        new_game.board = [row[:] for row in self.board]
        new_game.score = self.score
        new_game.lines_cleared = self.lines_cleared
        new_game.pieces_placed = self.pieces_placed
        new_game.game_over = self.game_over
        return new_game

    def column_tops(self):
        """Row index of the topmost filled cell per column (self.height if empty)."""
        board = self.board
        tops = []
        for col in range(self.width):
            row = 0
            while row < self.height and board[row][col] == 0:
                row += 1
            tops.append(row)
        return tops

    def get_column_heights(self):
        """Height of each column (distance from bottom to highest filled cell)."""
        return [self.height - top for top in self.column_tops()]

    def is_valid_position(self, piece, rotation, col_offset, row_offset=0):
        """Check if a piece can be placed at the given position."""
        for row, col in piece.get_rotation(rotation):
            new_row = row + row_offset
            new_col = col + col_offset
            if new_row < 0 or new_row >= self.height:
                return False
            if new_col < 0 or new_col >= self.width:
                return False
            if self.board[new_row][new_col] != 0:
                return False
        return True

    def get_drop_row(self, piece, rotation, col_offset, tops=None):
        """
        Find the row offset where a piece lands when hard-dropped from the top.

        Args:
            piece: TetrisPiece object
            rotation: Rotation index
            col_offset: Column offset
            tops: Optional precomputed column_tops() (speeds up move generation)

        Returns:
            Row offset where piece lands, or -1 if it cannot enter the board
        """
        width, profile = piece.profiles[rotation % len(piece.profiles)]
        if col_offset < 0 or col_offset + width > self.width:
            return -1
        if tops is None:
            tops = self.column_tops()

        drop = self.height
        for dc, lowest in profile:
            top = tops[col_offset + dc]
            if top <= lowest:
                # Stack reaches into the piece's spawn area: fall back to scanning
                return self._scan_drop_row(piece, rotation, col_offset)
            drop = min(drop, top - lowest - 1)
        return drop

    def _scan_drop_row(self, piece, rotation, col_offset):
        """Reference drop: move down from row 0 until collision."""
        row = 0
        while row < self.height:
            if not self.is_valid_position(piece, rotation, col_offset, row):
                return row - 1
            row += 1
        return self.height - 1

    def place_piece(self, piece, rotation, col_offset, tops=None):
        """
        Place a piece on the board at the specified position.

        Returns:
            True if piece placed successfully, False if invalid (sets game_over)
        """
        row_offset = self.get_drop_row(piece, rotation, col_offset, tops)

        if row_offset < 0:
            self.game_over = True
            return False

        board = self.board
        for row, col in piece.get_rotation(rotation):
            board[row + row_offset][col + col_offset] = piece.color

        self.pieces_placed += 1

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
        remaining = [row for row in self.board if 0 in row]
        cleared = self.height - len(remaining)
        if cleared:
            self.board = [[0] * self.width for _ in range(cleared)] + remaining
        return cleared

    def calculate_score(self, lines_cleared):
        """Standard Tetris scoring: 1 line = 40, 2 = 100, 3 = 300, 4 = 1200."""
        return self.LINE_SCORES.get(lines_cleared, lines_cleared * 400)

    def simulate_move(self, piece, rotation, col_offset, tops=None):
        """
        Simulate placing a piece without modifying the current game.

        Returns:
            Copy of game state after the move, or None if invalid
        """
        sim_game = self.copy()
        if sim_game.place_piece(piece, rotation, col_offset, tops):
            return sim_game
        return None

    def get_all_possible_moves(self, piece, tops=None):
        """Get all valid (rotation, column) pairs for a piece."""
        if tops is None:
            tops = self.column_tops()
        moves = []
        for rotation in range(piece.num_rotations()):
            for col in range(self.width):
                if self.get_drop_row(piece, rotation, col, tops) >= 0:
                    moves.append((rotation, col))
        return moves

    def display(self):
        """Return a string representation of the board."""
        lines = ['┌' + '─' * self.width + '┐']
        for row in self.board:
            lines.append('│' + ''.join('.' if cell == 0 else '█' for cell in row) + '│')
        lines.append('└' + '─' * self.width + '┘')
        lines.append(f'Lines: {self.lines_cleared} | Pieces: {self.pieces_placed} | Score: {self.score}')
        return '\n'.join(lines)

    def __str__(self):
        return self.display()
