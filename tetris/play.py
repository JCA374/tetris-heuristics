"""
Run games with a Policy on reproducible piece sequences.

Seed ranges are kept disjoint so that models are never selected on the games
they are finally tested on:
    TEST_SEEDS        0 ..            experiments/compare.py (held-out)
    VALIDATION_SEEDS  1_000_000 ..    final model pick at the end of training
    TRAIN_SEEDS       2_000_000 ..    GA fitness (new block every generation)
    ANALYSIS_SEEDS    3_000_000 ..    experiments/record_games.py (board logs for feature research)
"""

from collections import deque

from .game import TetrisGame
from .pieces import ALL_PIECES, make_generator

TEST_SEED_BASE = 0
VALIDATION_SEED_BASE = 1_000_000
TRAIN_SEED_BASE = 2_000_000
ANALYSIS_SEED_BASE = 3_000_000


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


def play_game(policy, seed=None, max_pieces=None, lookahead=False, randomizer='random',
              on_move=None, recorder=None):
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

    Returns:
        dict with lines, pieces, score, capped, regime_counts (+ record)
    """
    game = TetrisGame()
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
