"""
Tetris AI using Heuristic Evaluation

Implements a simple but effective Tetris AI using four key heuristics:
- Aggregate Height (minimize)
- Complete Lines (maximize)
- Holes (minimize)
- Bumpiness (minimize)
"""


class TetrisAI:
    """AI player for Tetris using heuristic evaluation."""

    # Default weights updated to defensive strategy (empirically best performer: 1,012 lines avg)
    # Previous GA-optimized weights (Lee 2013): height=-0.510066, lines=0.760666, holes=-0.35663, bumpiness=-0.184483
    DEFAULT_WEIGHTS = {
        'height': -0.600000,
        'lines': 0.500000,
        'holes': -0.800000,  # Doubled penalty - key to defensive strategy
        'bumpiness': -0.300000
    }

    def __init__(self, weights=None):
        """
        Initialize the AI with optional custom weights.

        Args:
            weights: Dict of weights for heuristics, or None for defaults
        """
        self.weights = weights if weights else self.DEFAULT_WEIGHTS.copy()
        self.moves_evaluated = 0

    def calculate_aggregate_height(self, game):
        """
        Calculate the sum of all column heights.

        Lower is better - indicates more room to play.

        Args:
            game: TetrisGame object

        Returns:
            Sum of column heights
        """
        return sum(game.get_column_heights())

    def calculate_complete_lines(self, game):
        """
        Count the number of complete lines on the board.

        Higher is better - primary game objective.

        Args:
            game: TetrisGame object

        Returns:
            Number of complete lines
        """
        complete = 0
        for row in game.board:
            if all(cell != 0 for cell in row):
                complete += 1
        return complete

    def calculate_holes(self, game):
        """
        Count holes (empty cells with filled cells above them).

        Lower is better - holes are difficult to clear.

        A hole is defined as an empty cell that has at least one
        filled cell above it in the same column.

        Args:
            game: TetrisGame object

        Returns:
            Number of holes
        """
        holes = 0

        for col in range(game.width):
            found_block = False
            for row in range(game.height):
                if game.board[row][col] != 0:
                    found_block = True
                elif found_block and game.board[row][col] == 0:
                    holes += 1

        return holes

    def calculate_bumpiness(self, game):
        """
        Calculate bumpiness (sum of height differences between adjacent columns).

        Lower is better - a flat surface is ideal for piece placement.

        Bumpiness is the sum of absolute differences in height
        between all pairs of adjacent columns.

        Args:
            game: TetrisGame object

        Returns:
            Total bumpiness
        """
        heights = game.get_column_heights()
        bumpiness = 0

        for i in range(len(heights) - 1):
            bumpiness += abs(heights[i] - heights[i + 1])

        return bumpiness

    def evaluate_board(self, game):
        """
        Evaluate a board state using weighted heuristics.

        Args:
            game: TetrisGame object

        Returns:
            Score (higher is better)
        """
        if game.game_over:
            return float('-inf')

        height = self.calculate_aggregate_height(game)
        lines = self.calculate_complete_lines(game)
        holes = self.calculate_holes(game)
        bumpiness = self.calculate_bumpiness(game)

        score = (
            self.weights['height'] * height +
            self.weights['lines'] * lines +
            self.weights['holes'] * holes +
            self.weights['bumpiness'] * bumpiness
        )

        return score

    def _evaluate_with_lookahead(self, game, next_piece):
        """
        Evaluate a board state by looking ahead to the next piece.

        This evaluates all possible placements of the next piece and
        returns the best score achievable. This is the core of the
        one-piece lookahead strategy.

        Args:
            game: TetrisGame object (state after current piece)
            next_piece: TetrisPiece to look ahead with

        Returns:
            Best score achievable with the next piece
        """
        if game.game_over:
            return float('-inf')

        # Get all possible moves for next piece
        next_moves = game.get_all_possible_moves(next_piece)

        if not next_moves:
            # No valid moves for next piece = game over
            return float('-inf')

        best_next_score = float('-inf')

        # Try all possible placements of next piece
        for next_rotation, next_col in next_moves:
            # Simulate placing the next piece
            next_game = game.simulate_move(next_piece, next_rotation, next_col)

            if next_game is None:
                continue

            # Evaluate the board after next piece
            score = self.evaluate_board(next_game)
            best_next_score = max(best_next_score, score)

            self.moves_evaluated += 1

        return best_next_score

    def get_best_move(self, game, piece, next_piece=None, verbose=False):
        """
        Find the best move for a given piece.

        Evaluates all possible placements and returns the one
        with the highest score. If next_piece is provided, uses
        one-piece lookahead for evaluation.

        Args:
            game: TetrisGame object
            piece: TetrisPiece to place
            next_piece: Optional next piece for lookahead (None = no lookahead)
            verbose: If True, print evaluation details

        Returns:
            Tuple of (rotation, column) for best move, or None if no valid moves
        """
        possible_moves = game.get_all_possible_moves(piece)

        if not possible_moves:
            return None

        best_score = float('-inf')
        best_move = None
        move_scores = []

        for rotation, col in possible_moves:
            # Simulate the move
            sim_game = game.simulate_move(piece, rotation, col)

            if sim_game is None:
                continue

            # Evaluate the resulting board
            if next_piece is not None:
                # Use one-piece lookahead
                score = self._evaluate_with_lookahead(sim_game, next_piece)
            else:
                # No lookahead - evaluate current state only
                score = self.evaluate_board(sim_game)
                self.moves_evaluated += 1

            move_scores.append((rotation, col, score))

            if score > best_score:
                best_score = score
                best_move = (rotation, col)

        if verbose and move_scores:
            lookahead_str = f" (with lookahead: {next_piece.name})" if next_piece else ""
            print(f"\nEvaluated {len(move_scores)} possible moves for piece {piece.name}{lookahead_str}:")
            # Show top 5 moves
            move_scores.sort(key=lambda x: x[2], reverse=True)
            for i, (rot, col, score) in enumerate(move_scores[:5]):
                marker = "★" if (rot, col) == best_move else " "
                print(f"  {marker} Rotation {rot}, Column {col}: {score:.2f}")

        return best_move

    def play_game(self, game, max_pieces=None, verbose=False, show_board=False, use_lookahead=False):
        """
        Play a complete game using the AI.

        Args:
            game: TetrisGame object
            max_pieces: Maximum pieces to place (None for unlimited)
            verbose: If True, print move details
            show_board: If True, display board after each move
            use_lookahead: If True, use one-piece lookahead with 7-bag generator

        Returns:
            Final game state
        """
        if use_lookahead:
            # Use 7-bag generator for fair piece distribution
            from tetris_pieces import SevenBagGenerator
            piece_generator = SevenBagGenerator()

            # Pre-generate first two pieces for lookahead
            current_piece = piece_generator.get_next_piece()
            next_piece = piece_generator.get_next_piece()
        else:
            # Use pure random pieces, no lookahead
            from tetris_pieces import get_random_piece
            current_piece = get_random_piece()
            next_piece = None

        pieces_placed = 0
        self.moves_evaluated = 0

        while not game.game_over:
            if max_pieces and pieces_placed >= max_pieces:
                break

            # Find best move (with or without lookahead)
            move = self.get_best_move(game, current_piece, next_piece=next_piece, verbose=verbose)

            if move is None:
                game.game_over = True
                break

            rotation, col = move

            # Make the move
            game.place_piece(current_piece, rotation, col)
            pieces_placed += 1

            if show_board:
                next_str = f" (next: {next_piece.name})" if next_piece else ""
                print(f"\n--- Piece {pieces_placed} ({current_piece.name}){next_str} ---")
                print(game.display())

            if verbose and pieces_placed % 100 == 0:
                print(f"Progress: {pieces_placed} pieces, {game.lines_cleared} lines")

            # Advance to next piece
            if use_lookahead:
                current_piece = next_piece
                next_piece = piece_generator.get_next_piece()
            else:
                current_piece = get_random_piece()

        return game

    def get_statistics(self):
        """Get AI statistics."""
        return {
            'moves_evaluated': self.moves_evaluated,
            'weights': self.weights.copy()
        }


if __name__ == '__main__':
    # Test the AI
    print("Tetris AI Test")
    print("=" * 40)

    from tetris_game import TetrisGame
    from tetris_pieces import get_random_piece

    # Create game and AI
    game = TetrisGame()
    ai = TetrisAI()

    print("\nDefault weights:")
    for key, value in ai.weights.items():
        print(f"  {key}: {value:.6f}")

    # Test heuristic calculations on empty board
    print("\n\nHeuristics on empty board:")
    print(f"  Aggregate Height: {ai.calculate_aggregate_height(game)}")
    print(f"  Complete Lines: {ai.calculate_complete_lines(game)}")
    print(f"  Holes: {ai.calculate_holes(game)}")
    print(f"  Bumpiness: {ai.calculate_bumpiness(game)}")
    print(f"  Overall Score: {ai.evaluate_board(game):.2f}")

    # Place a piece and test again
    piece = get_random_piece()
    print(f"\n\nAfter placing {piece.name} piece:")
    move = ai.get_best_move(game, piece, verbose=True)
    if move:
        game.place_piece(piece, move[0], move[1])
        print(game.display())
        print(f"\nHeuristics:")
        print(f"  Aggregate Height: {ai.calculate_aggregate_height(game)}")
        print(f"  Complete Lines: {ai.calculate_complete_lines(game)}")
        print(f"  Holes: {ai.calculate_holes(game)}")
        print(f"  Bumpiness: {ai.calculate_bumpiness(game)}")
        print(f"  Overall Score: {ai.evaluate_board(game):.2f}")

    # Test a short game
    print("\n\nPlaying a short game (10 pieces):")
    game.reset()
    ai.play_game(game, max_pieces=10, show_board=True)

    print(f"\n\nFinal Statistics:")
    print(f"  Lines Cleared: {game.lines_cleared}")
    print(f"  Score: {game.score}")
    print(f"  Pieces Placed: {game.pieces_placed}")
    print(f"  Moves Evaluated: {ai.moves_evaluated}")

    print("\n✓ AI tests completed")
