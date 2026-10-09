"""
Run games with a Policy on reproducible piece sequences.

Seed ranges are kept disjoint so that models are never selected on the games
they are finally tested on:
    TEST_SEEDS        0 ..            experiments/compare.py (held-out)
    VALIDATION_SEEDS  1_000_000 ..    final model pick at the end of training
    TRAIN_SEEDS       2_000_000 ..    GA fitness (new block every generation)
    ANALYSIS_SEEDS    3_000_000 ..    experiments/record_games.py (board logs for feature research)
    CRISIS seeds      4_000_000 ..    pieces after crisis start states (train), 5_000_000.. (validation)
"""

from collections import deque

from . import fastcore
from .game import TetrisGame
from .pieces import ALL_PIECES, make_generator

TEST_SEED_BASE = 0
VALIDATION_SEED_BASE = 1_000_000
TRAIN_SEED_BASE = 2_000_000
ANALYSIS_SEED_BASE = 3_000_000
CRISIS_TRAIN_SEED_BASE = 4_000_000      # pieces after a crisis start state (train.py --crisis)
CRISIS_VALIDATION_SEED_BASE = 5_000_000


def encode_board(game):
    """Board as a list of row strings: '.' empty, otherwise the piece letter (row 0 = top)."""
    return [''.join('.' if c == 0 else c for c in row) for row in game.board]


class GameRecorder:
    """
    Collects boards during a game for offline analysis:
    - the last `keep_last` placements before the game ended (board after each move)
    - a snapshot every `snapshot_every` pieces (typical mid-game boards)
    - how the game ended: final board, the piece that could not be placed,
      and how long since each piece type was last seen (droughts)
    """

    def __init__(self, keep_last=300, snapshot_every=100):
        self.keep_last = keep_last
        self.snapshot_every = snapshot_every
        self.recent = deque(maxlen=keep_last)
        self.snapshots = []
        self.last_seen = {p.name: 0 for p in ALL_PIECES}

    def after_move(self, game, piece, move, regime, cleared):
        n = game.pieces_placed
        self.last_seen[piece.name] = n
        board = encode_board(game)
        self.recent.append({'n': n, 'piece': piece.name, 'rotation': move[0], 'col': move[1],
                            'regime': regime, 'cleared': cleared, 'board': board})
        if self.snapshot_every and n % self.snapshot_every == 0:
            self.snapshots.append({'n': n, 'lines': game.lines_cleared, 'board': board})

    def finish(self, game, stream):
        n = game.pieces_placed
        return {
            'game_over': game.game_over,
            'final_board': encode_board(game),
            'killer_piece': stream.current.name if game.game_over else None,
            'next_piece': stream.next.name,
            'pieces_since_seen': {k: n - v for k, v in self.last_seen.items()},
            'recent': list(self.recent),
            'snapshots': self.snapshots,
        }


class PieceStream:
    """Current + next piece from a seeded generator."""

    def __init__(self, randomizer='random', seed=None):
        self.generator = make_generator(randomizer, seed)
        self.current = self.generator.get_next_piece()
        self.next = self.generator.get_next_piece()

    def advance(self):
        self.current = self.next
        self.next = self.generator.get_next_piece()


class _HistoryStream:
    """PieceStream over a fastcore.Runner's piece history, starting at piece `pos`."""

    def __init__(self, runner, pos):
        self.runner, self.pos = runner, pos
        runner._draw_until(pos + 2)
        self._set()

    def _set(self):
        h = self.runner.history
        self.current, self.next = ALL_PIECES[h[self.pos]], ALL_PIECES[h[self.pos + 1]]

    def advance(self):
        self.pos += 1
        self.runner._draw_until(self.pos + 2)
        self._set()


def record_game(policy, seed=None, max_pieces=None, lookahead=False, randomizer='random',
                keep_last=300, snapshot_every=10_000, tail_span=2_500, tail_every=100, height=20):
    """
    Like play_game(..., recorder=GameRecorder(...)), but fast enough for games of millions of pieces.

    The C core plays the game and keeps its state every `tail_every` pieces. When the
    game ends, the last ~`keep_last` pieces are replayed in Python with a GameRecorder
    (both engines make identical moves). Snapshots: every `snapshot_every` pieces,
    plus every `tail_every` pieces in the last `tail_span` (so "dies soon" boards exist
    for any game length). Boards from the C core have 'X' instead of piece letters.
    """
    runner = fastcore.Runner(policy, seed=seed, lookahead=lookahead, randomizer=randomizer, height=height)
    ring = deque(maxlen=(keep_last + tail_span) // tail_every + 3)
    snapshots = []
    ring.append(runner.state())
    while True:
        target = runner.game.pieces + tail_every
        if max_pieces is not None:
            target = min(target, max_pieces)
        if runner.advance(target) or (max_pieces is not None and runner.game.pieces >= max_pieces):
            break
        state = runner.state()
        ring.append(state)
        if state['pieces'] % snapshot_every == 0:
            snapshots.append({'n': state['pieces'], 'lines': state['lines'], 'board': runner.board()})

    end = runner.state()
    if end['pieces'] and end['pieces'] % snapshot_every == 0:
        snapshots.append({'n': end['pieces'], 'lines': end['lines'], 'board': runner.board()})
    regime_counts = {rule['name']: runner.counts[i] for i, rule in enumerate(policy.rules) if runner.counts[i]}
    result = {'seed': seed, 'lines': end['lines'], 'pieces': end['pieces'], 'score': end['score'],
              'capped': not end['game_over'], 'regime_counts': regime_counts}

    def to_board(rows, width=10):
        return [''.join('X' if (r >> c) & 1 else '.' for c in range(width)) for r in rows]

    total = end['pieces']
    dense = [s for s in ring if s['pieces'] >= total - tail_span and s['pieces'] % snapshot_every
             and s['pieces'] > 0]
    snapshots += [{'n': s['pieces'], 'lines': s['lines'], 'board': to_board(s['rows'])} for s in dense]
    snapshots.sort(key=lambda s: s['n'])

    if not end['game_over']:
        result['record'] = {'game_over': False, 'final_board': runner.board(), 'killer_piece': None,
                            'next_piece': None, 'pieces_since_seen': {}, 'recent': [], 'snapshots': snapshots}
        return result

    # Replay the end in Python from the latest saved state at least keep_last pieces before it
    start = max((s for s in ring if s['pieces'] <= total - keep_last), key=lambda s: s['pieces'],
                default=ring[0])
    game = TetrisGame(height=height)
    game.board = [[('X' if (r >> c) & 1 else 0) for c in range(game.width)] for r in start['rows']]
    game.lines_cleared, game.pieces_placed, game.score = start['lines'], start['pieces'], start['score']
    stream = _HistoryStream(runner, start['pieces'])
    recorder = GameRecorder(keep_last=keep_last, snapshot_every=0)
    n0 = start['pieces']
    for i in range(n0 - 1, -1, -1):         # piece droughts need the full history before the replay
        name = ALL_PIECES[runner.history[i]].name
        if recorder.last_seen[name] == 0:
            recorder.last_seen[name] = i + 1
        if all(recorder.last_seen.values()):
            break
    while not game.game_over:
        move = policy.get_best_move(game, stream.current, next_piece=stream.next if lookahead else None)
        if move is None:
            game.game_over = True
            break
        lines_before = game.lines_cleared
        game.place_piece(stream.current, *move)
        recorder.after_move(game, stream.current, move, getattr(policy, 'last_regime', None),
                            game.lines_cleared - lines_before)
        stream.advance()
    if game.pieces_placed != total or game.lines_cleared != end['lines']:
        raise RuntimeError(f'replay diverged from the C core (seed {seed}): '
                           f'{game.pieces_placed} vs {total} pieces')
    record = recorder.finish(game, stream)
    record['snapshots'] = snapshots
    result['record'] = record
    return result


def play_game(policy, seed=None, max_pieces=None, lookahead=False, randomizer='random',
              on_move=None, recorder=None, engine='auto', height=20):
    """
    Play one game to the end (or until max_pieces).

    Args:
        policy: tetris.policy.Policy
        seed: piece-sequence seed (None = unseeded)
        max_pieces: stop after this many pieces (None = play until game over)
        lookahead: give the policy the next piece (1-piece lookahead)
        randomizer: 'random' (uniform, classic) or 'bag' (7-bag)
        on_move: optional callback(game, stream, policy) after each placement
        recorder: optional GameRecorder; its log is returned under 'record'
        engine: 'auto' (C core when possible), 'c' or 'python'. The C core (tetris/fastcore.c)
                plays move-for-move identically and is ~100x faster, but supports no
                on_move/recorder callbacks.
        height: board height (rows)

    Returns:
        dict with lines, pieces, score, capped, regime_counts (+ record)
    """
    hooks = on_move is not None or recorder is not None
    if engine == 'c' or (engine == 'auto' and not hooks and fastcore.available()):
        if hooks:
            raise ValueError("engine='c' does not support on_move/recorder")
        return fastcore.play_game(policy, seed=seed, max_pieces=max_pieces, lookahead=lookahead,
                                  randomizer=randomizer, height=height)

    game = TetrisGame(height=height)
    stream = PieceStream(randomizer, seed)
    policy.reset_stats()

    while not game.game_over:
        if max_pieces is not None and game.pieces_placed >= max_pieces:
            break
        move = policy.get_best_move(game, stream.current,
                                    next_piece=stream.next if lookahead else None)
        if move is None:
            game.game_over = True
            break
        lines_before = game.lines_cleared
        game.place_piece(stream.current, *move)
        if recorder:
            recorder.after_move(game, stream.current, move, getattr(policy, 'last_regime', None),
                                game.lines_cleared - lines_before)
        if on_move:
            on_move(game, stream, policy)
        stream.advance()

    result = {
        'seed': seed,
        'lines': game.lines_cleared,
        'pieces': game.pieces_placed,
        'score': game.score,
        'capped': not game.game_over,
        'regime_counts': dict(policy.regime_counts),
    }
    if recorder:
        result['record'] = recorder.finish(game, stream)
    return result
