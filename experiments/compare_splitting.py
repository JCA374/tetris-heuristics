#!/usr/bin/env python3
"""
Fast paired comparison with multilevel-splitting estimates (tetris/splitting.py).

Each estimate gives ln(pieces per death); every model gets the same estimate
seeds (SPLIT_TEST seeds, never used in training), and the comparison is the
paired difference of logs, i.e. a ratio of expected game lengths. About 17x
cheaper than full games for strong models, so use it to screen; confirm the
final answer with experiments/compare.py on full games.

Example:
    python experiments/compare_splitting.py models/single_v4.json models/single_v6_cem.json --estimates 100
"""

import argparse
import json
import math
import os
import statistics
import sys
import time
import multiprocessing as mp
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tetris import splitting
from tetris.play import SPLIT_TEST_SEED_BASE
from tetris.policy import Policy
from experiments.compare import bootstrap_ci

_STARTS = None


def _init(starts):
    global _STARTS
    _STARTS = starts


def _estimate(args):
    index, model_dict, seed = args
    return index, seed, splitting.estimate(Policy.from_dict(model_dict), _STARTS, seed=seed)['log_pieces']


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('models', nargs='+', help='model JSON files (the first is the reference)')
    parser.add_argument('--estimates', type=int, default=100)
    parser.add_argument('--starts', default='runs/starts/single_v4.json')
    parser.add_argument('--workers', '-w', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--out-dir', default='results')
    args = parser.parse_args()

    with open(args.starts) as f:
        starts = json.load(f)['boards']
    policies = [Policy.load(p) for p in args.models]
    names = [os.path.splitext(os.path.basename(p))[0] for p in args.models]
    seeds = [SPLIT_TEST_SEED_BASE + i for i in range(args.estimates)]
    tasks = [(i, p.to_dict(), s) for i, p in enumerate(policies) for s in seeds]
    logs = [dict() for _ in policies]
    start = time.time()
    with mp.Pool(args.workers, initializer=_init, initargs=(starts,)) as pool:
        for k, (i, seed, value) in enumerate(pool.imap_unordered(_estimate, tasks), 1):
            logs[i][seed] = value
            print(f'\r  {k}/{len(tasks)} estimates  ({time.time() - start:.0f}s)', end='', flush=True)
    print()
    logs = [[d[s] for s in seeds] for d in logs]

    to_lines = lambda v: math.exp(v) / 2.5
    print(f'\n| model | est. lines per game (geo. mean) | 95% CI | vs {names[0]}: ratio (95% CI) |')
    print('|---|---:|---:|---:|')
    out = {'date': datetime.now().isoformat(timespec='seconds'), 'estimates': args.estimates,
           'reference': names[0], 'models': {}}
    for name, values in zip(names, logs):
        mean = statistics.mean(values)
        lo, hi = bootstrap_ci(values)
        row = {'est_lines': to_lines(mean), 'est_lines_ci95': [to_lines(lo), to_lines(hi)], 'log_pieces': values}
        if name != names[0]:
            diffs = [b - a for a, b in zip(logs[0], values)]
            dlo, dhi = bootstrap_ci(diffs)
            d = statistics.mean(diffs)
            row.update({'ratio': math.exp(d), 'ratio_ci95': [math.exp(dlo), math.exp(dhi)],
                        'significant': dlo > 0 or dhi < 0})
            vs = f"{math.exp(d):.2f}x ({math.exp(dlo):.2f}-{math.exp(dhi):.2f}){' *' if row['significant'] else ''}"
        else:
            vs = 'reference'
        out['models'][name] = row
        print(f'| {name} | {to_lines(mean):,.0f} | {to_lines(lo):,.0f}-{to_lines(hi):,.0f} | {vs} |')
    print('\n* = 95% CI of the paired ratio excludes 1')
    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, f'compare_splitting_{datetime.now():%Y%m%d_%H%M%S}.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    print(f'Saved {path}')


if __name__ == '__main__':
    main()
