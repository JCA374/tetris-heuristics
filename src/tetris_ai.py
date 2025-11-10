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

    # Default weights based on research and genetic algorithm optimization
    DEFAULT_WEIGHTS = {
        'height': -0.510066,
        'lines': 0.760666,
        'holes': -0.35663,
        'bumpiness': -0.184483
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

    def get_best_move(self, game, piece, verbose=False):
        """
        Find the best move for a given piece.

        Evaluates all possible placements and returns the one
        with the highest score.

        Args:
            game: TetrisGame object
            piece: TetrisPiece to place
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
            score = self.evaluate_board(sim_game)
            move_scores.append((rotation, col, score))

            if score > best_score:
                best_score = score
                best_move = (rotation, col)

            self.moves_evaluated += 1

        if verbose and move_scores:
            print(f"\nEvaluated {len(move_scores)} possible moves for piece {piece.name}:")
            # Show top 5 moves
            move_scores.sort(key=lambda x: x[2], reverse=True)
            for i, (rot, col, score) in enumerate(move_scores[:5]):
                marker = "★" if (rot, col) == best_move else " "
                print(f"  {marker} Rotation {rot}, Column {col}: {score:.2f}")

        return best_move

    def play_game(self, game, max_pieces=None, verbose=False, show_board=False):
        """
        Play a complete game using the AI.

        Args:
            game: TetrisGame object
            max_pieces: Maximum pieces to place (None for unlimited)
            verbose: If True, print move details
            show_board: If True, display board after each move

        Returns:
            Final game state
        """
        from tetris_pieces import get_random_piece

        pieces_placed = 0
        self.moves_evaluated = 0

        while not game.game_over:
            if max_pieces and pieces_placed >= max_pieces:
                break

            # Get next piece
            piece = get_random_piece()

            # Find best move
            move = self.get_best_move(game, piece, verbose=verbose)

            if move is None:
                game.game_over = True
                break

            rotation, col = move

            # Make the move
            game.place_piece(piece, rotation, col)
            pieces_placed += 1

            if show_board:
                print(f"\n--- Piece {pieces_placed} ({piece.name}) ---")
                print(game.display())

            if verbose and pieces_placed % 100 == 0:
                print(f"Progress: {pieces_placed} pieces, {game.lines_cleared} lines")

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
