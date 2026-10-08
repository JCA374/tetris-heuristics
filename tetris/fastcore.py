"""
ctypes bridge to fastcore.c, a C port of the game/feature/policy hot path.

The shared library is compiled with the system C compiler on first use and
cached in tetris/_build/ (keyed by a hash of the source). Pieces still come
from the Python generators, in chunks, so a seed gives exactly the same piece
sequence, and therefore the same game, as the pure-Python engine.

If no compiler is available, `available()` is False and play.play_game falls
back to Python.
"""

import ctypes
import hashlib
import os
import subprocess
import tempfile
from collections import Counter

from .features import FEATURES
from .pieces import ALL_PIECES, make_generator

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, 'fastcore.c')
BUILD_DIR = os.path.join(HERE, '_build')
CFLAGS = ['-O3', '-ffp-contract=off', '-shared', '-fPIC']

MAX_H, MAX_RULES, MAX_ROT, N_FEAT = 32, 8, 4, 6
STATS = ['max_height', 'agg_height', 'holes', 'bumpiness', 'wells', 'hole_depth']
OPS = {'>=': 0, '>': 1, '<=': 2, '<': 3}
PIECE_INDEX = {p.name: i for i, p in enumerate(ALL_PIECES)}
CHUNK = 8192

assert FEATURES == ('height', 'lines', 'holes', 'bumpiness', 'wells', 'hole_depth'), \
    'fastcore.c hard-codes this feature order'


class CGame(ctypes.Structure):
    _fields_ = [('width', ctypes.c_int32), ('height', ctypes.c_int32),
                ('game_over', ctypes.c_int32), ('pad', ctypes.c_int32),
                ('lines', ctypes.c_int64), ('pieces', ctypes.c_int64), ('score', ctypes.c_int64),
                ('rows', ctypes.c_uint32 * MAX_H)]


class CPolicy(ctypes.Structure):
    _fields_ = [('n_rules', ctypes.c_int32),
                ('stat', ctypes.c_int32 * MAX_RULES),
                ('op', ctypes.c_int32 * MAX_RULES),
                ('threshold', ctypes.c_double * MAX_RULES),
                ('w', (ctypes.c_double * N_FEAT) * MAX_RULES)]


_lib = None
_error = None


def _compile():
    with open(SOURCE, 'rb') as f:
        digest = hashlib.sha1(f.read() + ' '.join(CFLAGS).encode()).hexdigest()[:12]
    path = os.path.join(BUILD_DIR, f'fastcore_{digest}.so')
    if not os.path.exists(path):
        os.makedirs(BUILD_DIR, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix='.so', dir=BUILD_DIR)
        os.close(fd)
        try:
            subprocess.run([os.environ.get('CC', 'cc'), *CFLAGS, SOURCE, '-o', tmp, '-lm'],
                           check=True, capture_output=True, text=True)
            os.replace(tmp, path)   # atomic: parallel processes may compile at once
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    return path


def _load():
    global _lib, _error
    if _lib is not None or _error is not None:
        return _lib
    try:
        lib = ctypes.CDLL(_compile())
    except (OSError, subprocess.CalledProcessError) as e:
        _error = getattr(e, 'stderr', None) or str(e)
        return None
    lib.play.restype = ctypes.c_int64
    lib.play.argtypes = [ctypes.POINTER(CGame), ctypes.POINTER(CPolicy), ctypes.POINTER(ctypes.c_int8),
                         ctypes.c_int64, ctypes.c_int, ctypes.c_int64, ctypes.POINTER(ctypes.c_int64)]
    lib.best_move.restype = ctypes.c_int
    lib.best_move.argtypes = [ctypes.POINTER(CGame), ctypes.POINTER(CPolicy), ctypes.c_int, ctypes.c_int,
                              ctypes.POINTER(ctypes.c_int)]

    rotations = (ctypes.c_int32 * 7)(*[p.num_rotations() for p in ALL_PIECES])
    data = (ctypes.c_int32 * (7 * MAX_ROT * 4 * 2))()
    for pi, piece in enumerate(ALL_PIECES):
        for ri, coords in enumerate(piece.rotations):
            for ci, (r, c) in enumerate(coords):
                base = ((pi * MAX_ROT + ri) * 4 + ci) * 2
                data[base], data[base + 1] = r, c
    lib.set_pieces(rotations, data)
    _lib = lib
    return lib


def available():
    return _load() is not None


def build_error():
    _load()
    return _error


def to_cpolicy(policy):
    if len(policy.rules) > MAX_RULES:
        raise ValueError(f'fastcore supports at most {MAX_RULES} rules')
    cp = CPolicy()
    cp.n_rules = len(policy.rules)
    for i, rule in enumerate(policy.rules):
        if 'stat' in rule:
            cp.stat[i] = STATS.index(rule['stat'])
            cp.op[i] = OPS[rule['op']]
            cp.threshold[i] = float(rule['threshold'])
        else:
            cp.stat[i] = -1
        weights = policy.weights[rule['name']]
        for j, f in enumerate(FEATURES):
            cp.w[i][j] = float(weights[f])
    return cp


def play_game(policy, seed=None, max_pieces=None, lookahead=False, randomizer='random', width=10, height=20):
    """Same contract as tetris.play.play_game (without on_move/recorder)."""
    lib = _load()
    if lib is None:
        raise RuntimeError(f'fastcore unavailable: {_error}')
    if height > MAX_H or width > 31:
        raise ValueError('board too large for fastcore')

    game = CGame(width=width, height=height)
    cpol = to_cpolicy(policy)
    counts = (ctypes.c_int64 * MAX_RULES)()
    cap = -1 if max_pieces is None else max_pieces
    generator = make_generator(randomizer, seed)
    draw = lambda n: [PIECE_INDEX[generator.get_next_piece().name] for _ in range(n)]

    buffer = draw(CHUNK)
    while True:
        if max_pieces is not None:   # never draw far beyond the cap
            buffer = buffer[:max(2, max_pieces - game.pieces + 1)]
        seq = (ctypes.c_int8 * len(buffer))(*buffer)
        used = lib.play(ctypes.byref(game), ctypes.byref(cpol), seq, len(buffer), int(lookahead), cap, counts)
        if game.game_over or (max_pieces is not None and game.pieces >= max_pieces):
            break
        buffer = buffer[used:] + draw(CHUNK)

    regime_counts = {rule['name']: counts[i] for i, rule in enumerate(policy.rules) if counts[i]}
    policy.regime_counts = Counter(regime_counts)
    return {
        'seed': seed,
        'lines': game.lines,
        'pieces': game.pieces,
        'score': game.score,
        'capped': not game.game_over,
        'regime_counts': regime_counts,
    }
