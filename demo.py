#!/usr/bin/env python3
"""
Tetris AI Demo - Watch the AI Play

Allows you to watch the AI play Tetris in real-time with different weight sets.
"""

import argparse
import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tetris_game import TetrisGame
from tetris_ai import TetrisAI


# Pre-configured weight sets from research
WEIGHT_SETS = {
    'current': {
        'name': 'Current Implementation (Lee 2013)',
        'weights': {
            'height': -0.510066,
            'lines': 0.760666,
            'holes': -0.35663,
            'bumpiness': -0.184483
        },
        'expected_performance': '500-2,000 lines',
        'source': 'GA-optimized by Y. Lee (2013)'
    },

    'aggressive': {
        'name': 'Aggressive Line Clearing',
        'weights': {
            'height': -0.3,
            'lines': 1.0,
            'holes': -0.5,
            'bumpiness': -0.1
        },
        'expected_performance': '100-1,000 lines',
        'source': 'Hand-tuned for maximum line clearing'
    },

    'defensive': {
        'name': 'Defensive (Minimize Holes)',
        'weights': {
            'height': -0.6,
            'lines': 0.5,
            'holes': -0.8,
            'bumpiness': -0.3
        },
        'expected_performance': '200-1,500 lines',
        'source': 'Hand-tuned for survival'
    },

    'balanced': {
        'name': 'Balanced Strategy',
        'weights': {
            'height': -0.5,
            'lines': 0.75,
            'holes': -0.4,
            'bumpiness': -0.2
        },
        'expected_performance': '300-2,000 lines',
        'source': 'Balanced across all metrics'
    }
}


def clear_screen():
    """Clear the terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')


def print_game_state(game, piece_name, move_num, delay, ai_name):
    """Print the current game state in an attractive format."""
    clear_screen()

    print("=" * 60)
    print(f"🎮  TETRIS AI DEMO - {ai_name}")
    print("=" * 60)
    print()
    print(game.display())
    print()
    print(f"Current Piece: {piece_name}")
    print(f"Move #{move_num}")
    print(f"Speed: {1000/delay:.0f} moves/sec ({delay}ms delay)")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)


def demo_play(weight_set_name='current', max_pieces=None, delay=200, verbose=False):
    """
    Watch the AI play Tetris in real-time.

    Args:
        weight_set_name: Name of weight set to use
        max_pieces: Maximum pieces to place (None for unlimited)
        delay: Delay in ms between moves
        verbose: Show detailed move evaluations
    """
    # Load weight set
    if weight_set_name not in WEIGHT_SETS:
        print(f"Error: Unknown weight set '{weight_set_name}'")
        print(f"Available: {', '.join(WEIGHT_SETS.keys())}")
        return

    weight_config = WEIGHT_SETS[weight_set_name]

    # Create game and AI
    game = TetrisGame()
    ai = TetrisAI(weights=weight_config['weights'])

    print("\n" + "=" * 60)
    print(f"🎮  STARTING TETRIS AI DEMO")
    print("=" * 60)
    print(f"\nModel: {weight_config['name']}")
    print(f"Source: {weight_config['source']}")
    print(f"Expected Performance: {weight_config['expected_performance']}")
    print(f"\nWeights:")
    for key, val in weight_config['weights'].items():
        print(f"  {key:12s}: {val:+.6f}")
    print("\n" + "=" * 60)
    print("\nStarting game in 3 seconds...")
    time.sleep(3)

    # Play game
    from tetris_pieces import get_random_piece

    pieces_placed = 0
    move_num = 0

    try:
        while not game.game_over:
            if max_pieces and pieces_placed >= max_pieces:
                break

            # Get next piece
            piece = get_random_piece()

            # Find best move
            move = ai.get_best_move(game, piece, verbose=verbose)

            if move is None:
                game.game_over = True
                break

            rotation, col = move

            # Display board before move
            print_game_state(game, piece.name, move_num, delay, weight_config['name'])

            # Wait for animation
            time.sleep(delay / 1000.0)

            # Make the move
            game.place_piece(piece, rotation, col)
            pieces_placed += 1
            move_num += 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Game stopped by user")

    # Final statistics
    clear_screen()
    print("\n" + "=" * 60)
    print("🏁  GAME OVER")
    print("=" * 60)
    print()
    print(game.display())
    print()
    print("📊  FINAL STATISTICS")
    print("=" * 60)
    print(f"Model: {weight_config['name']}")
    print(f"Lines Cleared: {game.lines_cleared}")
    print(f"Pieces Placed: {game.pieces_placed}")
    print(f"Final Score: {game.score}")
    print(f"Moves Evaluated: {ai.moves_evaluated:,}")

    if game.pieces_placed > 0:
        print(f"Average Lines/Piece: {game.lines_cleared / game.pieces_placed:.2f}")

    print("=" * 60)
    print()


def compare_models(games_per_model=5):
    """
    Compare all available weight sets.

    Args:
        games_per_model: Number of games to run per model
    """
    print("\n" + "=" * 60)
    print("📊  MODEL COMPARISON")
    print("=" * 60)
    print(f"\nRunning {games_per_model} games per model...")
    print()

    results = {}

    for model_name, config in WEIGHT_SETS.items():
        print(f"\nTesting {config['name']}...")

        ai = TetrisAI(weights=config['weights'])
        game_results = []

        for game_num in range(games_per_model):
            game = TetrisGame()
            ai.play_game(game, verbose=False, show_board=False)

            game_results.append({
                'lines': game.lines_cleared,
                'pieces': game.pieces_placed,
                'score': game.score
            })

            print(f"  Game {game_num+1}/{games_per_model}: {game.lines_cleared} lines")

        # Calculate averages
        avg_lines = sum(g['lines'] for g in game_results) / games_per_model
        avg_pieces = sum(g['pieces'] for g in game_results) / games_per_model
        avg_score = sum(g['score'] for g in game_results) / games_per_model
        max_lines = max(g['lines'] for g in game_results)

        results[model_name] = {
            'config': config,
            'avg_lines': avg_lines,
            'avg_pieces': avg_pieces,
            'avg_score': avg_score,
            'max_lines': max_lines,
            'games': game_results
        }

    # Print comparison table
    print("\n\n" + "=" * 80)
    print("📊  COMPARISON RESULTS")
    print("=" * 80)
    print()
    print(f"{'Model':<30} {'Avg Lines':<12} {'Max Lines':<12} {'Avg Score':<12}")
    print("-" * 80)

    # Sort by average lines
    sorted_results = sorted(results.items(), key=lambda x: x[1]['avg_lines'], reverse=True)

    for model_name, data in sorted_results:
        config = data['config']
        marker = "🏆" if model_name == sorted_results[0][0] else "  "
        print(f"{marker} {config['name']:<28} {data['avg_lines']:<12.1f} "
              f"{data['max_lines']:<12} {data['avg_score']:<12.0f}")

    print("=" * 80)
    print()
    print(f"🏆 Winner: {sorted_results[0][1]['config']['name']}")
    print(f"   Average: {sorted_results[0][1]['avg_lines']:.1f} lines")
    print(f"   Best game: {sorted_results[0][1]['max_lines']} lines")
    print()


def list_models():
    """List all available models with their details."""
    print("\n" + "=" * 60)
    print("📚  AVAILABLE MODELS")
    print("=" * 60)
    print()

    for model_name, config in WEIGHT_SETS.items():
        print(f"Model: {model_name}")
        print(f"Name: {config['name']}")
        print(f"Source: {config['source']}")
        print(f"Expected Performance: {config['expected_performance']}")
        print("Weights:")
        for key, val in config['weights'].items():
            print(f"  {key:12s}: {val:+.6f}")
        print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Watch Tetris AI play with different strategies',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Watch current model play
  %(prog)s --model aggressive       # Watch aggressive strategy
  %(prog)s --delay 100              # Faster animation (100ms)
  %(prog)s --max-pieces 50          # Stop after 50 pieces
  %(prog)s --compare                # Compare all models
  %(prog)s --list                   # List available models
        """
    )

    parser.add_argument(
        '--model', '-m',
        type=str,
        default='current',
        help='Model to use (current, aggressive, defensive, balanced)'
    )

    parser.add_argument(
        '--delay', '-d',
        type=int,
        default=200,
        help='Delay between moves in milliseconds (default: 200)'
    )

    parser.add_argument(
        '--max-pieces', '-p',
        type=int,
        default=None,
        help='Maximum pieces to place (default: unlimited)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed move evaluation'
    )

    parser.add_argument(
        '--compare', '-c',
        action='store_true',
        help='Compare all available models'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all available models'
    )

    parser.add_argument(
        '--games',
        type=int,
        default=5,
        help='Number of games per model in comparison mode (default: 5)'
    )

    args = parser.parse_args()

    if args.list:
        list_models()
    elif args.compare:
        compare_models(games_per_model=args.games)
    else:
        demo_play(
            weight_set_name=args.model,
            max_pieces=args.max_pieces,
            delay=args.delay,
            verbose=args.verbose
        )


if __name__ == '__main__':
    main()
