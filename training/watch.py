#!/usr/bin/env python3
"""
Live view of running (or finished) GA trainings.

Reads runs/<run>/checkpoint.json, which train.py rewrites after every generation,
and redraws a matplotlib window. By default it shows the newest run of each model
type (re-checked on every refresh, so a run started later appears once its first
generation is saved). Panels: fitness, the leader's weights per generation, and
the leader's weights now.

Examples:
    python training/watch.py                       # newest run per model type
    python training/watch.py runs/20261009_201504_single_split
    python training/watch.py --text                # terminal table instead of a window
"""

import argparse
import glob
import json
import math
import os
import sys
import time
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tetris.features import FEATURES

PALETTE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948']
PLOTTED = [f for f in FEATURES if f != 'lines']        # lines is fixed at 0 in current models
FEATURE_COLORS = dict(zip(PLOTTED, PALETTE))
INK, MUTED, GRID = '#0b0b0b', '#52514e', '#e4e3df'


def latest_runs():
    runs = {}
    for path in sorted(glob.glob('runs/*/checkpoint.json')):
        run_dir = os.path.dirname(path)
        model = os.path.basename(run_dir).split('_', 2)[-1]   # e.g. single, single_cem_split
        runs[model] = run_dir  # sorted by timestamp, so the newest wins
    return list(runs.values())


def to_lines(data):
    """Fitness -> lines: splitting runs store ln(pieces per death)."""
    if str(data.get('fitness', 'lines')).startswith('est.'):
        return lambda v: None if v is None else math.exp(v) / 2.5
    return lambda v: v


def load(run_dir):
    try:
        with open(os.path.join(run_dir, 'checkpoint.json')) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None  # missing or mid-write; try again next refresh


def leader(h):
    return h['leader_genome'] or h['best_genome']


def weights(genome):
    """Feature -> weight of the default weight set (single models have only that one)."""
    prefix = 'default' if any(k.startswith('default.') for k in genome) else 'normal'
    return {f: genome.get(f'{prefix}.{f}', 0.0) for f in PLOTTED}


def print_table(runs):
    for run_dir in runs:
        data = load(run_dir)
        if not data or not data['history']:
            print(f'{run_dir}: waiting for first generation...')
            continue
        h = data['history'][-1]
        conv = to_lines(data)
        lead = f"{conv(h['leader_mean']):,.0f} ({h['leader_games']} games)" if h['leader_mean'] else 'n/a'
        print(f"{run_dir}  gen {h['generation']}: leader {lead}  best {conv(h['best']):,.0f}  mean {conv(h['mean']):,.0f}")
        for f, w in weights(leader(h)).items():
            print(f'    {f:15s} {w:+.3f}')


def style(ax, title):
    ax.set_title(title, loc='left', fontsize=15, color=INK, pad=10)
    ax.grid(color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(MUTED)


def plot_loop(find_runs, interval):
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    matplotlib.rcParams.update({
        'figure.raise_window': False,      # refreshes must not steal focus
        'font.size': 13, 'axes.labelsize': 13, 'xtick.labelsize': 12, 'ytick.labelsize': 12,
        'legend.fontsize': 13, 'legend.frameon': False, 'text.color': INK,
        'axes.labelcolor': MUTED, 'xtick.color': MUTED, 'ytick.color': MUTED,
        'figure.facecolor': '#fcfcfb', 'axes.facecolor': '#fcfcfb',
    })
    plt.ion()
    fig = plt.figure(figsize=(15, 10))
    fig.canvas.manager.set_window_title('Tetris GA - live')
    grid = fig.add_gridspec(2, 2, width_ratios=(1.4, 1))
    ax_fit = fig.add_subplot(grid[0, :])
    ax_hist = fig.add_subplot(grid[1, 0])
    ax_w = fig.add_subplot(grid[1, 1])

    from matplotlib.widgets import Button
    button_ax = fig.add_axes([0.87, 0.95, 0.11, 0.04])
    button = Button(button_ax, 'Refresh now')
    button.label.set_fontsize(13)
    button.on_clicked(lambda event: fig.canvas.stop_event_loop())   # ends the wait below early

    thousands = FuncFormatter(lambda v, _: f'{v / 1e6:.1f}M' if abs(v) >= 1e6 else f'{v / 1e3:.0f}k' if abs(v) >= 1e3 else f'{v:.0f}')
    shown = False
    while plt.fignum_exists(fig.number):
        runs = find_runs()
        ax_fit.clear(); ax_hist.clear(); ax_w.clear()
        fitness_label = 'lines cleared'
        latest = None
        for i, run_dir in enumerate(runs):
            data = load(run_dir)
            if not data or not data['history']:
                continue
            if data.get('fitness', 'lines') != 'lines':
                fitness_label = data['fitness']
            color = PALETTE[i % len(PALETTE)]
            name = os.path.basename(run_dir).split('_', 2)[-1]
            hist = data['history']
            gens = [h['generation'] for h in hist]
            conv = to_lines(data)
            ax_fit.plot(gens, [conv(h['leader_mean']) for h in hist], color=color, linewidth=2.5,
                        label=f'{name}: leader (mean over its games)')
            ax_fit.plot(gens, [conv(h['mean']) for h in hist], color=color, linestyle='--', linewidth=2,
                        alpha=0.7, label=f'{name}: population mean')
            ax_fit.scatter(gens, [conv(h['best']) for h in hist], color=color, s=28, alpha=0.45,
                           label=f'{name}: best of generation (noisy)')
            latest = (run_dir, gens, hist)

        style(ax_fit, 'Fitness')
        ax_fit.set_xlabel('generation'); ax_fit.set_ylabel(fitness_label)
        ax_fit.yaxis.set_major_formatter(thousands)
        ax_fit.xaxis.get_major_locator().set_params(integer=True)
        if ax_fit.lines:
            ax_fit.legend(loc='upper left')

        style(ax_hist, 'Leader weights per generation')
        style(ax_w, 'Leader weights now')
        if latest:
            run_dir, gens, hist = latest
            series = [weights(leader(h)) for h in hist]
            active = [f for f in PLOTTED if any(s[f] for s in series)]
            for f in active:
                ax_hist.plot(gens, [s[f] for s in series], color=FEATURE_COLORS[f], linewidth=2.5, label=f)
            ax_hist.axhline(0, color=MUTED, linewidth=1)
            ax_hist.set_yscale('symlog', linthresh=1)     # holes (~-8) would flatten the small weights
            lim = ax_hist.get_ylim()
            ax_hist.set_yticks([-10, -5, -2, -1, -0.5, 0, 0.5, 1, 2, 5])
            ax_hist.set_ylim(lim)                         # set_yticks would widen the view to every tick
            ax_hist.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:g}'))
            ax_hist.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
            ax_hist.set_xlabel('generation'); ax_hist.set_ylabel('weight (linear in -1..1, log outside)')
            ax_hist.xaxis.get_major_locator().set_params(integer=True)
            ax_hist.legend(loc='upper left', bbox_to_anchor=(1.0, 1.0))

            now = series[-1]
            ys = range(len(PLOTTED))
            ax_w.barh(ys, [now[f] for f in PLOTTED], color=[FEATURE_COLORS[f] for f in PLOTTED], height=0.7)
            ax_w.set_yticks(list(ys), PLOTTED, fontsize=13)
            ax_w.invert_yaxis()
            ax_w.axvline(0, color=MUTED, linewidth=1)
            ax_w.grid(axis='y', visible=False)
            lo = min(0.0, *now.values()); hi = max(0.0, *now.values())
            pad = 0.3 * (hi - lo or 1)
            ax_w.set_xlim(lo - pad, hi + pad)
            for y, f in zip(ys, PLOTTED):
                v = now[f]
                ax_w.text(v + (pad * 0.08 if v >= 0 else -pad * 0.08), y, f'{v:+.2f}' if v else '0',
                          va='center', ha='left' if v >= 0 else 'right', fontsize=12, color=INK)
            ax_w.set_xlabel('weight (score = sum of weight x feature)')

        names = '  |  '.join(os.path.basename(r) for r in runs)
        fig.suptitle(f'{names}\nUpdated {time.strftime("%H:%M:%S")}  -  refreshes every {interval}s (or click Refresh now)',
                     fontsize=13, x=0.02, ha='left', color=MUTED)
        with warnings.catch_warnings():   # the button's axes are outside the grid, which is fine
            warnings.simplefilter('ignore', UserWarning)
            fig.tight_layout(rect=(0, 0, 1, 0.96))
        if not shown:
            plt.show(block=False)
            shown = True
        fig.canvas.draw_idle()
        # Unlike plt.pause, this keeps the window responsive without re-showing/raising it
        fig.canvas.start_event_loop(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('runs', nargs='*', help='run directories (default: newest per model type)')
    parser.add_argument('--interval', type=int, default=300, help='refresh seconds')
    parser.add_argument('--text', action='store_true', help='print a table instead of plotting')
    args = parser.parse_args()

    # Without explicit runs, look again on every refresh so newly started runs appear
    find_runs = (lambda: args.runs) if args.runs else latest_runs
    if not find_runs():
        sys.exit('No runs found in runs/')

    if args.text:
        try:
            while True:
                print(f'\033[H\033[J{time.strftime("%H:%M:%S")}')
                print_table(find_runs())
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return
    plot_loop(find_runs, args.interval)


if __name__ == '__main__':
    main()
