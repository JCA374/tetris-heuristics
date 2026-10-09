#!/usr/bin/env python3
"""
Analyze recorded games (experiments/record_games.py) to look for new features.

Computes candidate board features on every logged board and asks:
  1. What do boards look like when the AI dies?          (gallery, heatmaps)
  2. Which features drift away from normal before death? (trajectories)
  3. Which features warn of an upcoming death?           (AUC on mid-game snapshots)
  4. Which add information the current features miss?    (partial correlation)
  5. What kills it: pieces, droughts, hole-making moves.

Writes PNGs, summary.json and report.html to results/game_analysis/<model>/.

Example:
    python experiments/analyze_games.py runs/games/baseline_single_v1.jsonl.gz
"""

import argparse
import gzip
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, LinearSegmentedColormap

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tetris.game import TetrisGame
from tetris.pieces import PIECES_BY_NAME

# --- style (reference palette from the dataviz skill) ---------------------------
SURFACE = '#fcfcfb'
INK = '#0b0b0b'
INK_2 = '#52514e'
GRID = '#e4e3df'
SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948']
PIECE_ORDER = 'IOTSZJL'
PIECE_COLOR = dict(zip(PIECE_ORDER, SERIES))
BLUES = LinearSegmentedColormap.from_list('blues', ['#fcfcfb', '#cde2fb', '#86b6ef', '#3987e5',
                                                    '#1c5cab', '#0d366b'])

plt.rcParams.update({
    'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE, 'savefig.facecolor': SURFACE,
    'axes.edgecolor': GRID, 'axes.labelcolor': INK_2, 'xtick.color': INK_2, 'ytick.color': INK_2,
    'text.color': INK, 'axes.titlecolor': INK, 'axes.titlesize': 11, 'axes.titleweight': 'bold',
    'axes.labelsize': 9, 'xtick.labelsize': 8, 'ytick.labelsize': 8, 'legend.fontsize': 8,
    'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6, 'axes.spines.top': False,
    'axes.spines.right': False, 'lines.linewidth': 2, 'font.family': 'DejaVu Sans',
})

# Model feature -> board feature computed here (lines is per-move, not a board property)
MODEL_FEATURE = {'height': 'agg_height', 'holes': 'holes', 'bumpiness': 'bumpiness',
                 'wells': 'cum_wells', 'hole_depth': 'hole_depth', 'sz_fit': 'sz_fit'}
# landing_height / eroded_cells describe the move, not the board, so they cannot be computed from recorded boards
ALL_FEATURES = ['agg_height', 'holes', 'bumpiness', 'max_height', 'height_spread', 'rows_with_holes',
                'hole_depth', 'max_col_holes', 'row_transitions', 'col_transitions', 'cum_wells',
                'max_well', 'deep_wells', 'near_full_rows', 'surface_rough2', 'piece_fit', 'sz_fit']
# Set in main() from the model's weights: features it uses vs. candidates
CURRENT, CANDIDATES = [], []
LABELS = {
    'agg_height': 'aggregate height', 'holes': 'holes', 'bumpiness': 'bumpiness',
    'max_height': 'max height', 'height_spread': 'max - min height',
    'rows_with_holes': 'rows with holes', 'hole_depth': 'hole depth (cells above holes)',
    'max_col_holes': 'most holes in one column', 'row_transitions': 'row transitions',
    'col_transitions': 'column transitions', 'cum_wells': 'cumulative wells',
    'max_well': 'deepest well', 'deep_wells': 'wells deeper than 2',
    'near_full_rows': 'rows with 8-9 cells', 'surface_rough2': 'sum of squared height steps',
    'piece_fit': 'piece types that fit without a hole', 'sz_fit': 'S/Z that fit without a hole',
}


def _bottom_profiles():
    """Per piece: list of bottom profiles, one per rotation. Profile[dc] = how far column dc's
    lowest cell sits above the piece's lowest cell; the piece lands flush (no new hole) at
    column c iff h[c + dc] - profile[dc] is the same for every dc."""
    from tetris.pieces import ALL_PIECES
    out = {}
    for piece in ALL_PIECES:
        profiles = []
        for coords in piece.rotations:
            width = max(c for _, c in coords) + 1
            low = [max(r for r, c in coords if c == dc) for dc in range(width)]
            profiles.append([max(low) - l for l in low])
        out[piece.name] = profiles
    return out


BOTTOM_PROFILES = _bottom_profiles()


def piece_fits(h):
    """(N, C) heights -> {piece: (N,) bool}: some rotation/column lands without creating a hole."""
    N, C = h.shape
    fits = {}
    for name, profiles in BOTTOM_PROFILES.items():
        ok = np.zeros(N, dtype=bool)
        for prof in profiles:
            w = len(prof)
            for c in range(C - w + 1):
                base = h[:, c] - prof[0]
                same = np.ones(N, dtype=bool)
                for dc in range(1, w):
                    same &= (h[:, c + dc] - prof[dc]) == base
                ok |= same
        fits[name] = ok
    return fits


# --- loading ------------------------------------------------------------------------

def load(path):
    games = []
    with gzip.open(path, 'rt') as f:
        header = json.loads(f.readline())['header']
        for line in f:
            games.append(json.loads(line))
    return header, games


def to_array(boards):
    """List of boards (list of row strings) -> (N, 20, 10) bool array, row 0 = top."""
    return np.array([[[c != '.' for c in row] for row in b] for b in boards], dtype=bool)


# --- features (vectorized over N boards) ------------------------------------------------

def features(F):
    N, R, C = F.shape
    rows = np.arange(R)[None, :, None]
    any_col = F.any(axis=1)
    top = np.where(any_col, F.argmax(axis=1), R)            # first filled row per column
    h = R - top                                              # (N, C)
    below_top = rows > top[:, None, :]
    hole = below_top & ~F
    above = np.cumsum(F, axis=1) - F                        # filled cells above each cell

    out = {}
    out['agg_height'] = h.sum(1)
    out['holes'] = hole.sum((1, 2))
    steps = np.diff(h, axis=1)
    out['bumpiness'] = np.abs(steps).sum(1)
    out['surface_rough2'] = (steps ** 2).sum(1)
    out['max_height'] = h.max(1)
    out['height_spread'] = h.max(1) - h.min(1)
    out['rows_with_holes'] = hole.any(2).sum(1)
    out['hole_depth'] = (above * hole).sum((1, 2))
    out['max_col_holes'] = hole.sum(1).max(1)

    wall = np.ones((N, R, 1), dtype=bool)
    padded = np.concatenate([wall, F, wall], axis=2)
    out['row_transitions'] = (padded[:, :, 1:] != padded[:, :, :-1]).sum((1, 2))
    floor = np.ones((N, 1, C), dtype=bool)
    colpad = np.concatenate([F, floor], axis=1)
    out['col_transitions'] = (colpad[:, 1:, :] != colpad[:, :-1, :]).sum((1, 2))

    big = np.full((N, 1), 10 ** 6)
    hp = np.concatenate([big, h, big], axis=1)
    well = np.clip(np.minimum(hp[:, :-2], hp[:, 2:]) - h, 0, None)   # depth per column
    out['cum_wells'] = (well * (well + 1) // 2).sum(1)
    out['max_well'] = well.max(1)
    out['deep_wells'] = (well > 2).sum(1)

    fill = F.sum(2)
    out['near_full_rows'] = ((fill >= 8) & (fill <= 9)).sum(1)
    fits = piece_fits(h)
    out['piece_fit'] = sum(fits.values()).astype(int)
    out['sz_fit'] = fits['S'].astype(int) + fits['Z'].astype(int)
    return {k: v.astype(float) for k, v in out.items()}


# --- stats helpers ----------------------------------------------------------------

def auc(scores, labels):
    """Mann-Whitney AUC: probability a positive outranks a negative (ties = 0.5)."""
    order = np.argsort(scores, kind='mergesort')
    s = scores[order]
    ranks = np.empty(len(s))
    i = 0
    while i < len(s):                      # average ranks for ties
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    pos = labels.astype(bool)
    n_pos, n_neg = pos.sum(), (~pos).sum()
    return (ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def residualize(y, X):
    X1 = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    return y - X1 @ beta


def corr(a, b):
    a = a - a.mean()
    b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d else 0.0


# --- drawing ------------------------------------------------------------------------

UNKNOWN_CELL = '#b4b2ac'   # 'X': cells from the C core, which doesn't track piece letters
BOARD_CMAP = ListedColormap([SURFACE] + [PIECE_COLOR[p] for p in PIECE_ORDER] + [UNKNOWN_CELL])


def board_codes(board):
    return np.array([[0 if c == '.' else PIECE_ORDER.index(c) + 1 if c in PIECE_ORDER else 8 for c in row]
                     for row in board])


def draw_board(ax, board, title=None):
    ax.imshow(board_codes(board), cmap=BOARD_CMAP, vmin=0, vmax=8, interpolation='nearest')
    ax.set_xticks(np.arange(-0.5, 10, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 20, 1), minor=True)
    ax.grid(which='minor', color='#ffffff', linewidth=0.6)
    ax.grid(which='major', visible=False)
    ax.tick_params(which='both', length=0, labelbottom=False, labelleft=False)
    for s in ax.spines.values():
        s.set_visible(True)
        s.set_color(INK_2)
    if title:
        ax.set_title(title, fontsize=8, fontweight='normal', color=INK_2)


def save(fig, out_dir, name):
    path = os.path.join(out_dir, name)
    fig.savefig(path, dpi=130, bbox_inches='tight')
    plt.close(fig)
    return name


# --- analysis -----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('games', help='runs/games/<model>.jsonl.gz')
    parser.add_argument('--out-dir', help='default: results/game_analysis/<model>')
    parser.add_argument('--warning', type=int, default=250,
                        help='"dies soon" = within this many pieces (for AUC)')
    parser.add_argument('--normal-gap', type=int, default=1000,
                        help='snapshots at least this many pieces before death define "normal" levels')
    args = parser.parse_args()

    header, games = load(args.games)
    policy = header['policy']
    default_weights = policy['weights'][policy['rules'][-1]['name']]
    CURRENT[:] = [MODEL_FEATURE[f] for f in MODEL_FEATURE if default_weights.get(f, 0)]
    CANDIDATES[:] = [k for k in ALL_FEATURES if k not in CURRENT]
    model = header['model']
    out_dir = args.out_dir or os.path.join('results', 'game_analysis', model)
    os.makedirs(out_dir, exist_ok=True)
    dead = [g for g in games if g['record']['game_over']]
    lines = np.array([g['lines'] for g in games])
    print(f'{model}: {len(games)} games, {len(dead)} ended in game over, '
          f'mean {lines.mean():.0f} lines, median {np.median(lines):.0f}')

    figures = []
    summary = {'model': model, 'games': len(games), 'game_overs': len(dead),
               'lines_mean': float(lines.mean()), 'lines_median': float(np.median(lines))}

    # 1. Gallery of final boards -----------------------------------------------------
    rng = np.random.default_rng(0)
    pick = sorted(rng.choice(len(dead), size=min(24, len(dead)), replace=False),
                  key=lambda i: dead[i]['lines'])
    fig, axes = plt.subplots(3, 8, figsize=(13, 9.5))
    for ax, i in zip(axes.flat, pick):
        g = dead[i]
        draw_board(ax, g['record']['final_board'],
                   f"{g['lines']} lines · killer {g['record']['killer_piece']}")
    for ax in axes.flat[len(pick):]:
        ax.axis('off')
    handles = [plt.Rectangle((0, 0), 1, 1, color=PIECE_COLOR[p]) for p in PIECE_ORDER]
    fig.legend(handles, list(PIECE_ORDER), loc='lower center', ncol=7, frameon=False)
    fig.suptitle(f'Final boards: 24 random games of {model} (sorted by lines)', fontweight='bold')
    figures.append(('Final boards', save(fig, out_dir, '1_final_boards.png'),
                    'The board at the moment no piece placement was possible. Colors show which piece filled each cell.'))

    # Features for all boards ----------------------------------------------------------
    snap_rows, snap_remaining, snap_game = [], [], []
    for gi, g in enumerate(dead):
        end = g['pieces']
        for s in g['record']['snapshots']:
            snap_rows.append(s['board'])
            snap_remaining.append(end - s['n'])
            snap_game.append(gi)
    snap = features(to_array(snap_rows))
    remaining = np.array(snap_remaining, dtype=float)
    # "Normal" = boards well before death (recordings of long games add dense snapshots near the end)
    normal = remaining >= args.normal_gap
    if normal.sum() < 50:
        normal = np.ones_like(normal)
    snap_n = {k: v[normal] for k, v in snap.items()}
    normal_rows = [b for b, ok in zip(snap_rows, normal) if ok]
    final = features(to_array([g['record']['final_board'] for g in dead]))

    keep_last = max(len(g['record']['recent']) for g in dead)
    traj = {k: np.full((len(dead), keep_last), np.nan) for k in CURRENT + CANDIDATES}
    for gi, g in enumerate(dead):
        rec = g['record']['recent']
        f = features(to_array([r['board'] for r in rec]))
        offset = keep_last - len(rec)
        for k in traj:
            traj[k][gi, offset:] = f[k]

    # 2. Heatmaps: where are holes / filled cells at death vs mid-game -------------------
    def hole_map(boards):
        F = to_array(boards)
        top = np.where(F.any(1), F.argmax(1), 20)
        hole = (np.arange(20)[None, :, None] > top[:, None, :]) & ~F
        return hole.mean(0), F.mean(0)

    mid_hole, mid_fill = hole_map(normal_rows)
    end_hole, end_fill = hole_map([g['record']['final_board'] for g in dead])
    fig, axes = plt.subplots(1, 4, figsize=(11, 5.6))
    for ax, data, title in zip(axes, [mid_fill, end_fill, mid_hole, end_hole],
                               ['filled · mid-game', 'filled · at death', 'holes · mid-game', 'holes · at death']):
        im = ax.imshow(data, cmap=BLUES, vmin=0, vmax=1, interpolation='nearest')
        ax.set_title(title, fontsize=9)
        ax.grid(False)
        ax.set_xticks(range(10))
        ax.set_yticks([0, 5, 10, 15, 19])
        ax.set_yticklabels(['top', '5', '10', '15', 'floor'])
    cbar = fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02)
    cbar.set_label('share of boards')
    fig.suptitle('Where cells and holes are (column x row)', fontweight='bold')
    figures.append(('Cell and hole heatmaps', save(fig, out_dir, '2_heatmaps.png'),
                    'Share of boards with a filled cell / hole at each position, mid-game snapshots vs final boards.'))

    # 3. Trajectories before death, small multiples ----------------------------------------
    show = CURRENT + CANDIDATES
    cols = 5
    rows_n = int(np.ceil(len(show) / cols))
    fig, axes = plt.subplots(rows_n, cols, figsize=(15, 2.7 * rows_n), sharex=True)
    x = np.arange(-keep_last + 1, 1)
    for ax, k in zip(axes.flat, show):
        med = np.nanmedian(traj[k], 0)
        lo, hi = np.nanpercentile(traj[k], 25, 0), np.nanpercentile(traj[k], 75, 0)
        color = SERIES[0] if k in CURRENT else SERIES[1]
        ax.fill_between(x, lo, hi, color=color, alpha=0.18, linewidth=0)
        ax.plot(x, med, color=color)
        typical = np.median(snap_n[k])
        ax.axhline(typical, color=INK_2, linestyle=(0, (3, 3)), linewidth=1)
        ax.set_title(LABELS[k] + (' (current)' if k in CURRENT else ''), fontsize=9)
    for ax in axes.flat[len(show):]:
        ax.axis('off')
    for ax in axes[-1]:
        ax.set_xlabel('pieces before game over')
    fig.suptitle(f'The last {keep_last} pieces: median (line) and middle 50% (band). Dashed = typical level far from death',
                 fontweight='bold')
    fig.tight_layout()
    figures.append(('Run-up to death', save(fig, out_dir, '3_trajectories.png'),
                    f'How each feature evolves over the last {keep_last} placements. Blue = features the model already uses, orange = candidates.'))

    # Early warning: at which point does each feature leave its normal range?
    departure = {}
    for k in show:
        p90 = np.percentile(snap_n[k], 90)
        med = np.nanmedian(traj[k], 0)
        above = np.where(med > p90)[0]
        departure[k] = int(x[above[0]]) if len(above) else None
    summary['departure_from_normal_p90'] = departure

    # 4. Warning power (AUC) and added information (partial correlation) --------------------
    soon = remaining <= args.warning
    y = np.log1p(remaining)
    X_cur = np.column_stack([snap[k] for k in CURRENT])
    model_eval = -sum(default_weights.get(f, 0) * snap[k] for f, k in MODEL_FEATURE.items())
    res_y = residualize(y, X_cur)
    stats = {}
    for k in show:
        a = auc(snap[k], soon)
        pc = corr(residualize(snap[k], X_cur), res_y) if k not in CURRENT else None
        stats[k] = {'auc': float(a), 'partial_corr': pc, 'spearman_like': corr(
            np.argsort(np.argsort(snap[k])).astype(float), np.argsort(np.argsort(y)).astype(float))}
    model_auc = float(auc(model_eval, soon))
    summary['n_snapshots'] = int(len(remaining))
    summary['n_soon'] = int(soon.sum())
    summary['model_eval_auc'] = model_auc
    summary['feature_stats'] = stats

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    order = sorted(show, key=lambda k: stats[k]['auc'])
    ax1.barh([LABELS[k] for k in order], [stats[k]['auc'] - 0.5 for k in order], left=0.5,
             color=[SERIES[0] if k in CURRENT else SERIES[1] for k in order], height=0.6)
    ax1.axvline(model_auc, color=INK, linestyle=(0, (3, 3)), linewidth=1.2)
    ax1.text(model_auc, len(order) - 0.4, f" model's own score {model_auc:.2f}", fontsize=8, color=INK, va='bottom')
    ax1.set_xlim(0.45, 1.0)
    ax1.set_xlabel(f'AUC: does a high value mean "dies within {args.warning} pieces"?  (0.5 = no signal)')
    ax1.set_title('Warning power on mid-game boards')
    ax1.grid(axis='y', visible=False)
    for i, k in enumerate(order):
        ax1.text(stats[k]['auc'] + 0.005, i, f"{stats[k]['auc']:.2f}", va='center', fontsize=8, color=INK_2)

    cand = sorted(CANDIDATES, key=lambda k: abs(stats[k]['partial_corr']))
    vals = [-stats[k]['partial_corr'] for k in cand]   # sign: positive = higher value -> sooner death
    ax2.barh([LABELS[k] for k in cand], vals, color=SERIES[1], height=0.6)
    ax2.axvline(0, color=INK_2, linewidth=0.8)
    ax2.set_xlabel('partial correlation with "dies sooner", after removing what\n' + ' + '.join(LABELS[k] for k in CURRENT) + ' already explain')
    ax2.set_title('New information beyond current features')
    ax2.grid(axis='y', visible=False)
    for i, v in enumerate(vals):
        ax2.text(v + (0.004 if v >= 0 else -0.004), i, f'{v:+.2f}', va='center',
                 ha='left' if v >= 0 else 'right', fontsize=8, color=INK_2)
    lim = max(abs(v) for v in vals) * 1.35
    ax2.set_xlim(-lim, lim)
    fig.tight_layout()
    figures.append(('Which features predict death', save(fig, out_dir, '4_feature_signal.png'),
                    f'Computed on {len(remaining)} mid-game snapshots ({int(soon.sum())} within {args.warning} pieces of death). '
                    'Left: each feature alone. Right: what a candidate adds once the current features are accounted for.'))

    # 5. What kills it ---------------------------------------------------------------------
    killers = [g['record']['killer_piece'] for g in dead]
    i_drought = np.array([g['record']['pieces_since_seen']['I'] for g in dead])
    hole_moves = {p: [0, 0] for p in PIECE_ORDER}      # [moves, moves that added holes]
    clear_moves = {p: [0, 0] for p in PIECE_ORDER}
    for g in dead:
        rec = g['record']['recent']
        f = features(to_array([r['board'] for r in rec]))['holes']
        for j in range(1, len(rec)):
            p = rec[j]['piece']
            hole_moves[p][0] += 1
            hole_moves[p][1] += int(f[j] > f[j - 1] and rec[j]['cleared'] == 0)
            clear_moves[p][0] += 1
            clear_moves[p][1] += int(rec[j]['cleared'] > 0)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    counts = [killers.count(p) / len(killers) for p in PIECE_ORDER]
    axes[0].bar(list(PIECE_ORDER), counts, color=[PIECE_COLOR[p] for p in PIECE_ORDER], width=0.6)
    axes[0].axhline(1 / 7, color=INK_2, linestyle=(0, (3, 3)), linewidth=1)
    axes[0].text(6.4, 1 / 7, ' 1/7', fontsize=8, color=INK_2, va='bottom', ha='right')
    axes[0].set_title('Piece that could not be placed')
    axes[0].set_ylabel('share of game overs')
    axes[0].grid(axis='x', visible=False)

    bins = np.arange(0, max(30, i_drought.max() + 2))
    axes[1].hist(i_drought, bins=bins, color=SERIES[0], rwidth=0.85)
    expected = len(dead) * (1 / 7) * (6 / 7) ** bins[:-1]
    axes[1].plot(bins[:-1] + 0.5, expected, color=INK, linewidth=1.2, label='expected if unrelated')
    axes[1].set_title('Pieces since the last I-piece, at death')
    axes[1].set_xlabel('pieces')
    axes[1].legend(frameon=False)
    axes[1].grid(axis='x', visible=False)

    rates = [hole_moves[p][1] / max(hole_moves[p][0], 1) for p in PIECE_ORDER]
    axes[2].bar(list(PIECE_ORDER), rates, color=[PIECE_COLOR[p] for p in PIECE_ORDER], width=0.6)
    axes[2].set_title(f'Share of moves that created holes (last {keep_last} pieces)')
    axes[2].grid(axis='x', visible=False)
    fig.tight_layout()
    figures.append(('What kills it', save(fig, out_dir, '5_death_causes.png'),
                    'Left: the killer piece vs. the 1/7 you would expect by chance. Middle: I-piece drought at death vs. chance. '
                    'Right: how often each piece type adds a hole without clearing a line, in the run-up to death.'))

    # 6. Onset: the last healthy board before the spiral --------------------------------
    healthy_holes = np.percentile(snap_n['holes'], 75)
    healthy_height = np.percentile(snap_n['agg_height'], 75)
    onsets = []            # (game index, index in recent of last healthy board)
    onset_distance = []
    for gi, g in enumerate(dead):
        rec = g['record']['recent']
        f = features(to_array([r['board'] for r in rec]))
        ok = np.where((f['holes'] <= healthy_holes) & (f['agg_height'] <= healthy_height))[0]
        ok = ok[ok < len(rec) - 1]
        if len(ok):
            j = int(ok[-1])
            onsets.append((gi, j))
            onset_distance.append(len(rec) - 1 - j)
    onset_distance = np.array(onset_distance)
    never = len(dead) - len(onsets)

    onset_piece = [dead[gi]['record']['recent'][j + 1]['piece'] for gi, j in onsets]
    onset_hole = []
    for gi, j in onsets:
        rec = dead[gi]['record']['recent']
        f = features(to_array([rec[j]['board'], rec[j + 1]['board']]))['holes']
        onset_hole.append(f[1] > f[0])

    fig = plt.figure(figsize=(14, 10.5))
    grid = fig.add_gridspec(4, 6, height_ratios=[1, 2.2, 2.2, 2.2])
    ax = fig.add_subplot(grid[0, :3])
    ax.hist(onset_distance, bins=30, color=SERIES[0], rwidth=0.85)
    ax.set_title('Pieces from last healthy board to game over')
    ax.set_xlabel(f'pieces ({never} games had no healthy board in the last {keep_last})')
    ax.grid(axis='x', visible=False)
    ax = fig.add_subplot(grid[0, 3:])
    share = [onset_piece.count(p) / max(len(onset_piece), 1) for p in PIECE_ORDER]
    ax.bar(list(PIECE_ORDER), share, color=[PIECE_COLOR[p] for p in PIECE_ORDER], width=0.6)
    ax.axhline(1 / 7, color=INK_2, linestyle=(0, (3, 3)), linewidth=1)
    ax.set_title(f'Piece placed right after the last healthy board ({np.mean(onset_hole):.0%} made a hole)')
    ax.grid(axis='x', visible=False)

    sample = [onsets[i] for i in rng.choice(len(onsets), size=min(6, len(onsets)), replace=False)]
    for col, (gi, j) in enumerate(sample):
        rec = dead[gi]['record']['recent']
        for row, step in enumerate((0, 10, 30)):
            k = min(j + step, len(rec) - 1)
            ax = fig.add_subplot(grid[row + 1, col])
            draw_board(ax, rec[k]['board'], f'+{k - j} pieces' if step else 'last healthy')
            if step == 0:
                nxt = rec[j + 1]
                game = TetrisGame()
                game.board = [[0 if c == '.' else c for c in r] for r in rec[j]['board']]
                piece = PIECES_BY_NAME[nxt['piece']]
                drop = game.get_drop_row(piece, nxt['rotation'], nxt['col'])
                for r, c in piece.get_rotation(nxt['rotation']):
                    ax.add_patch(plt.Rectangle((c + nxt['col'] - 0.5, r + drop - 0.5), 1, 1, fill=False,
                                               edgecolor=INK, linewidth=1.8))
                ax.set_title(f"last healthy · next: {nxt['piece']}", fontsize=8, color=INK_2)
    fig.suptitle('How the spiral starts: last healthy board (outline = next placement), then +10 and +30 pieces',
                 fontweight='bold')
    fig.tight_layout()
    figures.append(('How the spiral starts', save(fig, out_dir, '6_onset.png'),
                    f'"Healthy" = holes <= {healthy_holes:.0f} and aggregate height <= {healthy_height:.0f} '
                    '(75th percentile of boards far from death). Each column follows one game from its last healthy board.'))
    summary['onset'] = {
        'healthy_holes_max': float(healthy_holes), 'healthy_height_max': float(healthy_height),
        'games_with_onset': len(onsets), 'games_without_healthy_board': never,
        'distance_median': float(np.median(onset_distance)) if len(onset_distance) else None,
        'piece_share': dict(zip(PIECE_ORDER, share)), 'onset_move_made_hole': float(np.mean(onset_hole)),
    }

    # 7. Regime use (regime models only) ----------------------------------------------------
    rules = policy['rules']
    if len(rules) > 1:
        names = [r['name'] for r in rules]
        desc = {r['name']: (f"{r['name']} ({r['stat']} {r['op']} {r['threshold']})" if 'stat' in r
                            else f"{r['name']} (otherwise)") for r in rules}
        reg_share = np.full((len(names), len(dead), keep_last), np.nan)
        for gi, g in enumerate(dead):
            rec = g['record']['recent']
            offset = keep_last - len(rec)
            for ni, name in enumerate(names):
                reg_share[ni, gi, offset:] = [r['regime'] == name for r in rec]
        totals = {n: sum(g['regime_counts'].get(n, 0) for g in games) for n in names}
        all_moves = max(sum(totals.values()), 1)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.2), gridspec_kw={'width_ratios': [1, 2]})
        whole = [totals[n] / all_moves for n in names]
        last = [np.nanmean(reg_share[ni]) for ni in range(len(names))]
        xs = np.arange(len(names))
        ax1.bar(xs - 0.18, whole, width=0.34, color=SERIES[0], label='whole games')
        ax1.bar(xs + 0.18, last, width=0.34, color=SERIES[1], label=f'last {keep_last} pieces')
        for xi, (a, b) in enumerate(zip(whole, last)):
            ax1.text(xi - 0.18, a, f'{a:.0%}', ha='center', va='bottom', fontsize=8, color=INK_2)
            ax1.text(xi + 0.18, b, f'{b:.0%}', ha='center', va='bottom', fontsize=8, color=INK_2)
        ax1.set_xticks(xs)
        ax1.set_xticklabels(names)
        ax1.set_ylabel('share of moves')
        ax1.set_title('How often each regime is active')
        ax1.legend(frameon=False)
        ax1.grid(axis='x', visible=False)
        for ni, name in enumerate(names):
            ax2.plot(x, np.nanmean(reg_share[ni], 0), color=SERIES[ni], label=desc[name])
        ax2.set_ylim(0, 1)
        ax2.set_xlabel('pieces before game over')
        ax2.set_ylabel('share of games in this regime')
        ax2.set_title('Regime in the run-up to death')
        ax2.legend(frameon=False, loc='center left')
        fig.tight_layout()
        figures.append(('Regime use', save(fig, out_dir, '7_regimes.png'),
                        'Left: share of moves made in each regime, over whole games and in the run-up to death. '
                        'Right: which regime is active at each step before game over.'))
        summary['regime_share_whole'] = dict(zip(names, map(float, whole)))
        summary['regime_share_last'] = dict(zip(names, map(float, last)))

    summary['killer_share'] = dict(zip(PIECE_ORDER, counts))
    summary['i_drought_mean'] = float(i_drought.mean())
    summary['hole_rate_by_piece'] = dict(zip(PIECE_ORDER, rates))
    summary['final_board_medians'] = {k: float(np.median(final[k])) for k in show}
    summary['midgame_medians'] = {k: float(np.median(snap_n[k])) for k in show}

    with open(os.path.join(out_dir, 'summary.json'), 'w') as f:
        json.dump(summary, f, indent=1)

    # report.html ------------------------------------------------------------------
    def table_row(k):
        pc = stats[k]['partial_corr']
        tag = ' <span class=cur>current</span>' if k in CURRENT else ''
        return (f"<tr><td>{LABELS[k]}{tag}</td>"
                f"<td>{summary['midgame_medians'][k]:.0f}</td><td>{summary['final_board_medians'][k]:.0f}</td>"
                f"<td>{stats[k]['auc']:.2f}</td><td>{'' if pc is None else f'{-pc:+.2f}'}</td>"
                f"<td>{'' if departure[k] is None else departure[k]}</td></tr>")

    rows = ''.join(table_row(k) for k in sorted(show, key=lambda k: -stats[k]['auc']))
    sections = ''.join(f'<section><h2>{t}</h2><p>{d}</p><img src="{img}" alt="{t}"></section>'
                       for t, img, d in figures)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Game analysis: {model}</title>
<style>body{{font-family:system-ui,sans-serif;background:{SURFACE};color:{INK};max-width:1200px;margin:24px auto;padding:0 16px}}
h1{{margin-bottom:4px}} .sub{{color:{INK_2}}} img{{max-width:100%;border:1px solid {GRID};border-radius:6px}}
table{{border-collapse:collapse;font-size:14px;margin:12px 0}} td,th{{padding:4px 10px;border-bottom:1px solid {GRID};text-align:right}}
td:first-child,th:first-child{{text-align:left}} .cur{{font-size:11px;color:#fff;background:{SERIES[0]};border-radius:4px;padding:1px 5px}}
section{{margin:28px 0}}</style></head><body>
<h1>Game analysis: {model}</h1>
<p class="sub">{len(games)} games ({len(dead)} game overs), mean {lines.mean():.0f} lines, median {np.median(lines):.0f}.
{len(remaining)} mid-game snapshots; "dies soon" = within {args.warning} pieces.</p>
<table><tr><th>feature</th><th>median mid-game</th><th>median at death</th><th>AUC (warning)</th>
<th>added info (partial corr.)</th><th>leaves normal range at</th></tr>{rows}</table>
<p class="sub">AUC of the model's own board score: {model_auc:.2f}. "Leaves normal range" = the piece (before death) where the median first exceeds the 90th percentile of boards far from death. "Mid-game" = snapshots at least {args.normal_gap} pieces before death; current features: {', '.join(LABELS[k] for k in CURRENT)}.</p>
{sections}</body></html>"""
    with open(os.path.join(out_dir, 'report.html'), 'w') as f:
        f.write(html)
    print(f'Wrote {out_dir}/report.html')


if __name__ == '__main__':
    main()
