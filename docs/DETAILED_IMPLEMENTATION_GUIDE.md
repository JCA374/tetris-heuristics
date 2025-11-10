# Detailed Implementation Guide - Phase by Phase

## 🎯 Overview

This guide provides step-by-step instructions for implementing the improvements from RESEARCH_ANALYSIS.md. Each phase includes specific code changes, examples, and expected outcomes.

---

## 📊 Performance Projection

| Phase | Implementation | Lines Cleared | Improvement | Time to Implement |
|-------|----------------|---------------|-------------|-------------------|
| **Current** | 4 features, no lookahead | 513 | Baseline (1×) | ✅ Complete |
| **Phase 1** | + One-piece lookahead | 5,000+ | 10× | 1-2 days |
| **Phase 2** | + Dellacherie 6 features | 100,000+ | 200-1,000× | 2-3 days |
| **Phase 3** | + GA weight training | 1-5M | 2,000-10,000× | 1-2 weeks |
| **Phase 4** | + Cross-Entropy Method | 10-35M | 20,000-68,000× | 2-4 weeks |

---

# PHASE 1: One-Piece Lookahead (HIGHEST PRIORITY)

## 🎯 Goal: 10× Improvement → 5,000+ lines per game

### Why This Matters

**Current problem:** The AI only looks at the current piece:
```python
# AI evaluates: "Where should I put this I-piece?"
# Problem: Might create a perfect spot for I but terrible for next O-piece!
```

**Solution:** Consider both current AND next piece:
```python
# AI evaluates: "Where should I put this I-piece so the next O-piece also has a good spot?"
# Result: Avoids shortsighted decisions
```

### Step 1: Add Next Piece Tracking (30 minutes)

**File: `src/tetris_pieces.py`**

Add a 7-bag generator (more fair than pure random):

```python
# Add this class to tetris_pieces.py

import random

class SevenBagGenerator:
    """
    Generates pieces using the 7-bag system.

    More fair than pure random:
    - Shuffle all 7 pieces
    - Dispense them in order
    - Repeat

    Prevents long droughts or floods of the same piece.
    """

    def __init__(self):
        self.bag = []
        self.refill_bag()

    def refill_bag(self):
        """Create a new shuffled bag of all 7 pieces."""
        self.bag = ALL_PIECES.copy()
        random.shuffle(self.bag)

    def get_next_piece(self):
        """Get the next piece from the bag."""
        if not self.bag:
            self.refill_bag()
        return self.bag.pop()

    def peek_next_piece(self):
        """Look at next piece without removing it."""
        if not self.bag:
            self.refill_bag()
        return self.bag[-1]
```

### Step 2: Update Game to Track Next Piece (20 minutes)

**File: `src/tetris_game.py`**

```python
# In TetrisGame.__init__():
def __init__(self, width=10, height=20, use_7bag=True):
    # ... existing code ...
    self.use_7bag = use_7bag

    if use_7bag:
        from tetris_pieces import SevenBagGenerator
        self.piece_generator = SevenBagGenerator()
    else:
        self.piece_generator = None

    self.current_piece = None
    self.next_piece = None

# Add this method:
def get_next_piece(self):
    """Get the next piece to play."""
    if self.piece_generator:
        return self.piece_generator.get_next_piece()
    else:
        from tetris_pieces import get_random_piece
        return get_random_piece()

def peek_next_piece(self):
    """Look at the next piece without consuming it."""
    if self.piece_generator:
        return self.piece_generator.peek_next_piece()
    else:
        # If not using 7-bag, we can't peek
        return None
```

### Step 3: Implement One-Piece Lookahead in AI (1 hour)

**File: `src/tetris_ai.py`**

Add the lookahead logic:

```python
def get_best_move(self, game, piece, next_piece=None, verbose=False):
    """
    Find the best move for a given piece, optionally considering next piece.

    Args:
        game: TetrisGame object
        piece: TetrisPiece to place
        next_piece: Optional next piece for lookahead
        verbose: If True, print evaluation details

    Returns:
        Tuple of (rotation, column) for best move, or None if no valid moves
    """
    possible_moves = game.get_all_possible_moves(piece)

    if not possible_moves:
        return None

    best_score = float('-inf')
    best_move = None
    move_scores = []

    for rotation, col in possible_moves:
        # Simulate the move for current piece
        sim_game = game.simulate_move(piece, rotation, col)

        if sim_game is None:
            continue

        # If we have a next piece, use lookahead
        if next_piece is not None:
            score = self._evaluate_with_lookahead(sim_game, next_piece)
        else:
            # No lookahead, just evaluate current board
            score = self.evaluate_board(sim_game)

        move_scores.append((rotation, col, score))

        if score > best_score:
            best_score = score
            best_move = (rotation, col)

        self.moves_evaluated += 1

    if verbose and move_scores:
        print(f"\nEvaluated {len(move_scores)} possible moves for piece {piece.name}:")
        # Show top 5 moves
        move_scores.sort(key=lambda x: x[2], reverse=True)
        for i, (rot, col, score) in enumerate(move_scores[:5]):
            marker = "★" if (rot, col) == best_move else " "
            print(f"  {marker} Rotation {rot}, Column {col}: {score:.2f}")

    return best_move

def _evaluate_with_lookahead(self, game, next_piece):
    """
    Evaluate a board position considering the optimal placement of next piece.

    Args:
        game: TetrisGame state after current piece
        next_piece: The next piece to consider

    Returns:
        Best score achievable after optimally placing next piece
    """
    next_moves = game.get_all_possible_moves(next_piece)

    if not next_moves:
        # If next piece can't be placed, this position is terrible
        return float('-inf')

    best_next_score = float('-inf')

    for next_rotation, next_col in next_moves:
        # Simulate placing the next piece
        next_game = game.simulate_move(next_piece, next_rotation, next_col)

        if next_game is None:
            continue

        # Evaluate the board after placing next piece
        score = self.evaluate_board(next_game)
        best_next_score = max(best_next_score, score)

    # Return the best score we can achieve with optimal next piece placement
    return best_next_score
```

### Step 4: Update Main Runner to Use Lookahead (15 minutes)

**File: `src/main.py`**

Update the `run_single_game` function:

```python
def run_single_game(ai, verbose=False, show_board=False, delay=0, use_lookahead=True):
    """
    Run a single game with the AI.

    Args:
        ai: TetrisAI object
        verbose: Show move details
        show_board: Display board after each move
        delay: Delay between moves in seconds
        use_lookahead: Whether to use one-piece lookahead

    Returns:
        Game statistics dict
    """
    game = TetrisGame(use_7bag=use_lookahead)  # Use 7-bag if doing lookahead

    print("\n" + "=" * 50)
    print(f"Starting new game {'with' if use_lookahead else 'without'} lookahead...")
    print("=" * 50)

    start_time = time.time()

    current_piece = game.get_next_piece()

    while not game.game_over:
        # Peek at next piece if using lookahead
        next_piece = game.peek_next_piece() if use_lookahead else None

        # Find best move (with or without lookahead)
        move = ai.get_best_move(game, current_piece, next_piece, verbose=verbose)

        if move is None:
            game.game_over = True
            break

        rotation, col = move

        # Make the move
        game.place_piece(current_piece, rotation, col)

        # Get next piece for next iteration
        current_piece = game.get_next_piece()

        if show_board:
            print(f"\n--- Piece {game.pieces_placed} ({current_piece.name}) ---")
            print(game.display())

        if delay > 0:
            time.sleep(delay)

    end_time = time.time()
    elapsed = end_time - start_time

    # ... rest of function ...
```

### Step 5: Test Phase 1 (15 minutes)

```bash
# Test without lookahead (baseline)
python src/main.py --games 3

# Test WITH lookahead (should be ~10× better!)
python src/main.py --games 3 --lookahead
```

**Add command-line flag:**

```python
# In main.py argparse section:
parser.add_argument(
    '--lookahead',
    action='store_true',
    help='Use one-piece lookahead (slower but much better performance)'
)
```

### Expected Results

**Before (no lookahead):**
- Average: 513 lines
- Speed: 2.7ms per move

**After (with lookahead):**
- Average: 5,000-10,000 lines (10-20× improvement!)
- Speed: ~10-20ms per move (still very fast)

### Validation Checklist

- [ ] `SevenBagGenerator` class added and working
- [ ] `TetrisGame` tracks next piece
- [ ] `get_best_move()` accepts `next_piece` parameter
- [ ] `_evaluate_with_lookahead()` method implemented
- [ ] Tests updated (can pass `None` for `next_piece`)
- [ ] Benchmarking shows 5,000+ lines average

---

# PHASE 2: Dellacherie Features (HIGH PRIORITY)

## 🎯 Goal: 100-1,000× Improvement → 100,000+ lines per game

### Why These Features Matter

Current 4 features are "beginner" metrics. Dellacherie features capture strategic concepts:

| Current Features | Dellacherie Features |
|------------------|----------------------|
| Height (simple sum) | Landing Height (where piece lands) |
| Lines (count) | Eroded Cells (cells from piece that clear) |
| Holes (count) | Row/Column Transitions (surface roughness) |
| Bumpiness (height diff) | Wells (deep vertical gaps) |

**Research finding:** "Dellacherie features achieve 660,000 lines hand-tuned, 35 million optimized"

### Feature 1: Landing Height (30 minutes)

**Concept:** Row where the piece's center lands. Lower is better.

```python
# Add to TetrisAI class:

def calculate_landing_height(self, game, piece, rotation, col_offset):
    """
    Calculate the landing height (row where piece lands).

    Lower is better - indicates we're not building too high.

    Args:
        game: TetrisGame object
        piece: The piece that was placed
        rotation: Rotation used
        col_offset: Column where placed

    Returns:
        Landing height (row index where piece center lands)
    """
    row_offset = game.get_drop_row(piece, rotation, col_offset)

    if row_offset < 0:
        return game.height  # Piece couldn't be placed

    coords = piece.get_rotation(rotation)

    # Find the average row of the piece (its "center")
    total_row = sum(row + row_offset for row, col in coords)
    avg_row = total_row / len(coords)

    # Convert to height from bottom (higher number = higher on board)
    landing_height = game.height - avg_row

    return landing_height
```

### Feature 2: Eroded Piece Cells (45 minutes)

**Concept:** Cells from the placed piece that are cleared immediately. Rewards efficient clearing.

**Formula:** `eroded_cells = lines_cleared × cells_from_piece_in_cleared_lines`

Example:
- Place I-piece horizontally
- It completes 4 lines
- All 4 cells of I-piece are in those lines
- **Eroded cells = 4 × 4 = 16** (maximum reward!)

```python
# This requires tracking which cells came from the placed piece
# We need to modify how we track placed pieces

def calculate_eroded_cells(self, game_before, game_after, piece, rotation, col_offset):
    """
    Calculate eroded piece cells (cells from placed piece that cleared).

    This is the best feature for rewarding efficient line clearing.

    Args:
        game_before: Game state before placement
        game_after: Game state after placement and clearing
        piece: The piece that was placed
        rotation: Rotation used
        col_offset: Column where placed

    Returns:
        Number of eroded cells (lines_cleared × piece_cells_in_cleared_lines)
    """
    lines_cleared = game_after.lines_cleared - game_before.lines_cleared

    if lines_cleared == 0:
        return 0

    # Find which rows were cleared
    # We need to track this in the game engine...
    # For now, we can approximate by checking which piece cells would be in full rows

    row_offset = game_before.get_drop_row(piece, rotation, col_offset)
    coords = piece.get_rotation(rotation)

    piece_cells_in_cleared_lines = 0

    # Check each cell of the piece
    for piece_row, piece_col in coords:
        final_row = piece_row + row_offset
        final_col = piece_col + col_offset

        # Count if this cell would be in a full row
        if all(game_before.board[final_row][c] != 0 or c == final_col
               for c in range(game_before.width)):
            piece_cells_in_cleared_lines += 1

    return lines_cleared * piece_cells_in_cleared_lines
```

**Note:** This feature requires us to track line clears DURING placement. We'll need to enhance `place_piece()`.

### Feature 3 & 4: Row and Column Transitions (1 hour)

**Concept:** Count empty↔filled boundaries. Measures surface roughness.

```python
def calculate_row_transitions(self, game):
    """
    Count horizontal transitions (empty ↔ filled).

    Includes board edges as "filled".
    Lower is better - indicates smoother horizontal surface.

    Returns:
        Total number of row transitions
    """
    transitions = 0

    for row in range(game.height):
        # Left edge (board edge counts as filled)
        if game.board[row][0] == 0:
            transitions += 1

        # Check each adjacent pair
        for col in range(game.width - 1):
            if (game.board[row][col] == 0) != (game.board[row][col + 1] == 0):
                transitions += 1

        # Right edge
        if game.board[row][game.width - 1] == 0:
            transitions += 1

    return transitions

def calculate_column_transitions(self, game):
    """
    Count vertical transitions (empty ↔ filled).

    Includes board edges and floor as "filled".
    Lower is better - indicates fewer holes and gaps.

    This is MORE IMPORTANT than row transitions (weight ~2× higher).

    Returns:
        Total number of column transitions
    """
    transitions = 0

    for col in range(game.width):
        # Top edge (board edge counts as filled)
        if game.board[0][col] == 0:
            transitions += 1

        # Check each adjacent pair
        for row in range(game.height - 1):
            if (game.board[row][col] == 0) != (game.board[row + 1][col] == 0):
                transitions += 1

        # Bottom edge (floor counts as filled)
        if game.board[game.height - 1][col] == 0:
            transitions += 1

    return transitions
```

### Feature 5: Wells (1 hour)

**Concept:** Vertical sequences of empty cells with both neighbors filled.

**Formula:** For each well, add `1 + 2 + ... + depth`

Example: Well of depth 3 contributes 1+2+3=6

```python
def calculate_wells(self, game):
    """
    Calculate well sums (deep vertical gaps).

    A well is a sequence of empty cells with filled cells on both sides.
    Score each well as sum(1..depth): well of depth 3 = 1+2+3 = 6

    Lower is better - deep wells are problematic.

    Returns:
        Total well score
    """
    total_well_score = 0

    for col in range(game.width):
        well_depth = 0

        for row in range(game.height):
            if game.board[row][col] != 0:
                # Filled cell, end of potential well
                if well_depth > 0:
                    # Check if both neighbors were filled (was it a well?)
                    left_filled = (col == 0 or
                                 any(game.board[r][col-1] != 0
                                     for r in range(row-well_depth, row)))
                    right_filled = (col == game.width-1 or
                                  any(game.board[r][col+1] != 0
                                      for r in range(row-well_depth, row)))

                    if left_filled and right_filled:
                        # It's a well! Add triangular number
                        total_well_score += (well_depth * (well_depth + 1)) // 2

                well_depth = 0
            else:
                # Empty cell, extend well depth
                well_depth += 1

        # Handle well at bottom
        if well_depth > 0:
            left_filled = (col == 0 or
                         any(game.board[r][col-1] != 0
                             for r in range(game.height-well_depth, game.height)))
            right_filled = (col == game.width-1 or
                          any(game.board[r][col+1] != 0
                              for r in range(game.height-well_depth, game.height)))

            if left_filled and right_filled:
                total_well_score += (well_depth * (well_depth + 1)) // 2

    return total_well_score
```

### Feature 6 & 7: Hole Depth and Rows with Holes (30 minutes)

```python
def calculate_hole_depth(self, game):
    """
    Calculate hole depth (sum of filled cells above each hole).

    A deeply buried hole is much worse than a shallow one.

    Returns:
        Total hole depth score
    """
    hole_depth_sum = 0

    for col in range(game.width):
        found_block = False
        depth_above = 0

        for row in range(game.height):
            if game.board[row][col] != 0:
                found_block = True
                depth_above += 1
            elif found_block:
                # This is a hole, add the depth above it
                hole_depth_sum += depth_above

    return hole_depth_sum

def calculate_rows_with_holes(self, game):
    """
    Count rows that contain at least one hole.

    MOST IMPORTANT FEATURE (weight: -24.04 in CEM)

    Two holes in same row = 1, not 2

    Returns:
        Number of rows containing holes
    """
    rows_with_holes = 0

    for row in range(game.height):
        has_hole_in_row = False
        found_block_in_row = False

        for col in range(game.width):
            # Check if column has a block above this position
            has_block_above = any(game.board[r][col] != 0 for r in range(row))

            if has_block_above and game.board[row][col] == 0:
                # This is a hole
                has_hole_in_row = True
                break

        if has_hole_in_row:
            rows_with_holes += 1

    return rows_with_holes
```

### Update Evaluation Function

```python
# Add new weight set:
DELLACHERIE_WEIGHTS = {
    'landing_height': -1.0,
    'eroded_cells': 1.0,
    'row_transitions': -1.0,
    'column_transitions': -1.0,
    'holes': -4.0,
    'wells': -1.0
}

DELLACHERIE_THIERY_WEIGHTS = {
    'landing_height': -12.63,
    'eroded_cells': 6.60,
    'row_transitions': -9.22,
    'column_transitions': -19.77,
    'holes': -13.08,
    'wells': -10.49,
    'hole_depth': -1.61,
    'rows_with_holes': -24.04
}

def __init__(self, weights=None, feature_set='basic'):
    """
    Initialize AI with weights and feature set.

    Args:
        weights: Dict of weights (None for defaults)
        feature_set: 'basic', 'dellacherie', or 'dellacherie_thiery'
    """
    self.feature_set = feature_set

    if weights is None:
        if feature_set == 'dellacherie':
            self.weights = self.DELLACHERIE_WEIGHTS.copy()
        elif feature_set == 'dellacherie_thiery':
            self.weights = self.DELLACHERIE_THIERY_WEIGHTS.copy()
        else:
            self.weights = self.DEFAULT_WEIGHTS.copy()
    else:
        self.weights = weights

    self.moves_evaluated = 0
```

### Testing Phase 2

```bash
# Test basic features (baseline)
python src/main.py --games 3

# Test Dellacherie features (should be 100-1000× better!)
python src/main.py --games 3 --features dellacherie

# Test full Dellacherie-Thiery (8 features)
python src/main.py --games 3 --features dellacherie_thiery
```

### Expected Results

**Phase 1 (lookahead only):** 5,000 lines
**Phase 2 (Dellacherie features):** 100,000-660,000 lines
**Phase 2 (+ optimized weights):** Up to 35,000,000 lines with training

---

## 🎯 Quick Decision Guide

**Want immediate 10× improvement?** → Do Phase 1 (1-2 days)
**Want 1000× improvement?** → Do Phase 1 + 2 (3-5 days)
**Want world-class AI?** → Do Phase 1 + 2 + 3 (2-3 weeks)

---

## 📝 Implementation Checklist

### Phase 1: One-Piece Lookahead
- [ ] Add `SevenBagGenerator` class
- [ ] Update `TetrisGame` to track next piece
- [ ] Modify `get_best_move()` to accept `next_piece`
- [ ] Implement `_evaluate_with_lookahead()` method
- [ ] Add `--lookahead` command-line flag
- [ ] Update tests to handle optional `next_piece`
- [ ] Benchmark: achieve 5,000+ lines average

### Phase 2: Dellacherie Features
- [ ] Implement `calculate_landing_height()`
- [ ] Implement `calculate_eroded_cells()`
- [ ] Implement `calculate_row_transitions()`
- [ ] Implement `calculate_column_transitions()`
- [ ] Implement `calculate_wells()`
- [ ] Implement `calculate_hole_depth()`
- [ ] Implement `calculate_rows_with_holes()`
- [ ] Add `DELLACHERIE_WEIGHTS` constant
- [ ] Add `DELLACHERIE_THIERY_WEIGHTS` constant
- [ ] Update `evaluate_board()` to use selected feature set
- [ ] Add `--features` command-line flag
- [ ] Add tests for new features
- [ ] Benchmark: achieve 100,000+ lines average

---

## 🚀 Next Steps

Would you like me to:
1. **Start implementing Phase 1** (one-piece lookahead)
2. **Create skeleton code** for all Dellacherie features
3. **Set up the genetic algorithm** framework for Phase 3
4. **Add comprehensive tests** for the new features first

Let me know which approach you'd prefer!
