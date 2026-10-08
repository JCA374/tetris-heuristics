#!/usr/bin/env python3
"""
Live view of running (or finished) GA trainings.

Reads runs/<run>/checkpoint.json, which train.py rewrites after every generation,
and redraws a matplotlib window. Watches the newest run of each model type by
default, so single and regime trainings appear side by side.

Examples:
    python training/watch.py                       # newest run per model type
    python training/watch.py runs/20261008_140426_regime
    python training/watch.py --text                # terminal table instead of a window
"""

import argparse
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tetris.features import FEATURES

COLORS = {'single': '#1f77b4', 'regime': '#d62728'}
HATCHES = {'normal': '', 'danger': '///', 'repair': '...'}


def latest_runs():
    runs = {}
    for path in sorted(glob.glob('runs/*/checkpoint.json')):
        run_dir = os.path.dirname(path)
        model = run_dir.rsplit('_', 1)[-1]
        runs[model] = run_dir  # sorted by timestamp, so the newest wins
    return list(runs.values())


def load(run_dir):
    try:
        with open(os.path.join(run_dir, 'checkpoint.json')) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None  # missing or mid-write; try again next refresh


def leader(h):
    return h['leader_genome'] or h['best_genome']


def print_table(runs):
    for run_dir in runs:
        data = load(run_dir)
        if not data or not data['history']:
            print(f'{run_dir}: waiting for first generation...')
            continue
        h = data['history'][-1]
        lead = f"{h['leader_mean']:.0f} ({h['leader_games']} games)" if h['leader_mean'] else 'n/a'
        print(f"{run_dir}  gen {h['generation']}: leader {lead}  best {h['best']:.0f}  mean {h['mean']:.0f}")
        g = leader(h)
        for k in sorted(g):
            if k.endswith('.threshold'):
                print(f'    {k} = {g[k]}')


def plot_loop(runs, interval):
    import matplotlib.pyplot as plt

    plt.ion()
    fig = plt.figure(figsize=(13, 8))
    fig.canvas.manager.set_window_title('Tetris GA - live')
    grid = fig.add_gridspec(2, 2)
    ax_fit = fig.add_subplot(grid[0, :])
    ax_thr = fig.add_subplot(grid[1, 0])
    ax_w = fig.add_subplot(grid[1, 1])

    while plt.fignum_exists(fig.number):
        ax_fit.clear(); ax_thr.clear(); ax_w.clear()
        bars = []
        for run_dir in runs:
            data = load(run_dir)
            if not data or not data['history']:
                continue
            model = data['template']
            color = COLORS.get(model)
            hist = data['history']
            gens = [h['generation'] for h in hist]
            lm = [h['leader_mean'] for h in hist]
            ax_fit.plot(gens, lm, color=color, linewidth=2.5, label=f'{model}: leader (multi-game mean)')
            ax_fit.plot(gens, [h['mean'] for h in hist], color=color, linestyle='--', alpha=0.6,
                        label=f'{model}: population mean')
            ax_fit.scatter(gens, [h['best'] for h in hist], color=color, s=10, alpha=0.4)

            thresholds = sorted(k for k in leader(hist[-1]) if k.endswith('.threshold'))
            for name, style in zip(thresholds, ('-', ':')):
                ax_thr.step(gens, [leader(h)[name] for h in hist], where='mid', color=color,
                            linestyle=style, linewidth=2, label=name.replace('.threshold', ''))

            g = leader(hist[-1])
            regimes = sorted({k.split('.')[0] for k in g if not k.endswith('.threshold')})
            for r in regimes:
                bars.append((f'{model} {r}' if model != 'single' else 'single', [g.get(f'{r}.{f}', 0.0) for f in FEATURES], color, HATCHES.get(r, '')))

        ax_fit.set_title('Fitness (dots = best individual of each generation, noisy)')
        ax_fit.set_xlabel('generation'); ax_fit.set_ylabel('lines cleared')
        ax_fit.grid(alpha=0.3)
        ax_fit.xaxis.get_major_locator().set_params(integer=True)
        ax_thr.xaxis.get_major_locator().set_params(integer=True)
        if ax_fit.lines:
            ax_fit.legend(loc='upper left', fontsize=8)

        ax_thr.set_title('Regime thresholds of the leader')
        ax_thr.set_xlabel('generation')
        ax_thr.grid(alpha=0.3)
        if ax_thr.lines:
            ax_thr.legend(fontsize=8)
            ax_thr.text(0.99, 0.02, 'repair: holes >=   danger: max height >=', transform=ax_thr.transAxes,
                        ha='right', fontsize=7, alpha=0.7)

        ax_w.set_title('Leader weights now (per regime)')
        if bars:
            n = len(bars)
            width = 0.8 / n
            for i, (label, values, color, hatch) in enumerate(bars):
                xs = [j + (i - (n - 1) / 2) * width for j in range(len(FEATURES))]
                ax_w.bar(xs, values, width, label=label, color=color, hatch=hatch, alpha=0.8,
                         edgecolor='black', linewidth=0.5)
            ax_w.set_xticks(range(len(FEATURES)))
            ax_w.set_xticklabels(FEATURES)
            ax_w.axhline(0, color='black', linewidth=0.8)
            ax_w.legend(fontsize=7)
        ax_w.grid(alpha=0.3, axis='y')

        fig.suptitle(f'Updated {time.strftime("%H:%M:%S")}  -  refreshes every {interval}s  -  close window to exit')
        fig.tight_layout()
        plt.pause(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('runs', nargs='*', help='run directories (default: newest per model type)')
    parser.add_argument('--interval', type=int, default=15, help='refresh seconds')
    parser.add_argument('--text', action='store_true', help='print a table instead of plotting')
    args = parser.parse_args()

    runs = args.runs or latest_runs()
    if not runs:
        sys.exit('No runs found in runs/')

    if args.text:
        try:
            while True:
                print(f'\033[H\033[J{time.strftime("%H:%M:%S")}')
                print_table(runs)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return
    plot_loop(runs, args.interval)


if __name__ == '__main__':
    main()
