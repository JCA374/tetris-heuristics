"""
Tetris Piece Definitions

Defines all 7 standard Tetris tetrominoes with their rotation states.
Each piece is represented as a list of (row, col) coordinates.
"""

import random


class TetrisPiece:
    """Represents a Tetris piece with its rotation states."""

    def __init__(self, name, rotations, color='#'):
        """
        Initialize a Tetris piece.

        Args:
            name: Single character name (I, O, T, S, Z, J, L)
            rotations: List of rotation states, each is a list of (row, col) coordinates
            color: Character to display for this piece
        """
        self.name = name
        self.rotations = rotations
        self.color = color
        # Per rotation: (width, [(dc, lowest_row_in_that_column), ...]).
        # Lets TetrisGame compute drop rows from column tops instead of scanning.
        self.profiles = []
        for coords in rotations:
            lowest = {}
            for r, c in coords:
                lowest[c] = max(lowest.get(c, r), r)
            width = max(c for _, c in coords) + 1
            self.profiles.append((width, sorted(lowest.items())))

    def get_rotation(self, rotation_index):
        """Get coordinates for a specific rotation state."""
        return self.rotations[rotation_index % len(self.rotations)]

    def num_rotations(self):
        """Return number of unique rotation states."""
        return len(self.rotations)


# Define all 7 Tetris pieces with their rotation states
# Coordinates are (row, col) relative to a reference point

# I - Line piece (cyan)
# ####
I_PIECE = TetrisPiece('I', [
    [(0, 0), (0, 1), (0, 2), (0, 3)],  # Horizontal
    [(0, 0), (1, 0), (2, 0), (3, 0)]   # Vertical
], 'I')

# O - Square piece (yellow)
# ##
# ##
O_PIECE = TetrisPiece('O', [
    [(0, 0), (0, 1), (1, 0), (1, 1)]   # Only one rotation
], 'O')

# T - T piece (purple)
#  #
# ###
T_PIECE = TetrisPiece('T', [
    [(0, 1), (1, 0), (1, 1), (1, 2)],  # Up
    [(0, 0), (1, 0), (1, 1), (2, 0)],  # Right
    [(1, 0), (1, 1), (1, 2), (2, 1)],  # Down
    [(0, 1), (1, 0), (1, 1), (2, 1)]   # Left
], 'T')

# S - S piece (green)
#  ##
# ##
S_PIECE = TetrisPiece('S', [
    [(0, 1), (0, 2), (1, 0), (1, 1)],  # Horizontal
    [(0, 0), (1, 0), (1, 1), (2, 1)]   # Vertical
], 'S')

# Z - Z piece (red)
# ##
#  ##
Z_PIECE = TetrisPiece('Z', [
    [(0, 0), (0, 1), (1, 1), (1, 2)],  # Horizontal
    [(0, 1), (1, 0), (1, 1), (2, 0)]   # Vertical
], 'Z')

# J - J piece (blue)
# #
# ###
J_PIECE = TetrisPiece('J', [
    [(0, 0), (1, 0), (1, 1), (1, 2)],  # Up
    [(0, 0), (0, 1), (1, 0), (2, 0)],  # Right
    [(1, 0), (1, 1), (1, 2), (2, 2)],  # Down
    [(0, 1), (1, 1), (2, 0), (2, 1)]   # Left
], 'J')

# L - L piece (orange)
#   #
# ###
L_PIECE = TetrisPiece('L', [
    [(0, 2), (1, 0), (1, 1), (1, 2)],  # Up
    [(0, 0), (1, 0), (2, 0), (2, 1)],  # Right
    [(1, 0), (1, 1), (1, 2), (2, 0)],  # Down
    [(0, 0), (0, 1), (1, 1), (2, 1)]   # Left
], 'L')


# List of all pieces for random selection
ALL_PIECES = [I_PIECE, O_PIECE, T_PIECE, S_PIECE, Z_PIECE, J_PIECE, L_PIECE]
PIECES_BY_NAME = {p.name: p for p in ALL_PIECES}


class SevenBagGenerator:
    """
    Generates pieces using the 7-bag randomization system.

    This is the modern Tetris standard (used in official games since 2001):
    - Shuffle all 7 pieces into a bag
    - Dispense them in order
    - When bag is empty, refill and reshuffle

    This prevents long droughts/floods of specific pieces and makes the game fairer.
    Example: You're guaranteed to see an I-piece within every 7 pieces.
    """

    def __init__(self, rng=None):
        """
        Args:
            rng: random.Random instance (None = module-level random, unseeded)
        """
        self.rng = rng or random
        self.bag = []

    def get_next_piece(self):
        """Get the next piece from the bag, refilling and shuffling when empty."""
        if not self.bag:
            self.bag = ALL_PIECES.copy()
            self.rng.shuffle(self.bag)
        return self.bag.pop()


class UniformGenerator:
    """Classic randomizer: every piece drawn independently and uniformly."""

    def __init__(self, rng=None):
        self.rng = rng or random

    def get_next_piece(self):
        return self.rng.choice(ALL_PIECES)


GENERATORS = {'random': UniformGenerator, 'bag': SevenBagGenerator}


def make_generator(randomizer='random', seed=None):
    """Create a piece generator ('random' or 'bag') with its own seeded RNG."""
    return GENERATORS[randomizer](random.Random(seed))


def get_random_piece(rng=None):
    """Get a random Tetris piece."""
    return (rng or random).choice(ALL_PIECES)


def get_piece_by_name(name):
    """Get a piece by its name character."""
    return PIECES_BY_NAME.get(name.upper())


if __name__ == '__main__':
    # Test piece definitions
    print("Tetris Pieces Test")
    print("=" * 40)

    for piece in ALL_PIECES:
        print(f"\nPiece {piece.name}: {piece.num_rotations()} rotations")
        for i in range(piece.num_rotations()):
            coords = piece.get_rotation(i)
            print(f"  Rotation {i}: {coords}")

    print("\n✓ All pieces defined successfully")
