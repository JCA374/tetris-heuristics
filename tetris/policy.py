"""
Move-selection policies.

A Policy is an ordered list of regime rules plus one weight set per regime:

    rules = [
        {'name': 'repair', 'stat': 'holes',      'op': '>=', 'threshold': 3},
        {'name': 'danger', 'stat': 'max_height', 'op': '>=', 'threshold': 12},
        {'name': 'normal'},                       # default (no condition)
    ]

Before each piece, the rules are checked top to bottom against the *current*
board (see features.regime_stats); the first match picks the weight set used to
score every candidate move for that piece (including lookahead). Choosing the
regime from the pre-move board keeps all candidate scores on the same scale.

A single-weight model is simply a Policy with one default rule.
"""

import json
from collections import Counter

from .features import FEATURES, evaluate, regime_stats

OPS = {
    '>=': lambda a, b: a >= b,
    '>': lambda a, b: a > b,
    '<=': lambda a, b: a <= b,
    '<': lambda a, b: a < b,
}

# Rule templates used for training. Thresholds are filled in by the GA.
TEMPLATES = {
    'single': [{'name': 'default'}],
    'regime': [
        {'name': 'repair', 'stat': 'holes', 'op': '>='},
        {'name': 'danger', 'stat': 'max_height', 'op': '>='},
        {'name': 'normal'},
    ],
}


class Policy:
    def __init__(self, rules, weights, meta=None):
        """
        Args:
            rules: ordered list of rule dicts; the last must have no 'stat' (default)
            weights: {regime_name: {feature: weight}}
            meta: free-form info saved with the model
        """
        if 'stat' in rules[-1]:
            raise ValueError("last rule must be the unconditional default")
        for rule in rules:
            if rule['name'] not in weights:
                raise ValueError(f"no weights for regime '{rule['name']}'")
        self.rules = rules
        self.weights = weights
        self.meta = meta or {}
        self.regime_counts = Counter()
        self.moves_evaluated = 0

    @classmethod
    def single(cls, weights, meta=None):
        return cls([{'name': 'default'}], {'default': dict(weights)}, meta)

    @property
    def is_single(self):
        return len(self.rules) == 1

    def select_regime(self, game):
        """Name of the regime that applies to the current (pre-move) board."""
        if self.is_single:
            return self.rules[0]['name']
        stats = regime_stats(game)
        for rule in self.rules:
            if 'stat' not in rule or OPS[rule['op']](stats[rule['stat']], rule['threshold']):
                return rule['name']

    def get_best_move(self, game, piece, next_piece=None):
        """
        Best (rotation, column) for `piece`, or None if no valid move.
        With next_piece, scores each move by the best follow-up placement (1-piece lookahead).
        """
        regime = self.select_regime(game)
        self.regime_counts[regime] += 1
        weights = self.weights[regime]
        self.last_regime = regime

        best_score = float('-inf')
        best_move = None
        base_lines = game.lines_cleared
        tops = game.column_tops()

        for rotation, col in game.get_all_possible_moves(piece, tops):
            sim = game.simulate_move(piece, rotation, col, tops)
            if sim is None:
                continue
            if next_piece is None:
                score = evaluate(sim, sim.lines_cleared - base_lines, weights)
                self.moves_evaluated += 1
            else:
                score = self._lookahead_score(sim, next_piece, base_lines, weights)
            if score > best_score:
                best_score = score
                best_move = (rotation, col)

        return best_move

    def _lookahead_score(self, game, next_piece, base_lines, weights):
        best = float('-inf')
        tops = game.column_tops()
        for rotation, col in game.get_all_possible_moves(next_piece, tops):
            sim = game.simulate_move(next_piece, rotation, col, tops)
            if sim is None:
                continue
            best = max(best, evaluate(sim, sim.lines_cleared - base_lines, weights))
            self.moves_evaluated += 1
        return best

    def reset_stats(self):
        self.regime_counts = Counter()
        self.moves_evaluated = 0

    # --- serialization -------------------------------------------------------

    def to_dict(self):
        return {
            'type': 'single' if self.is_single else 'regime',
            'rules': self.rules,
            'weights': self.weights,
            'meta': self.meta,
        }

    def save(self, path):
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
            f.write('\n')

    @classmethod
    def from_dict(cls, data):
        if 'rules' not in data:
            # Legacy best_model.json format: {"weights": {...}, "fitness": ..., ...}
            meta = {k: v for k, v in data.items() if k != 'weights'}
            return cls.single(data['weights'], meta)
        return cls(data['rules'], data['weights'], data.get('meta'))

    @classmethod
    def load(cls, path):
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def describe(self):
        """Human-readable multi-line summary."""
        lines = []
        for rule in self.rules:
            cond = (f"if {rule['stat']} {rule['op']} {rule['threshold']}"
                    if 'stat' in rule else 'otherwise')
            w = self.weights[rule['name']]
            ws = '  '.join(f"{f}={w[f]:+.3f}" for f in FEATURES)
            lines.append(f"{rule['name']:>8} ({cond}): {ws}")
        return '\n'.join(lines)
