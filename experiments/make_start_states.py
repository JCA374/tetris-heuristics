#!/usr/bin/env python3
"""
Extract clean start boards from recorded games (experiments/record_games.py) for
splitting-based training (train.py --fitness splitting).

Takes mid-game snapshots with no holes that are far from the game's end
(typical healthy play). Splitting estimates start from these boards; the crisis
boards are then reached by each evaluated policy's own play, so this set only
needs to look like normal play, not like any particular crisis.

Example:
    python experiments/make_start_states.py runs/games/single_v4.jsonl.gz
    -> runs/starts/single_v4.json
"""

import argparse
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tetris.fastcore import board_rows


def holes(rows, width=10):
    seen, n = 0, 0
    for r in rows:
        n += bin(seen & ~r & ((1 << width) - 1)).count('1')
        seen |= r
    return n


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('games', help='runs/games/<model>.jsonl.gz')
    parser.add_argument('--min-before-end', type=int, default=20_000,
                        help='only snapshots at least this many pieces before the game ended')
    parser.add_argument('--out', help='default: runs/starts/<model>.json')
    args = parser.parse_args()

    with gzip.open(args.games, 'rt') as f:
        header = json.loads(f.readline())['header']
        games = [json.loads(line) for line in f]
    boards = []
    for g in games:
        for s in g['record']['snapshots']:
            if g['pieces'] - s['n'] >= args.min_before_end:
                rows = board_rows(s['board'])
                if holes(rows) == 0:
                    boards.append(rows)
    out = args.out or os.path.join('runs', 'starts', f"{header['model']}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        json.dump({'source': args.games, 'model': header['model'], 'boards': boards}, f)
    print(f'{len(games)} games -> {len(boards)} clean start boards')
    print(f'Saved {out}')


if __name__ == '__main__':
    main()
