#!/usr/bin/env python3
"""
Play with the Best Trained Model

Loads the best model from GA training (best_model.json) and lets you:
- Watch it play
- Run benchmarks
- Compare to default weights
"""

import json
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tetris_game import TetrisGame
from tetris_ai import TetrisAI


def load_best_model():
    """Load the best trained model."""
    try:
        with open('best_model.json', 'r') as f:
            data = json.load(f)

        print("=" * 70)
        print("🏆  LOADING BEST TRAINED MODEL")
        print("=" * 70)
        print(f"\nModel Info:")
        print(f"  {data['info']}")
        print(f"  Fitness: {data['fitness']:.1f} lines")
        print(f"  Trained with lookahead: {data.get('trained_with_lookahead', False)}")
        print(f"\nWeights:")
        for key, val in data['weights'].items():
            print(f"  {key:12s}: {val:+.6f}")
        print("=" * 70)

        return data['weights'], data
    except FileNotFoundError:
        print("❌ Error: best_model.json not found!")
        print("\nYou need to train a model first:")
        print("  python train_ga.py --quick")
        print("\nOr use default weights:")
        print("  python src/main.py")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        sys.exit(1)


def play_games(weights, num_games=5, use_lookahead=False):
    """Play multiple games and show statistics."""
    ai = TetrisAI(weights=weights)

    print(f"\n🎮 Playing {num_games} game(s)...")
    if use_lookahead:
        print("   (with one-piece lookahead)")
    print()

    results = []

    for i in range(num_games):
        game = TetrisGame()
        ai.play_game(game, use_lookahead=use_lookahead)

        results.append({
            'lines': game.lines_cleared,
            'pieces': game.pieces_placed,
            'score': game.score
        })

        print(f"  Game {i+1}/{num_games}: {game.lines_cleared} lines, {game.pieces_placed} pieces")

    # Statistics
    avg_lines = sum(r['lines'] for r in results) / len(results)
    max_lines = max(r['lines'] for r in results)
    min_lines = min(r['lines'] for r in results)

    print("\n" + "=" * 70)
    print("📊  RESULTS")
    print("=" * 70)
    print(f"  Average: {avg_lines:.1f} lines")
    print(f"  Best:    {max_lines} lines")
    print(f"  Worst:   {min_lines} lines")
    print("=" * 70)


def compare_to_default(trained_weights, num_games=5):
    """Compare trained model to default weights."""
    print("\n" + "=" * 70)
    print("⚖️  COMPARING TO DEFAULT WEIGHTS")
    print("=" * 70)

    # Default weights (defensive)
    default_weights = {
        'height': -0.600000,
        'lines': 0.500000,
        'holes': -0.800000,
        'bumpiness': -0.300000
    }

    print("\n🤖 Testing DEFAULT weights...")
    default_ai = TetrisAI(weights=default_weights)
    default_results = []

    for i in range(num_games):
        game = TetrisGame()
        default_ai.play_game(game)
        default_results.append(game.lines_cleared)
        print(f"  Game {i+1}/{num_games}: {game.lines_cleared} lines")

    default_avg = sum(default_results) / len(default_results)

    print("\n🧬 Testing TRAINED weights...")
    trained_ai = TetrisAI(weights=trained_weights)
    trained_results = []

    for i in range(num_games):
        game = TetrisGame()
        trained_ai.play_game(game)
        trained_results.append(game.lines_cleared)
        print(f"  Game {i+1}/{num_games}: {game.lines_cleared} lines")

    trained_avg = sum(trained_results) / len(trained_results)

    # Comparison
    print("\n" + "=" * 70)
    print("📊  COMPARISON RESULTS")
    print("=" * 70)
    print(f"  Default weights:  {default_avg:.1f} lines (avg)")
    print(f"  Trained weights:  {trained_avg:.1f} lines (avg)")

    improvement = ((trained_avg - default_avg) / default_avg) * 100
    if improvement > 0:
        print(f"\n  🎉 Trained model is {improvement:.1f}% BETTER!")
    elif improvement < 0:
        print(f"\n  ⚠️  Trained model is {abs(improvement):.1f}% worse")
    else:
        print(f"\n  Equal performance")

    print("=" * 70)


def watch_game(weights, use_lookahead=False):
    """Watch the model play one game in slow motion."""
    print("\n" + "=" * 70)
    print("👁️  WATCHING MODEL PLAY")
    print("=" * 70)
    print("\nStarting game in 2 seconds...")
    import time
    time.sleep(2)

    ai = TetrisAI(weights=weights)
    game = TetrisGame()

    # Play with board display
    ai.play_game(game, show_board=True, use_lookahead=use_lookahead)

    print("\n" + "=" * 70)
    print("GAME OVER")
    print("=" * 70)
    print(f"Lines:  {game.lines_cleared}")
    print(f"Pieces: {game.pieces_placed}")
    print(f"Score:  {game.score}")
    print("=" * 70)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Play with Best Trained Model')
    parser.add_argument('--games', '-g', type=int, default=5,
                        help='Number of games to play (default: 5)')
    parser.add_argument('--lookahead', action='store_true',
                        help='Use one-piece lookahead')
    parser.add_argument('--compare', action='store_true',
                        help='Compare to default weights')
    parser.add_argument('--watch', action='store_true',
                        help='Watch one game in slow motion')
    parser.add_argument('--pygame', action='store_true',
                        help='Launch pygame demo with trained weights')

    args = parser.parse_args()

    # Load best model
    weights, model_data = load_best_model()

    if args.pygame:
        # Launch pygame demo
        print("\n🎮 Launching pygame demo with trained weights...")
        print("\nNote: You'll need to manually update demo_pygame.py")
        print("      or use the weights directly in the game.")
        print("\nWeights to use:")
        print(f"  height={weights['height']:.6f}")
        print(f"  lines={weights['lines']:.6f}")
        print(f"  holes={weights['holes']:.6f}")
        print(f"  bumpiness={weights['bumpiness']:.6f}")
        return

    if args.watch:
        watch_game(weights, use_lookahead=args.lookahead)
    elif args.compare:
        compare_to_default(weights, num_games=args.games)
    else:
        play_games(weights, num_games=args.games, use_lookahead=args.lookahead)

    print("\n💡 Tip: Use these weights in main.py:")
    print(f"  python src/main.py --weights {weights['height']:.6f},{weights['lines']:.6f},{weights['holes']:.6f},{weights['bumpiness']:.6f}")


if __name__ == '__main__':
    main()
