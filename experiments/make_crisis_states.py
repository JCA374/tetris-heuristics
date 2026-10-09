#!/usr/bin/env python3
"""
Extract crisis start states from recorded games (experiments/record_games.py),
for training repair behaviour (train.py --crisis).

From each game that ended in game over, boards are taken from the run-up to
death at several distances before the end, as long as they have at least one
hole. With fresh pieces most of these are recoverable: single_v4 recovers 51%
of states 10 pieces before death, 80% at 30, 96% at 100+. The default 10-40
(~70%) leaves room to measure improvement. Games are split into train and
validation by index, so no game contributes to both.

Example:
    python experiments/make_crisis_states.py runs/games/single_v4.jsonl.gz
    -> runs/crisis/single_v4.json
"""

import argparse
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tetris.fastcore import board_rows


def holes(board):
    seen, count = [False] * len(board[0]), 0
    for row in board:
        for c, ch in enumerate(row):
            if ch != '.':
                seen[c] = True
            elif seen[c]:
                count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('games', help='runs/games/<model>.jsonl.gz')
    parser.add_argument('--distances', default='40,30,20,10',
                        help='pieces before game over at which to take a board')
    parser.add_argument('--validation-share', type=float, default=0.2)
    parser.add_argument('--out', help='default: runs/crisis/<model>.json')
    args = parser.parse_args()

    distances = [int(d) for d in args.distances.split(',')]
    with gzip.open(args.games, 'rt') as f:
        header = json.loads(f.readline())['header']
        games = [json.loads(line) for line in f]
    dead = [g for g in games if g['record']['game_over']]

    split = {'train': [], 'validation': []}
    every = max(2, round(1 / args.validation_share))
    for i, g in enumerate(dead):
        recent = g['record']['recent']
        end = g['pieces']
        target = 'validation' if i % every == 0 else 'train'
        for d in distances:
            j = len(recent) - d
            if j < 0:
                continue
            board = recent[j]['board']
            h = holes(board)
            if h == 0:
                continue
            split[target].append({'seed': g['seed'], 'before_death': end - recent[j]['n'],
                                  'holes': h, 'rows': board_rows(board)})

    out = args.out or os.path.join('runs', 'crisis', f"{header['model']}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        json.dump({'source': args.games, 'model': header['model'], 'distances': distances, **split}, f)
    print(f"{len(dead)} games -> {len(split['train'])} train / {len(split['validation'])} validation states")
    print(f'Saved {out}')


if __name__ == '__main__':
    main()
