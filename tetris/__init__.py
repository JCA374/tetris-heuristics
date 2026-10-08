"""Tetris heuristic AI: game engine, features, policies (single / regime-switching)."""

from .game import TetrisGame
from .pieces import ALL_PIECES, SevenBagGenerator, UniformGenerator, make_generator, get_piece_by_name
from .features import FEATURES, compute_features, evaluate, regime_stats
from .policy import Policy, TEMPLATES
from .play import play_game, PieceStream
