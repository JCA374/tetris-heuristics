#!/usr/bin/env python3
"""
Watch a model play Tetris in the terminal (colored, no dependencies).

Examples:
    python demo.py                                   # best available model
    python demo.py --model models/regime_v2.json     # shows which regime is active
    python demo.py --delay 0 --pieces 2000           # fast run
    python demo.py --lookahead --seed 7
    python demo.py --list                            # models in models/
"""

import argparse
import glob
import os
import sys
import time

from tetris import Policy, play_game
from tetris.features import compute_features

RESET, BOLD, DIM = '\033[0m', '\033[1m', '\033[2m'
PIECE_COLORS = {
    'I': '\033[96m', 'O': '\033[93m', 'T': '\033[95m', 'S': '\033[92m',
    'Z': '\033[91m', 'J': '\033[94m', 'L': '\033[38;5;214m',
}
REGIME_COLORS = {'normal': '\033[92m', 'danger': '\033[91m', 'repair': '\033[93m', 'default': '\033[96m'}
MODEL_PREFERENCE = ['regime_v2', 'single_v2', 'baseline_single_v1']


def default_model():
    for name in MODEL_PREFERENCE:
        path = os.path.join('models', f'{name}.json')
        if os.path.exists(path):
            return path
    sys.exit('No model found in models/. Train one with training/train.py')


def piece_lines(piece, label):
    coords = piece.get_rotation(0)
    rows = max(r for r, _ in coords) + 1
    cols = max(c for _, c in coords) + 1
    color = PIECE_COLORS.get(piece.name, '')
    out = [f'{BOLD}{label}{RESET}']
    for r in range(rows):
        out.append('  ' + ''.join(color + '██' + RESET if (r, c) in coords else '  ' for c in range(cols)))
    return out


def render(game, stream, policy, model_name, lookahead):
    board = [f'{BOLD}┌{"─" * (game.width * 2)}┐{RESET}']
    for row in game.board:
        cells = ''.join('  ' if c == 0 else PIECE_COLORS.get(c, '') + '██' + RESET for c in row)
        board.append(f'{BOLD}│{RESET}{cells}{BOLD}│{RESET}')
    board.append(f'{BOLD}└{"─" * (game.width * 2)}┘{RESET}')

    regime = getattr(policy, 'last_regime', '-')
    features = compute_features(game)
    side = [
        f'{BOLD}{model_name}{RESET}',
        '',
        f'Lines   {BOLD}{game.lines_cleared}{RESET}',
        f'Pieces  {game.pieces_placed}',
        f'Score   {game.score}',
        '',
        f'Regime  {REGIME_COLORS.get(regime, "")}{BOLD}{regime}{RESET}',
    ]
    if not policy.is_single:
        total = sum(policy.regime_counts.values()) or 1
        for name, count in sorted(policy.regime_counts.items()):
            side.append(f'  {name:<7} {count / total:5.0%}')
    side += [
        '',
        f'{DIM}height {features["height"]}  holes {features["holes"]}  bump {features["bumpiness"]}{RESET}',
        '',
    ]
    side += piece_lines(stream.next, 'NEXT' + (' (lookahead)' if lookahead else ''))

    out = []
    for i, line in enumerate(board):
        out.append(line + '   ' + (side[i] if i < len(side) else ''))
    return '\n'.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--model', help='model JSON (default: best in models/)')
    parser.add_argument('--delay', type=int, default=50, help='ms between pieces (0 = as fast as possible)')
    parser.add_argument('--pieces', type=int, help='stop after N pieces')
    parser.add_argument('--seed', type=int, help='piece sequence seed (default: random)')
    parser.add_argument('--lookahead', action='store_true')
    parser.add_argument('--randomizer', choices=['random', 'bag'], default='random')
    parser.add_argument('--every', type=int, default=1, help='redraw every N pieces')
    parser.add_argument('--list', action='store_true', help='list models and exit')
    args = parser.parse_args()

    if args.list:
        for path in sorted(glob.glob('models/*.json')):
            policy = Policy.load(path)
            print(f'\n{path}  ({policy.meta.get("validation_mean", "?")} validation lines)')
            print(policy.describe())
        return

    path = args.model or default_model()
    policy = Policy.load(path)
    name = os.path.splitext(os.path.basename(path))[0]

    def on_move(game, stream, policy):
        if game.pieces_placed % args.every == 0:
            sys.stdout.write('\033[H\033[J' + render(game, stream, policy, name, args.lookahead) + '\n')
            sys.stdout.flush()
            if args.delay:
                time.sleep(args.delay / 1000)

    try:
        result = play_game(policy, seed=args.seed, max_pieces=args.pieces, lookahead=args.lookahead,
                           randomizer=args.randomizer, on_move=on_move)
    except KeyboardInterrupt:
        print('\nStopped.')
        return
    print(f"\n{'Stopped' if result['capped'] else 'Game over'}: {result['lines']} lines, "
          f"{result['pieces']} pieces, score {result['score']}")
    if not policy.is_single:
        total = sum(result['regime_counts'].values()) or 1
        print('Regime usage: ' + ', '.join(f'{k} {v / total:.0%}' for k, v in sorted(result['regime_counts'].items())))


if __name__ == '__main__':
    main()
