#!/usr/bin/env python3
"""
Tetris AI Runner

Main script to run the Tetris AI and evaluate its performance.
"""

import argparse
import time
import sys
from tetris_game import TetrisGame
from tetris_ai import TetrisAI


def run_single_game(ai, verbose=False, show_board=False, delay=0, use_lookahead=False):
    """
    Run a single game with the AI.

    Args:
        ai: TetrisAI object
        verbose: Show move details
        show_board: Display board after each move
        delay: Delay between moves in seconds
        use_lookahead: Enable one-piece lookahead

    Returns:
        Game statistics dict
    """
    game = TetrisGame()

    print("\n" + "=" * 50)
    print("Starting new game...")
    if use_lookahead:
        print("(One-piece lookahead ENABLED)")
    print("=" * 50)

    start_time = time.time()
    ai.play_game(game, verbose=verbose, show_board=show_board, use_lookahead=use_lookahead)
    end_time = time.time()

    elapsed = end_time - start_time

    if show_board or verbose:
        print("\n" + "=" * 50)
        print("GAME OVER")
        print("=" * 50)
        print(game.display())

    stats = {
        'lines_cleared': game.lines_cleared,
        'pieces_placed': game.pieces_placed,
        'score': game.score,
        'time': elapsed,
        'moves_evaluated': ai.moves_evaluated
    }

    return stats


def run_multiple_games(num_games, ai, verbose=False, use_lookahead=False):
    """
    Run multiple games and collect statistics.

    Args:
        num_games: Number of games to play
        ai: TetrisAI object
        verbose: Show progress
        use_lookahead: Enable one-piece lookahead

    Returns:
        List of game statistics
    """
    all_stats = []

    for game_num in range(1, num_games + 1):
        if verbose:
            print(f"\n{'='*50}")
            print(f"Game {game_num}/{num_games}")
            print(f"{'='*50}")

        stats = run_single_game(ai, verbose=False, show_board=False, use_lookahead=use_lookahead)
        all_stats.append(stats)

        if verbose:
            print(f"  Lines: {stats['lines_cleared']}")
            print(f"  Pieces: {stats['pieces_placed']}")
            print(f"  Score: {stats['score']}")
            print(f"  Time: {stats['time']:.2f}s")
        else:
            # Show compact progress
            print(f"Game {game_num}/{num_games}: {stats['lines_cleared']} lines, {stats['pieces_placed']} pieces")

    return all_stats


def print_summary(stats_list):
    """
    Print summary statistics from multiple games.

    Args:
        stats_list: List of game statistics dicts
    """
    if not stats_list:
        print("No games played!")
        return

    print("\n" + "=" * 50)
    print("SUMMARY STATISTICS")
    print("=" * 50)

    # Calculate averages
    avg_lines = sum(s['lines_cleared'] for s in stats_list) / len(stats_list)
    avg_pieces = sum(s['pieces_placed'] for s in stats_list) / len(stats_list)
    avg_score = sum(s['score'] for s in stats_list) / len(stats_list)
    avg_time = sum(s['time'] for s in stats_list) / len(stats_list)
    total_moves = sum(s['moves_evaluated'] for s in stats_list)

    # Find best game
    best_game = max(stats_list, key=lambda s: s['lines_cleared'])

    print(f"\nGames Played: {len(stats_list)}")
    print(f"\nAverage Performance:")
    print(f"  Lines Cleared: {avg_lines:.1f}")
    print(f"  Pieces Placed: {avg_pieces:.1f}")
    print(f"  Score: {avg_score:.1f}")
    print(f"  Time per Game: {avg_time:.2f}s")
    print(f"  Time per Move: {(avg_time / avg_pieces * 1000):.1f}ms")

    print(f"\nBest Game:")
    print(f"  Lines Cleared: {best_game['lines_cleared']}")
    print(f"  Pieces Placed: {best_game['pieces_placed']}")
    print(f"  Score: {best_game['score']}")

    print(f"\nTotal Moves Evaluated: {total_moves:,}")

    # Distribution
    print(f"\nLines Cleared Distribution:")
    ranges = [(0, 50), (50, 100), (100, 200), (200, 500), (500, 1000), (1000, float('inf'))]
    for low, high in ranges:
        count = sum(1 for s in stats_list if low <= s['lines_cleared'] < high)
        if count > 0:
            pct = (count / len(stats_list)) * 100
            label = f"{low}-{high}" if high != float('inf') else f"{low}+"
            bar = "█" * int(pct / 2)
            print(f"  {label:>10}: {bar} {count} ({pct:.1f}%)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run Tetris AI with heuristic evaluation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Run one game with visualization
  %(prog)s --games 10                   # Run 10 games and show statistics
  %(prog)s --verbose                    # Show detailed move information
  %(prog)s --test                       # Run quick test game
  %(prog)s --weights="-0.5,0.8,-0.3,-0.2"  # Use custom weights
        """
    )

    parser.add_argument(
        '--games', '-g',
        type=int,
        default=1,
        help='Number of games to play (default: 1)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed move evaluation'
    )

    parser.add_argument(
        '--no-board',
        action='store_true',
        help='Don\'t show board visualization'
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Run a quick test (10 pieces only)'
    )

    parser.add_argument(
        '--lookahead',
        action='store_true',
        help='Enable one-piece lookahead (10× performance boost, slower)'
    )

    parser.add_argument(
        '--weights',
        type=str,
        help='Custom weights: --weights="h,l,o,b" (height,lines,holes,bumpiness)'
    )

    args = parser.parse_args()

    # Create AI
    ai = TetrisAI()

    # Custom weights if provided
    if args.weights:
        try:
            h, l, o, b = map(float, args.weights.split(','))
            ai.weights = {
                'height': h,
                'lines': l,
                'holes': o,
                'bumpiness': b
            }
            print(f"\nUsing custom weights:")
            for key, val in ai.weights.items():
                print(f"  {key}: {val}")
        except Exception as e:
            print(f"Error parsing weights: {e}")
            print('Format: --weights="h,l,o,b" (e.g., --weights="-0.5,0.8,-0.3,-0.2")')
            sys.exit(1)
    else:
        print("\nUsing default weights:")
        for key, val in ai.weights.items():
            print(f"  {key}: {val}")

    # Display lookahead status
    if args.lookahead:
        print("\n🔮 One-piece lookahead: ENABLED")
        print("   Expected: 10× performance boost (5,000-10,000 lines)")
        print("   Note: Move evaluation will be ~160× slower")
    else:
        print("\n🔮 One-piece lookahead: DISABLED")
        print("   Use --lookahead to enable")

    # Test mode
    if args.test:
        print("\n" + "=" * 50)
        print("TEST MODE - Playing 10 pieces")
        print("=" * 50)
        game = TetrisGame()
        ai.play_game(game, max_pieces=10, verbose=args.verbose, show_board=not args.no_board, use_lookahead=args.lookahead)
        print(f"\nTest completed!")
        print(f"  Lines: {game.lines_cleared}")
        print(f"  Pieces: {game.pieces_placed}")
        print(f"  Score: {game.score}")
        return

    # Run games
    if args.games == 1:
        # Single game with visualization
        stats = run_single_game(
            ai,
            verbose=args.verbose,
            show_board=not args.no_board,
            use_lookahead=args.lookahead
        )
        print("\n" + "=" * 50)
        print("GAME STATISTICS")
        print("=" * 50)
        print(f"Lines Cleared: {stats['lines_cleared']}")
        print(f"Pieces Placed: {stats['pieces_placed']}")
        print(f"Score: {stats['score']}")
        print(f"Time: {stats['time']:.2f}s")
        print(f"Moves Evaluated: {stats['moves_evaluated']:,}")
        print(f"Time per Move: {(stats['time'] / stats['pieces_placed'] * 1000):.1f}ms")
    else:
        # Multiple games with summary
        all_stats = run_multiple_games(args.games, ai, verbose=args.verbose, use_lookahead=args.lookahead)
        print_summary(all_stats)


if __name__ == '__main__':
    main()
