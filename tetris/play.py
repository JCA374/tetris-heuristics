"""
Run games with a Policy on reproducible piece sequences.

Seed ranges are kept disjoint so that models are never selected on the games
they are finally tested on:
    TEST_SEEDS        0 ..            experiments/compare.py (held-out)
    VALIDATION_SEEDS  1_000_000 ..    final model pick at the end of training
    TRAIN_SEEDS       2_000_000 ..    GA fitness (new block every generation)
"""

from .game import TetrisGame
from .pieces import make_generator

TEST_SEED_BASE = 0
VALIDATION_SEED_BASE = 1_000_000
TRAIN_SEED_BASE = 2_000_000


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
              on_move=None):
    """
    Play one game to the end (or until max_pieces).

    Args:
        policy: tetris.policy.Policy
        seed: piece-sequence seed (None = unseeded)
        max_pieces: stop after this many pieces (None = play until game over)
        lookahead: give the policy the next piece (1-piece lookahead)
        randomizer: 'random' (uniform, classic) or 'bag' (7-bag)
        on_move: optional callback(game, stream, policy) after each placement

    Returns:
        dict with lines, pieces, score, capped, regime_counts
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
        game.place_piece(stream.current, *move)
        if on_move:
            on_move(game, stream, policy)
        stream.advance()

    return {
        'seed': seed,
        'lines': game.lines_cleared,
        'pieces': game.pieces_placed,
        'score': game.score,
        'capped': not game.game_over,
        'regime_counts': dict(policy.regime_counts),
    }
