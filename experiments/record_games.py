#!/usr/bin/env python3
"""
Play games and save board logs for feature research.

Per game it stores the final board, the last N boards before the end (with the
move, regime and lines cleared), a snapshot every K pieces, the piece that could
not be placed, and piece droughts at death. Output is gzipped JSON lines, one
game per line, in runs/games/ (git-ignored).

Examples:
    python experiments/record_games.py models/baseline_single_v1.json --games 500
    python experiments/record_games.py models/regime_v2.json --games 500 --workers 8
    python experiments/analyze_games.py runs/games/baseline_single_v1.jsonl.gz
"""

import argparse
import gzip
import json
import os
import sys
import time
import multiprocessing as mp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tetris.policy import Policy
from tetris.play import play_game, GameRecorder, ANALYSIS_SEED_BASE


def _play(args):
    model_dict, seed, max_pieces, lookahead, randomizer, keep_last, snapshot_every = args
    return play_game(Policy.from_dict(model_dict), seed=seed, max_pieces=max_pieces,
                     lookahead=lookahead, randomizer=randomizer,
                     recorder=GameRecorder(keep_last, snapshot_every))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('model', help='model JSON')
    parser.add_argument('--games', type=int, default=500)
    parser.add_argument('--keep-last', type=int, default=300, help='boards kept before the end of each game')
    parser.add_argument('--snapshot-every', type=int, default=100, help='mid-game snapshot interval (pieces)')
    parser.add_argument('--max-pieces', type=int, default=100000)
    parser.add_argument('--lookahead', action='store_true')
    parser.add_argument('--randomizer', choices=['random', 'bag'], default='random')
    parser.add_argument('--workers', '-w', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--out', help='output file (default: runs/games/<model>.jsonl.gz)')
    args = parser.parse_args()

    policy = Policy.load(args.model)
    name = os.path.splitext(os.path.basename(args.model))[0]
    out = args.out or os.path.join('runs', 'games', f'{name}.jsonl.gz')
    os.makedirs(os.path.dirname(out), exist_ok=True)

    seeds = [ANALYSIS_SEED_BASE + i for i in range(args.games)]
    tasks = [(policy.to_dict(), s, args.max_pieces, args.lookahead, args.randomizer,
              args.keep_last, args.snapshot_every) for s in seeds]
    header = {'model': name, 'path': args.model, 'policy': policy.to_dict(),
              'settings': {k: v for k, v in vars(args).items() if k not in ('model', 'out')}}

    start = time.time()
    with gzip.open(out, 'wt') as f, mp.Pool(args.workers) as pool:
        f.write(json.dumps({'header': header}) + '\n')
        for i, result in enumerate(pool.imap_unordered(_play, tasks), 1):
            result['model'] = name
            f.write(json.dumps(result, separators=(',', ':')) + '\n')
            if i % 10 == 0 or i == len(tasks):
                print(f'\r{i}/{len(tasks)} games ({time.time() - start:.0f}s)', end='', flush=True)
    print(f'\nSaved {out} ({os.path.getsize(out) / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
