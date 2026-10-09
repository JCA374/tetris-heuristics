#!/usr/bin/env python3
"""
Head-to-head benchmark of models on held-out seeds.

Every model plays exactly the same piece sequences (TEST seeds, never used in
training or validation). Because Tetris scores vary ~10x between games, the
comparison is *paired*: per seed, model B minus the reference model A.

Examples:
    python experiments/compare.py models/baseline_single_v1.json models/single_v2.json models/regime_v2.json
    python experiments/compare.py models/*.json --games 50 --ref models/single_v2.json
"""

import argparse
import json
import os
import random
import statistics
import sys
import time
import multiprocessing as mp
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tetris.policy import Policy
from tetris.play import play_game, TEST_SEED_BASE

BOOTSTRAP_SAMPLES = 10000


def _play(args):
    model_index, model_dict, seed, max_pieces, lookahead, randomizer = args
    result = play_game(Policy.from_dict(model_dict), seed=seed, max_pieces=max_pieces,
                       lookahead=lookahead, randomizer=randomizer)
    return model_index, result


def bootstrap_ci(values, stat=statistics.mean, rng=None, level=0.95):
    rng = rng or random.Random(0)
    n = len(values)
    samples = sorted(stat([values[rng.randrange(n)] for _ in range(n)]) for _ in range(BOOTSTRAP_SAMPLES))
    lo = samples[int((1 - level) / 2 * BOOTSTRAP_SAMPLES)]
    hi = samples[int((1 + level) / 2 * BOOTSTRAP_SAMPLES) - 1]
    return lo, hi


def summarize(lines):
    lo, hi = bootstrap_ci(lines)
    return {
        'mean': statistics.mean(lines),
        'median': statistics.median(lines),
        'std': statistics.stdev(lines) if len(lines) > 1 else 0.0,
        'min': min(lines),
        'max': max(lines),
        'mean_ci95': [lo, hi],
    }


def paired(ref, other):
    """Paired comparison of `other` vs `ref` on the same seeds."""
    diffs = [b - a for a, b in zip(ref, other)]
    lo, hi = bootstrap_ci(diffs)
    ratios = [(b + 1) / (a + 1) for a, b in zip(ref, other)]
    return {
        'mean_diff': statistics.mean(diffs),
        'mean_diff_ci95': [lo, hi],
        'wins': sum(d > 0 for d in diffs),
        'losses': sum(d < 0 for d in diffs),
        'ties': sum(d == 0 for d in diffs),
        'median_ratio': statistics.median(ratios),
        'significant': lo > 0 or hi < 0,
    }


def running_report(names, results, seeds, ref_index, done, total, elapsed):
    """Interim block: mean per model so far, and the paired difference vs the reference on the
    seeds both have finished (normal-approximation 95% CI; the final report uses the bootstrap)."""
    eta = elapsed / done * (total - done) if done else 0
    out = [f'--- {done}/{total} games, {elapsed / 60:.1f} min elapsed, ~{eta / 60:.0f} min left ---']
    ref = results[ref_index]
    for m, name in enumerate(names):
        vals = [r['lines'] for r in results[m].values()]
        if not vals:
            continue
        line = f'  {name:24s} n={len(vals):5d}  mean {statistics.mean(vals):>12,.0f}  median {statistics.median(vals):>12,.0f}'
        if m != ref_index:
            both = [s for s in seeds if s in results[m] and s in ref]
            if len(both) >= 2:
                diffs = [results[m][s]['lines'] - ref[s]['lines'] for s in both]
                mean = statistics.mean(diffs)
                half = 1.96 * statistics.stdev(diffs) / len(diffs) ** 0.5
                pct = mean / max(statistics.mean(ref[s]['lines'] for s in both), 1)
                sig = ' *' if abs(mean) > half else ''
                line += f'  diff {mean:>+11,.0f} ({pct:+.1%}) ±{half:,.0f}{sig}'
        out.append(line)
    return '\n'.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('models', nargs='+', help='model JSON files')
    parser.add_argument('--games', type=int, default=50)
    parser.add_argument('--max-pieces', type=int, default=100000, help='safety cap per game')
    parser.add_argument('--lookahead', action='store_true')
    parser.add_argument('--randomizer', choices=['random', 'bag'], default='random')
    parser.add_argument('--workers', '-w', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--ref', help='reference model for paired tests (default: first model)')
    parser.add_argument('--out-dir', default='results')
    parser.add_argument('--report-every', type=float, default=60,
                        help='seconds between running averages (0 = off)')
    args = parser.parse_args()

    names = [os.path.splitext(os.path.basename(p))[0] for p in args.models]
    policies = [Policy.load(p) for p in args.models]
    ref_index = args.models.index(args.ref) if args.ref else 0
    seeds = [TEST_SEED_BASE + i for i in range(args.games)]

    print(f"Comparing {len(policies)} models on {args.games} held-out seeds "
          f"(randomizer={args.randomizer}, lookahead={args.lookahead}, cap={args.max_pieces} pieces)")
    for name, policy in zip(names, policies):
        print(f"\n[{name}]\n{policy.describe()}")

    tasks = [(m, policies[m].to_dict(), s, args.max_pieces, args.lookahead, args.randomizer)
             for s in seeds for m in range(len(policies))]
    results = [dict() for _ in policies]
    start = last_report = time.time()
    done = 0
    with mp.Pool(args.workers) as pool:
        for m, result in pool.imap_unordered(_play, tasks):
            results[m][result['seed']] = result
            done += 1
            now = time.time()
            if args.report_every and now - last_report >= args.report_every:
                last_report = now
                print('\r' + running_report(names, results, seeds, ref_index, done, len(tasks), now - start),
                      flush=True)
            print(f"\r  {done}/{len(tasks)} games  ({now - start:.0f}s)", end='', flush=True)
    print()

    lines = [[results[m][s]['lines'] for s in seeds] for m in range(len(policies))]

    report = {
        'date': datetime.now().isoformat(timespec='seconds'),
        'settings': {'games': args.games, 'seeds': [seeds[0], seeds[-1]], 'max_pieces': args.max_pieces,
                     'lookahead': args.lookahead, 'randomizer': args.randomizer},
        'reference': names[ref_index],
        'models': {},
    }
    for m, name in enumerate(names):
        regime_totals = {}
        for r in results[m].values():
            for k, v in r['regime_counts'].items():
                regime_totals[k] = regime_totals.get(k, 0) + v
        total_moves = sum(regime_totals.values()) or 1
        report['models'][name] = {
            'path': args.models[m],
            'policy': policies[m].to_dict(),
            'summary': summarize(lines[m]),
            'capped_games': sum(r['capped'] for r in results[m].values()),
            'regime_usage': {k: v / total_moves for k, v in regime_totals.items()},
            'paired_vs_reference': None if m == ref_index else paired(lines[ref_index], lines[m]),
            'lines_per_seed': lines[m],
        }

    # --- print table -----------------------------------------------------------
    ref = names[ref_index]
    print(f"\n| model | mean | 95% CI | median | std | vs {ref}: mean diff (95% CI) | W/L | median ratio |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name in names:
        r = report['models'][name]
        s = r['summary']
        p = r['paired_vs_reference']
        if p:
            sig = ' *' if p['significant'] else ''
            vs = (f"{p['mean_diff']:+.0f} ({p['mean_diff_ci95'][0]:+.0f}..{p['mean_diff_ci95'][1]:+.0f}){sig} "
                  f"| {p['wins']}/{p['losses']} | {p['median_ratio']:.2f}x")
        else:
            vs = "reference | | "
        print(f"| {name} | {s['mean']:.0f} | {s['mean_ci95'][0]:.0f}-{s['mean_ci95'][1]:.0f} | "
              f"{s['median']:.0f} | {s['std']:.0f} | {vs} |")
    print("\n* = 95% CI of the paired difference excludes 0")
    for name in names:
        usage = report['models'][name]['regime_usage']
        if len(usage) > 1:
            print(f"regime usage {name}: " + ", ".join(f"{k} {v:.0%}" for k, v in sorted(usage.items())))
        capped = report['models'][name]['capped_games']
        if capped:
            print(f"note: {name} hit the {args.max_pieces}-piece cap in {capped} games (its scores are lower bounds)")

    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, f"compare_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(path, 'w') as f:
        json.dump(report, f, indent=1)
    print(f"\nSaved {path}")


if __name__ == '__main__':
    main()
