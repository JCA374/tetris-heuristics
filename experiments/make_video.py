"""
Silent ~105 s explainer video: how the AI plays, how it scores moves, how the
genetic algorithm learns the weights (on real training-run data), how the
features were found, and the results.

Every frame is drawn with Pillow and piped into ffmpeg (libx264, no audio).
The gameplay is a real single_v8 game played by the Python engine; the GA scenes
read runs/<v7, v8 runs>/checkpoint.json (git-ignored; illustrative data if missing).

    python experiments/make_video.py                  # -> docs/video/tetris_explainer.mp4
    python experiments/make_video.py --preview        # contact sheet PNG, one frame per scene
"""

import argparse
import json
import math
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # optional dependency
    sys.exit('make_video.py needs Pillow: pip install pillow')

from tetris.features import compute_features
from tetris.game import TetrisGame
from tetris.play import PieceStream
from tetris.policy import Policy

W, H = 1920, 1080
BG = (26, 26, 25)
SURFACE2 = (37, 37, 35)
EMPTY = (44, 44, 42)
GRID = (56, 56, 53)
INK = (255, 255, 255)
INK2 = (195, 194, 183)
INK3 = (142, 141, 133)
S1, S2, S3, S4 = (57, 135, 229), (217, 89, 38), (25, 158, 112), (201, 133, 0)
S5, S7, S8 = (213, 81, 129), (144, 133, 233), (230, 103, 103)
GOOD, CRIT = (12, 163, 12), (208, 59, 59)
PIECE = {'I': (0, 200, 210), 'O': (225, 205, 0), 'T': (150, 60, 220), 'S': (40, 190, 70),
         'Z': (215, 50, 50), 'J': (50, 90, 225), 'L': (235, 145, 0)}

FONT_DIR = '/usr/share/fonts/truetype/dejavu'
_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
        try:
            _fonts[key] = ImageFont.truetype(os.path.join(FONT_DIR, name), size)
        except OSError:
            _fonts[key] = ImageFont.load_default(size)
    return _fonts[key]


# ---------------------------------------------------------------- helpers

def lerp(a, b, t):
    return a + (b - a) * t


def mix(c, t, bg=BG):
    """Colour c faded towards the background (t = 1: full colour)."""
    t = max(0.0, min(1.0, t))
    return tuple(int(lerp(b, x, t)) for x, b in zip(c, bg))


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def fade(i, n, start=0, inn=9, out=9):
    """Alpha for an element shown from frame `start` to the end of an n-frame scene."""
    if i < start:
        return 0.0
    return min(1.0, (i - start) / inn, (n - 1 - i) / out if out else 1.0)


def text(d, xy, s, size, color=INK, alpha=1.0, bold=False, anchor='la'):
    d.text(xy, s, font=font(size, bold), fill=mix(color, alpha), anchor=anchor)


def new_frame():
    img = Image.new('RGB', (W, H), BG)
    return img, ImageDraw.Draw(img)


def draw_board(d, board, x, y, cell, alpha=1.0, highlight=None, ghost=None, ghost_color=None):
    """board: rows of 0 / piece name. highlight: {(r, c): colour} drawn over cells."""
    rows, cols = len(board), len(board[0])
    d.rectangle([x - 6, y - 6, x + cols * cell + 6, y + rows * cell + 6], fill=mix(SURFACE2, alpha))
    for r in range(rows):
        for c in range(cols):
            v = board[r][c]
            color = PIECE.get(v, (105, 115, 135)) if v else EMPTY
            if highlight and (r, c) in highlight:
                color = highlight[(r, c)]
            x0, y0 = x + c * cell, y + r * cell
            d.rectangle([x0 + 1, y0 + 1, x0 + cell - 2, y0 + cell - 2], fill=mix(color, alpha))
    if ghost:
        for r, c in ghost:
            x0, y0 = x + c * cell, y + r * cell
            d.rectangle([x0 + 1, y0 + 1, x0 + cell - 2, y0 + cell - 2],
                        fill=mix(ghost_color, 0.55 * alpha), outline=mix(ghost_color, alpha), width=3)


def piece_cells(game, piece, rotation, col):
    row = game.get_drop_row(piece, rotation, col)
    return [(r + row, c + col) for r, c in piece.get_rotation(rotation)]


def fmt(v):
    if v >= 1e6:
        return f'{v / 1e6:g}M'
    if v >= 1e3:
        return f'{v / 1e3:.0f}k'
    return f'{v:,.0f}'


# ---------------------------------------------------------------- data

def load_policy():
    return Policy.load(os.path.join(ROOT, 'models', 'single_v8.json'))


WEIGHT_ROWS = [('holes', 'holes'), ('bumpiness', 'bumpiness'), ('wells', 'wells'),
               ('landing_height', 'landing height'), ('sz_fit', 'S/Z fit')]

RESULTS = [  # README Results table: mean lines per game on held-out seeds
    ('v1', 1785, 'start: 3 features'),
    ('v2', 2527, 'bug fixed'),
    ('v4', 493138, '+ holes, wells'),
    ('v7', 2498084, '+ move features'),
    ('v8', 5879365, 'pruned to 5 weights'),
]


GENES = [k for k, _ in WEIGHT_ROWS]
BOUNDS = {'holes': (-10, 0), 'bumpiness': (-5, 0), 'wells': (-5, 0),     # training/ga.py WEIGHT_BOUNDS
          'landing_height': (-5, 0), 'sz_fit': (0, 5)}
V7_RUN = 'runs/20261009_201504_single_split'   # v8's parent run: learns the move features
V8_RUN = 'runs/20261009_214729_single_split'   # 5 genes, as in the final model


def load_run(run):
    path = os.path.join(ROOT, run, 'checkpoint.json')
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def population_data(weights, rng):
    """Final population of the v8 run: [(genes dict, fitness)], best first."""
    c = load_run(V8_RUN)
    if c:
        pop = [({g: ind['genome'].get('default.' + g, 0.0) for g in GENES}, ind['fitness'])
               for ind in c['population']]
        real = True
    else:  # illustrative: mutated copies of the final weights
        pop = []
        for _ in range(30):
            gen = {g: max(BOUNDS[g][0], min(BOUNDS[g][1], weights[g] + rng.gauss(0, 0.6))) for g in GENES}
            pop.append((gen, 16 - sum(abs(gen[g] - weights[g]) for g in GENES) + rng.gauss(0, 0.3)))
        real = False
    pop.sort(key=lambda x: -x[1])
    return pop, real


def curve_data():
    """Per generation of the v7 run: mean / best fitness, leader fitness and leader genes."""
    c = load_run(V7_RUN)
    if not c:
        return None
    out = []
    for h in c['history']:
        g = h['leader_genome'] or h['best_genome']
        out.append({'mean': h['mean'], 'best': h['best'], 'leader': h['leader_mean'] or h['best'],
                    'landing_height': g.get('default.landing_height', 0.0),
                    'sz_fit': g.get('default.sz_fit', 0.0)})
    return out


def play_frames(policy, seed, moves):
    """Boards after each move of a real game, plus the game at a chosen 'freeze' move."""
    game = TetrisGame()
    stream = PieceStream('random', seed)
    states = []
    for _ in range(moves):
        move = policy.get_best_move(game, stream.current)
        if move is None:
            break
        game.place_piece(stream.current, *move)
        states.append(([row[:] for row in game.board], game.lines_cleared, game.pieces_placed))
        stream.advance()
    return game, stream, states


# ---------------------------------------------------------------- scenes

def s_title(i, n, ctx):
    img, d = new_frame()
    a = fade(i, n, 0, 12)
    # a few falling pieces as decoration
    for k, name in enumerate('ITSZOLJ'):
        x = 260 + k * 230
        y = int(-200 + ((i * (3 + k % 3) + k * 90) % 1400))
        cells = {'I': [(0, 0), (1, 0), (2, 0), (3, 0)], 'O': [(0, 0), (0, 1), (1, 0), (1, 1)],
                 'T': [(0, 0), (0, 1), (0, 2), (1, 1)], 'S': [(0, 1), (0, 2), (1, 0), (1, 1)],
                 'Z': [(0, 0), (0, 1), (1, 1), (1, 2)], 'L': [(0, 0), (1, 0), (2, 0), (2, 1)],
                 'J': [(0, 1), (1, 1), (2, 1), (2, 0)]}[name]
        for r, c in cells:
            d.rectangle([x + c * 40, y + r * 40, x + c * 40 + 38, y + r * 40 + 38],
                        fill=mix(PIECE[name], 0.22 * a))
    text(d, (W // 2, 380), 'A Tetris AI without deep learning', 84, INK, a, True, 'ma')
    text(d, (W // 2, 500), 'hand-picked features  ·  tuned weights  ·  honest measurement', 40, INK2,
         fade(i, n, 15), anchor='ma')
    b = fade(i, n, 35)
    text(d, (W // 2, 640), '1,785', 72, INK3, b, True, 'ra')
    text(d, (W // 2 + 40, 640), '→', 72, INK3, b, anchor='ma')
    text(d, (W // 2 + 80, 640), '≈ 6,000,000', 72, S3, b, True, 'la')
    text(d, (W // 2, 740), 'lines cleared per game', 36, INK2, b, anchor='ma')
    return img


def s_play(i, n, ctx):
    img, d = new_frame()
    a = fade(i, n)
    states = ctx['states']
    k = min(len(states) - 1, i * len(states) // n)
    board, lines, pieces = states[k]
    cell = 44
    bx, by = 260, (H - 20 * cell) // 2
    draw_board(d, board, bx, by, cell, a)
    text(d, (bx + 5 * cell, by - 60), f'pieces {pieces}    lines {lines}', 30, INK2, a, anchor='ma')
    x = 900
    text(d, (x, 300), '1  It plays by itself', 64, INK, a, True)
    text(d, (x, 420), 'For every new piece it tries', 42, INK2, fade(i, n, 10))
    text(d, (x, 475), 'every rotation in every column', 42, INK2, fade(i, n, 10))
    text(d, (x, 530), '(up to 34 possible drops).', 42, INK2, fade(i, n, 10))
    text(d, (x, 640), 'Each drop gets a score.', 42, INK, fade(i, n, 50), True)
    text(d, (x, 695), 'The best score wins.', 42, INK, fade(i, n, 50), True)
    return img


def s_logic(i, n, ctx):
    img, d = new_frame()
    a = fade(i, n)
    game, piece, cands, best = ctx['freeze']
    cell = 44
    bx, by = 160, (H - 20 * cell) // 2
    scan = int(n * 0.5)
    if i < scan:
        k = min(len(cands) - 1, i * len(cands) // scan)
        shown = cands[k]
        color = S4
        best_so_far = max(cands[:k + 1], key=lambda c: c['score'])
    else:
        shown = cands[best]
        color = GOOD
        best_so_far = shown
    draw_board(d, game.board, bx, by, cell, a, ghost=shown['cells'], ghost_color=color)
    text(d, (bx + 5 * cell, by - 60), f'next piece: {piece.name}', 30, INK2, a, anchor='ma')

    x = 760
    text(d, (x, 120), '2  The logic: a weighted sum', 64, INK, a, True)
    text(d, (x, 215), 'score = Σ weight × feature  (higher is better)', 38, INK2, a)
    # table
    y0 = 310
    text(d, (x, y0), 'feature', 30, INK3, a)
    text(d, (x + 470, y0), 'weight', 30, INK3, a, anchor='ra')
    text(d, (x + 690, y0), 'value', 30, INK3, a, anchor='ra')
    text(d, (x + 950, y0), 'points', 30, INK3, a, anchor='ra')
    weights = ctx['weights']
    for j, (key, label) in enumerate(WEIGHT_ROWS):
        y = y0 + 60 + j * 62
        w = weights[key]
        v = shown['features'][key]
        text(d, (x, y), label, 40, INK, a)
        text(d, (x + 470, y), f'{w:+.2f}', 40, S2 if w < 0 else S3, a, anchor='ra')
        text(d, (x + 690, y), f'{v:g}', 40, INK, a, anchor='ra')
        text(d, (x + 950, y), f'{w * v + 0.0:+.1f}'.replace('+0.0', '0.0').replace('-0.0', '0.0'), 40, INK2, a, anchor='ra')
    y = y0 + 60 + 5 * 62 + 10
    d.line([x, y, x + 950, y], fill=mix(GRID, a), width=2)
    text(d, (x, y + 20), 'score', 44, INK, a, True)
    text(d, (x + 950, y + 20), f'{shown["score"]:+.1f}', 44, color, a, True, 'ra')
    k_text = f'drop {cands.index(shown) + 1} of {len(cands)}' if i < scan else 'best drop → play it'
    text(d, (x, y + 100), k_text, 36, color, a, True)
    text(d, (x + 950, y + 100), f'best so far {best_so_far["score"]:+.1f}', 32, INK3, a, anchor='ra')
    text(d, (x, 960), 'Penalise holes, bumps, wells and high drops; reward room for S/Z.',
         30, INK2, fade(i, n, scan))
    return img


def s_ml(i, n, ctx):
    img, d = new_frame()
    a = fade(i, n)
    text(d, (120, 110), 'Machine learning with 5 numbers', 64, INK, a, True)
    text(d, (120, 210), 'No neural network. The whole "brain" is 5 weights.', 40, INK2, fade(i, n, 10))
    weights = ctx['weights']
    reveal = (i - 50) / 25
    for k, (key, label) in enumerate(WEIGHT_ROWS):
        x = 160 + k * 330
        y = 380
        d.rounded_rectangle([x, y, x + 280, y + 200], 24, fill=mix(SURFACE2, a))
        text(d, (x + 140, y + 40), label, 30, INK2, a, anchor='ma')
        t = ease(reveal - k * 0.3)
        if t < 1:
            text(d, (x + 140, y + 125), '?', 72, INK3, a * (1 - t), True, 'mm')
        if t > 0:
            w = weights[key]
            text(d, (x + 140, y + 125), f'{w:+.2f}', 60, S2 if w < 0 else S3, a * t, True, 'mm')
    b = fade(i, n, 95)
    text(d, (W // 2, 700), 'Learning = searching for the 5 numbers that let the bot survive longest.', 40, INK, b, True, 'ma')
    text(d, (W // 2, 780), 'There is no gradient to follow: the only signal is "play games and count".', 36, INK2,
         fade(i, n, 140), anchor='ma')
    text(d, (W // 2, 840), 'So the search is a black-box optimiser: a genetic algorithm.', 36, INK2,
         fade(i, n, 140), anchor='ma')
    return img


def weight_bar(d, x, y, w, gene, value, color, alpha, h=26):
    """Horizontal bar for one weight, length = |value| / |bound|."""
    lo, hi = BOUNDS[gene]
    span = max(abs(lo), abs(hi))
    d.rectangle([x, y, x + w, y + h], fill=mix(EMPTY, alpha))
    d.rectangle([x, y, x + w * min(1, abs(value) / span), y + h], fill=mix(color, alpha))


def s_population(i, n, ctx):
    img, d = new_frame()
    a = fade(i, n)
    pop, real = ctx['population']
    text(d, (120, 90), 'A population of 30 candidates', 64, INK, a, True)
    text(d, (120, 180), 'Each row is one candidate = one set of 5 weights (bar length = size of the weight).',
         34, INK2, fade(i, n, 10))
    x0, y0, rh, cw = 380, 300, 22, 230
    for k, (_, label) in enumerate(WEIGHT_ROWS):
        text(d, (x0 + k * (cw + 20) + cw // 2, y0 - 45), label, 26, INK3, a, anchor='ma')
    text(d, (x0 + 5 * (cw + 20) + 120, y0 - 45), 'fitness', 26, INK3, a, anchor='ma')
    fmin = min(f for _, f in pop)
    fmax = max(f for _, f in pop)
    for r, (genes, fit) in enumerate(pop):
        b = a * ease((i - 15 - r * 1.5) / 10)
        if b <= 0:
            continue
        y = y0 + r * rh
        top = r < 5 and i > n * 0.55
        text(d, (x0 - 20, y + rh // 2), f'#{r + 1}', 18, S3 if top else INK3, b, anchor='rm')
        for k, g in enumerate(GENES):
            weight_bar(d, x0 + k * (cw + 20), y + 3, cw, g, genes[g], S1, b, rh - 6)
        fx = x0 + 5 * (cw + 20)
        d.rectangle([fx, y + 3, fx + 240 * (0.1 + 0.9 * (fit - fmin) / max(1e-9, fmax - fmin)), y + rh - 3],
                    fill=mix(S3 if top else S7, b))
    c = fade(i, n, int(n * 0.55))
    text(d, (120, 990), 'Fitness = how long the bot survives with those weights (log of pieces per death).',
         32, INK, c)
    text(d, (1800, 105), 'real data: v8 run, last generation' if real else 'illustration', 24, INK3, a, anchor='ra')
    return img


def piece_strip(d, x, y, names, size, alpha):
    for k, nm in enumerate(names):
        d.rectangle([x + k * (size + 4), y, x + k * (size + 4) + size, y + size], fill=mix(PIECE[nm], alpha))


def s_ga(i, n, ctx):
    img, d = new_frame()
    a = fade(i, n)
    pop, _ = ctx['population']
    step_n = n // 4
    step = min(3, i // step_n)
    j = i - step * step_n
    sa = a * min(1.0, j / 8, (step_n - 1 - j) / 8 if step < 3 else 1.0)
    text(d, (120, 90), 'One generation of the genetic algorithm', 60, INK, a, True)
    steps = [('Evaluate', 'everyone plays the same pieces'),
             ('Select', 'tournaments pick the parents'),
             ('Crossover', 'mix two parents'),
             ('Mutate', 'small random changes')]
    for k, (t1, t2) in enumerate(steps):
        y = 260 + k * 160
        on = k == step
        d.rounded_rectangle([120, y, 600, y + 120], 20, fill=mix(S1 if on else SURFACE2, a))
        text(d, (150, y + 22), f'{k + 1}  {t1}', 38, INK, a, True)
        text(d, (150, y + 74), t2, 26, INK if on else INK3, a)
    if step == 0:
        text(d, (W // 2 + 380, 230), 'Fitness = average over the same games', 34, INK, sa, True, 'ma')
        seq = ctx['pieces'][:18]
        for r in range(6):
            y = 330 + r * 90
            text(d, (760, y + 14), f'candidate {r + 1}', 26, INK2, sa)
            piece_strip(d, 960, y + 10, seq, 30, sa)
            text(d, (1800, y + 14), f'{pop[r * 5][1]:.1f}', 28, INK, sa, True, 'ra')
        text(d, (760, 900), 'Same piece sequences for all ("common random numbers"),', 30, INK2, sa)
        text(d, (760, 945), 'so differences come from the weights, not from luck.', 30, INK2, sa)
    elif step == 1:
        text(d, (W // 2 + 380, 230), 'Tournament selection', 34, INK, sa, True, 'ma')
        rng = ctx['rng_sel']
        picks = rng[(j // 30) % len(rng)]
        best = min(picks)
        for r in range(30):
            cx = 800 + (r % 10) * 100
            cy = 360 + (r // 10) * 130
            rad = 20 + 18 * (pop[r][1] - pop[-1][1]) / max(1e-9, pop[0][1] - pop[-1][1])
            col = S3 if r < 5 else (S4 if r in picks else S7)
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=mix(col, sa * (1 if r in picks or r < 5 else 0.45)))
            if r == best:
                d.ellipse([cx - rad - 10, cy - rad - 10, cx + rad + 10, cy + rad + 10], outline=mix(INK, sa), width=4)
        text(d, (760, 780), 'Pick 5 at random (yellow); the fittest of them becomes a parent (ring).', 30, INK2, sa)
        text(d, (760, 830), 'Bigger circle = higher fitness. The 5 best overall (green)', 30, INK2, sa)
        text(d, (760, 875), 'survive unchanged ("elites") and are re-tested every generation,', 30, INK2, sa)
        text(d, (760, 920), 'so a candidate that was only lucky gets found out.', 30, INK2, sa)
    else:
        A, B = pop[0][0], pop[3][0]
        child, src, mut = ctx['child']
        text(d, (W // 2 + 380, 230), 'Crossover: each weight from parent A or B' if step == 2
             else 'Mutation: ~20% of weights get random noise', 34, INK, sa, True, 'ma')
        cols = [('parent A', A, S1), ('parent B', B, S2), ('child', child, None)]
        for c, (name, genes, color) in enumerate(cols):
            x = 760 + c * 380
            text(d, (x, 320), name, 30, INK, sa, True)
            for k, (g, label) in enumerate(WEIGHT_ROWS):
                y = 380 + k * 95
                text(d, (x, y), label, 22, INK3, sa)
                if color is None:
                    col = S1 if src[g] == 'A' else S2
                    v = genes[g]
                    if step == 3 and g == mut:
                        t = ease((j - 20) / 25)
                        v = lerp((A if src[g] == 'A' else B)[g], genes[g], t)
                        col = S5 if t > 0 else col
                    elif step == 3:
                        v = (A if src[g] == 'A' else B)[g]
                    else:
                        v = (A if src[g] == 'A' else B)[g]
                        if ease((j - 10 - k * 6) / 8) <= 0:
                            col = EMPTY
                else:
                    col, v = color, genes[g]
                weight_bar(d, x, y + 32, 320, g, v, col, sa, 30)
                text(d, (x + 320, y), f'{v:+.2f}', 22, INK2, sa, anchor='ra')
        if step == 2:
            text(d, (760, 900), 'Each weight is copied from a random parent (70% of children; the rest', 30, INK2, sa)
            text(d, (760, 945), 'are copies of one parent). Good parts of two solutions can combine.', 30, INK2, sa)
        else:
            text(d, (760, 900), 'Pink: one weight nudged by Gaussian noise (σ = 10% of its range).', 30, INK2, sa)
            text(d, (760, 945), 'Mutation keeps exploring weights nobody in the population has tried.', 30, INK2, sa)
    return img


def s_noise(i, n, ctx):
    img, d = new_frame()
    a = fade(i, n)
    text(d, (120, 90), 'The hard part: measuring fitness', 64, INK, a, True)
    # left: spread of 30 games with the same weights
    x0, x1, y = 140, 860, 500
    lo, hi = 4, 7.5
    text(d, (x0, 230), '30 games, same bot, same weights:', 34, INK, a, True)
    for v in (1e4, 1e5, 1e6, 1e7):
        gx = x0 + (math.log10(v) - lo) / (hi - lo) * (x1 - x0)
        d.line([gx, y - 140, gx, y + 60], fill=mix(GRID, a), width=2)
        text(d, (gx, y + 75), fmt(v) + ' lines', 22, INK3, a, anchor='ma')
    for k, v in enumerate(ctx['noise']):
        t = ease((i - 10 - k) / 6)
        gx = x0 + (math.log10(v) - lo) / (hi - lo) * (x1 - x0)
        gy = y - 110 + (k * 37) % 150
        d.ellipse([gx - 11, gy - 11, gx + 11, gy + 11], fill=mix(S1, a * t))
    text(d, (x0, 640), 'One game is one very noisy data point:', 32, INK2, fade(i, n, 40))
    text(d, (x0, 685), 'from 100k to 20M lines for the same weights.', 32, INK2, fade(i, n, 40))
    text(d, (x0, 730), 'And a strong bot needs ~1M pieces per game.', 32, INK2, fade(i, n, 40))

    b = fade(i, n, 90)
    x = 1020
    text(d, (x, 230), 'Fix: measure the road to death in steps', 34, INK, b, True)
    levels = ['clean', '6 holes', '10', '14', '18', 'game over']
    probs = ['', 'time', 'p₁', 'p₂', 'p₃', 'p₄']
    reveal = (i - 100) / 12
    for k, label in enumerate(levels):
        t = ease(reveal - k)
        xx = x + k * 140
        hgt = 30 + k * 52
        col = CRIT if k == len(levels) - 1 else S7
        d.rectangle([xx, 640 - hgt * t, xx + 100, 640], fill=mix(col, b * (0.35 + 0.65 * t)))
        text(d, (xx + 50, 655), label, 24, INK2, b * t, anchor='ma')
        if k:
            text(d, (xx + 50, 630 - hgt * t - 40), probs[k], 26, INK, b * t, anchor='ma')
    c = fade(i, n, 170)
    text(d, (x, 740), 'Start from clean boards, run until 6 holes, then', 30, INK2, c)
    text(d, (x, 785), 'count how often 6 → 10, 10 → 14, ... → game over.', 30, INK2, c)
    text(d, (x, 830), 'pieces per death ≈ time to 6 holes ÷ (p₁·p₂·p₃·p₄)', 30, INK, c, True)
    text(d, (x, 900), 'Every step is common, so a few hundred short games', 30, INK2, fade(i, n, 230))
    text(d, (x, 945), 'are enough ("multilevel splitting").', 30, INK2, fade(i, n, 230))
    return img


def line_chart(d, box, series, n_show, ylo, yhi, alpha, ylabels):
    x0, y0, x1, y1 = box
    d.line([x0, y1, x1, y1], fill=mix(GRID, alpha), width=2)
    for v, lab in ylabels:
        yy = y1 - (v - ylo) / (yhi - ylo) * (y1 - y0)
        d.line([x0, yy, x1, yy], fill=mix(GRID, alpha * 0.6), width=1)
        text(d, (x0 - 14, yy), lab, 22, INK3, alpha, anchor='rm')
    for vals, color, width in series:
        m = len(vals)
        pts = [(x0 + k / (m - 1) * (x1 - x0), y1 - (v - ylo) / (yhi - ylo) * (y1 - y0))
               for k, v in enumerate(vals[:max(2, n_show)])]
        d.line(pts, fill=mix(color, alpha), width=width, joint='curve')


def s_curve(i, n, ctx):
    img, d = new_frame()
    a = fade(i, n)
    data = ctx['curve']
    text(d, (120, 90), 'A real training run (v7, 40 generations)', 60, INK, a, True)
    m = len(data)
    show = int(m * ease((i - 15) / (n * 0.55)))
    # top: fitness
    box = (260, 230, 1180, 560)
    line_chart(d, box, [([h['mean'] for h in data], S7, 4), ([h['best'] for h in data], INK3, 2),
                        ([h['leader'] for h in data], S3, 6)], show, 6, 18, a,
               [(8, '8'), (12, '12'), (16, '16')])
    text(d, (260, 190), 'fitness (log pieces per death)', 26, INK2, a)
    for k, (lab, col) in enumerate([('leader (best long-run average)', S3), ('population mean', S7),
                                    ('best this generation (noisy)', INK3)]):
        d.rectangle([1230, 260 + k * 50, 1260, 280 + k * 50], fill=mix(col, a))
        text(d, (1275, 255 + k * 50), lab, 26, INK2, a)
    # bottom: genes
    box2 = (260, 680, 1180, 930)
    line_chart(d, box2, [([h['sz_fit'] for h in data], S3, 6), ([h['landing_height'] for h in data], S2, 6)],
               show, -1.5, 2.5, a, [(-1, '-1'), (0, '0'), (1, '+1'), (2, '+2')])
    text(d, (260, 640), 'leader\'s weights', 26, INK2, a)
    text(d, (720, 960), 'generation →', 24, INK3, a, anchor='ma')
    d.rectangle([1230, 720, 1260, 740], fill=mix(S3, a))
    text(d, (1275, 715), 'S/Z fit  0 → +2.3', 26, INK2, a)
    d.rectangle([1230, 770, 1260, 790], fill=mix(S2, a))
    text(d, (1275, 765), 'landing height  0 → −1.15', 26, INK2, a)
    b = fade(i, n, int(n * 0.6))
    text(d, (1230, 450), 'Generation 1 is half random,', 28, INK, b)
    text(d, (1230, 490), 'so its mean is low.', 28, INK, b)
    text(d, (1230, 860), 'The GA found by itself that the', 28, INK, b)
    text(d, (1230, 900), 'new move features matter.', 28, INK, b)
    return img


def s_overfit(i, n, ctx):
    img, d = new_frame()
    a = fade(i, n)
    text(d, (120, 90), "Trap: the winner's curse", 64, INK, a, True)
    text(d, (120, 190), 'The best of many noisy scores is mostly the luckiest.', 38, INK2, fade(i, n, 10))
    vals = [('first GA: its own best score', 5968, S4), ('same weights on new games', 1785, S1)]
    for k, (lab, v, col) in enumerate(vals):
        t = ease((i - 25 - k * 25) / 20)
        y = 300 + k * 110
        text(d, (120, y + 20), lab, 30, INK, a)
        d.rectangle([700, y, 700 + 900 * v / 6000 * t, y + 70], fill=mix(col, a))
        if t > 0:
            text(d, (700 + 900 * v / 6000 * t + 20, y + 35), f'{v * t:,.0f} lines', 32, INK, a, True, 'lm')
    b = fade(i, n, 90)
    text(d, (120, 560), 'So the games are split three ways and never mixed:', 36, INK, b, True)
    blocks = [('train seeds', 'the GA learns on these', S7),
              ('validation seeds', 'pick the final weights', S4),
              ('test seeds', 'only for the reported results', S3)]
    for k, (t1, t2, col) in enumerate(blocks):
        c = fade(i, n, 110 + k * 20)
        x = 120 + k * 570
        d.rounded_rectangle([x, 640, x + 530, 800], 20, fill=mix(col, c * 0.85))
        text(d, (x + 265, 685), t1, 34, INK, c, True, 'ma')
        text(d, (x + 265, 740), t2, 28, INK, c, anchor='ma')
    text(d, (120, 880), 'Two models are compared on the same test games (paired), ≥ 1,000 games', 32, INK2,
         fade(i, n, 190))
    text(d, (120, 925), 'to see a 10% difference.', 32, INK2, fade(i, n, 190))
    return img


def s_features(i, n, ctx):
    img, d = new_frame()
    a = fade(i, n)
    text(d, (120, 110), '4  How the features were found', 64, INK, a, True)
    board = ctx['crisis']
    cell = 36
    bx, by = 200, 230
    heights = []
    for c in range(10):
        r = 0
        while r < 20 and not board[r][c]:
            r += 1
        heights.append(r)
    holes = {(r, c): (255, 255, 255) for c in range(10) for r in range(heights[c] + 1, 20) if not board[r][c]}
    pulse = 0.6 + 0.4 * math.sin(i / 4)
    draw_board(d, board, bx, by, cell, a, {k: mix(v, pulse) for k, v in holes.items()})
    text(d, (bx + 5 * cell, by + 20 * cell + 30), f'how an early version died: {len(holes)} holes', 28, INK2, a, anchor='ma')
    x = 760
    steps = [('Record 500 games until the bot dies', INK),
             ('Measure what rises before each death', INK),
             ('Add the strongest signal as a feature', INK),
             ('Keep it only if it wins on held-out games', S3)]
    for k, (s, col) in enumerate(steps):
        b = fade(i, n, 8 + k * 16)
        y = 330 + k * 120
        d.ellipse([x, y - 6, x + 64, y + 58], fill=mix(S1, b))
        text(d, (x + 32, y + 26), str(k + 1), 34, INK, b, True, 'mm')
        text(d, (x + 95, y + 6), s, 40, col, b, k == 3)
    text(d, (x, 860), 'Found this way: holes & wells (×200 lines),', 32, INK2, fade(i, n, 70))
    text(d, (x, 905), 'then landing height & S/Z fit (×5 more).', 32, INK2, fade(i, n, 70))
    return img


def s_results(i, n, ctx):
    img, d = new_frame()
    a = fade(i, n, 0, 9, 12)
    text(d, (120, 110), '5  Results', 64, INK, a, True)
    text(d, (120, 200), 'mean lines per game, held-out games (log scale)', 34, INK2, a)
    x0, x1 = 420, 1650
    y0 = 300
    lo, hi = math.log10(1000), math.log10(1e7)
    for v in (1e3, 1e4, 1e5, 1e6, 1e7):
        gx = x0 + (math.log10(v) - lo) / (hi - lo) * (x1 - x0)
        d.line([gx, y0 - 20, gx, y0 + 5 * 130 - 30], fill=mix(GRID, a), width=2)
        text(d, (gx, y0 + 5 * 130 - 15), fmt(v), 26, INK3, a, anchor='ma')
    for k, (name, val, why) in enumerate(RESULTS):
        t = ease((i - 10 - k * 14) / 18)
        y = y0 + k * 130
        cur = 10 ** lerp(lo, math.log10(val), t)
        bw = (math.log10(cur) - lo) / (hi - lo) * (x1 - x0)
        col = S3 if k == len(RESULTS) - 1 else S1
        text(d, (x0 - 30, y + 10), name, 42, INK, a, True, 'ra')
        text(d, (x0 - 30, y + 62), why, 24, INK3, a, anchor='ra')
        if t > 0:
            d.rectangle([x0, y, x0 + max(bw, 4), y + 80], fill=mix(col, a))
            text(d, (x0 + bw + 20, y + 40), f'{cur:,.0f}', 38, INK, a * min(1, t * 3), True, 'lm')
    text(d, (W // 2, 990), '≈ 3,300× more lines than the first version', 40, S3, fade(i, n, 95, 9, 12), True, 'ma')
    return img


def s_outro(i, n, ctx):
    img, d = new_frame()
    a = fade(i, n, 0, 9, 1)
    text(d, (W // 2, 400), 'Simple features + tuned weights + honest tests', 60, INK, a, True, 'ma')
    text(d, (W // 2, 500), '5 numbers play ~6 million lines', 44, S3, a, anchor='ma')
    text(d, (W // 2, 640), 'github.com/JCA374/tetris-heuristics', 34, INK2, a, anchor='ma')
    return img


SCENES = [(s_title, 5.0), (s_ml, 8.0), (s_play, 7.0), (s_logic, 10.0), (s_population, 8.0),
          (s_ga, 18.0), (s_noise, 11.0), (s_curve, 10.0), (s_overfit, 9.0), (s_features, 8.0),
          (s_results, 8.0), (s_outro, 4.0)]


# ---------------------------------------------------------------- main

def build_context(seed):
    policy = load_policy()
    weights = policy.weights['default']
    game, stream, states = play_frames(policy, seed, 150)

    # freeze: the board after 40 moves, the next piece and all its candidate drops
    g = TetrisGame()
    s = PieceStream('random', seed)
    for _ in range(40):
        g.place_piece(s.current, *policy.get_best_move(g, s.current))
        s.advance()
    piece = s.current
    cands = []
    for rot, col in g.get_all_possible_moves(piece):
        sim = g.simulate_move(piece, rot, col)
        if sim is None:
            continue
        f = compute_features(sim, sim.lines_cleared - g.lines_cleared)
        score = sum(weights[k] * f[k] for k, _ in WEIGHT_ROWS)
        cands.append({'cells': piece_cells(g, piece, rot, col), 'features': f, 'score': score,
                      'move': (rot, col)})
    best_move = policy.get_best_move(g, piece)
    best = next(k for k, c in enumerate(cands) if c['move'] == best_move)

    # a board at death from a weak model (baseline) for the features scene
    weak = Policy.load(os.path.join(ROOT, 'models', 'baseline_single_v1.json'))
    crisis = None
    for sd in range(seed, seed + 20):
        wg, ws = TetrisGame(), PieceStream('random', sd)
        last = None
        while not wg.game_over:
            m = weak.get_best_move(wg, ws.current)
            if m is None or not wg.place_piece(ws.current, *m):
                break
            last = [row[:] for row in wg.board]
            ws.advance()
        if last:
            crisis = last
            break
    rng = random.Random(seed)
    pop, real = population_data(weights, rng)
    A, B = pop[0][0], pop[3][0]
    src = {g: ('A' if rng.random() < 0.5 else 'B') for g in GENES}
    child = {g: (A if src[g] == 'A' else B)[g] for g in GENES}
    mut = 'landing_height'
    lo, hi = BOUNDS[mut]
    child[mut] = max(lo, min(hi, child[mut] - 0.1 * (hi - lo)))
    stream = PieceStream('random', seed)
    pieces = []
    for _ in range(18):
        pieces.append(stream.current.name)
        stream.advance()
    sel = [sorted(rng.sample(range(30), 5)) for _ in range(8)]
    # per-game spread of a strong model: log-normal, median 4.18M, log sd 1.25 (README / CLAUDE.md)
    noise = [rng.lognormvariate(math.log(4.18e6), 1.25) for _ in range(30)]
    noise = [min(max(v, 2e4), 2.5e7) for v in noise]
    if curve_data() is None:
        global SCENES
        SCENES = [sc for sc in SCENES if sc[0] is not s_curve]
    return {'states': states, 'freeze': (g, piece, cands, best), 'weights': weights, 'crisis': crisis,
            'population': (pop, real), 'child': (child, src, mut), 'pieces': pieces, 'rng_sel': sel,
            'noise': noise, 'curve': curve_data()}


def frames(ctx, fps):
    for fn, secs in SCENES:
        n = int(round(secs * fps))
        for i in range(n):
            yield fn(i, n, ctx)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'video', 'tetris_explainer.mp4'))
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--seed', type=int, default=3_100_000)  # analysis seed range
    ap.add_argument('--preview', metavar='PNG', nargs='?', const='video_preview.png',
                    help='write a contact sheet (2 frames per scene) instead of the video')
    args = ap.parse_args()
    ctx = build_context(args.seed)

    if args.preview:
        thumbs = []
        for fn, secs in SCENES:
            n = int(round(secs * args.fps))
            for i in (n // 3, n * 3 // 4):
                thumbs.append(fn(i, n, ctx).resize((W // 4, H // 4)))
        cols = 4
        sheet = Image.new('RGB', (cols * W // 4, math.ceil(len(thumbs) / cols) * H // 4), BG)
        for k, t in enumerate(thumbs):
            sheet.paste(t, ((k % cols) * W // 4, (k // cols) * H // 4))
        sheet.save(args.preview)
        print('wrote', args.preview)
        return

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{W}x{H}', '-r', str(args.fps), '-i', '-', '-an', '-c:v', 'libx264',
           '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for img in frames(ctx, args.fps):
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    if proc.wait():
        sys.exit('ffmpeg failed')
    print('wrote', args.out)


if __name__ == '__main__':
    main()
