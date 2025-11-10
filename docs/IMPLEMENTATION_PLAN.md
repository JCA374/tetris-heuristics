# Tetris AI Implementation Plan

## Project Overview
Build a simple, computationally efficient Tetris AI using heuristic evaluation with Python.

## Design Decisions

### Approach: 4-Feature Heuristic with Hand-Tuned Weights
- **Why:** Simplest approach, low computational cost, proven to work
- **Lookahead:** None (0-piece) initially, can add 1-piece later
- **Language:** Python 3 (clean, simple, fast to implement)
- **Visualization:** Text-based (simple, works everywhere)

### Architecture

```
tetris-heuristics/
├── src/
│   ├── tetris_game.py      # Core game engine
│   ├── tetris_pieces.py    # Tetromino definitions
│   ├── tetris_ai.py        # AI with heuristics
│   └── main.py             # Runner script
├── tests/
│   └── test_heuristics.py  # Unit tests
├── RESEARCH.md             # Research documentation
├── IMPLEMENTATION_PLAN.md  # This file
├── requirements.txt        # Python dependencies
└── README.md              # Project documentation
```

## Implementation Steps

### Phase 1: Core Game Engine (tetris_game.py)

**TetrisGame class:**
- `__init__(width=10, height=20)` - Initialize board
- `board` - 2D array representing game state
- `current_piece` - Active tetromino
- `score` - Lines cleared counter
- `is_game_over()` - Check if game ended
- `get_column_heights()` - Return height of each column
- `place_piece(piece, rotation, column)` - Place piece on board
- `clear_lines()` - Remove completed lines, return count
- `copy()` - Deep copy game state for simulation
- `simulate_move(piece, rotation, column)` - Return resulting board state

### Phase 2: Tetromino Definitions (tetris_pieces.py)

**Piece class:**
- 7 standard Tetris pieces (I, O, T, S, Z, J, L)
- Each piece has 1-4 rotation states
- Store as 2D coordinate arrays

**Pieces:**
```python
I = [[(0,0), (0,1), (0,2), (0,3)], [(0,0), (1,0), (2,0), (3,0)]]
O = [[(0,0), (0,1), (1,0), (1,1)]]
T = [[(0,1), (1,0), (1,1), (1,2)], ...]  # 4 rotations
S, Z, J, L = ...  # Similar definitions
```

### Phase 3: AI Heuristics (tetris_ai.py)

**TetrisAI class:**

**Heuristic Functions:**
1. `calculate_aggregate_height(board)` → int
   - Sum of column heights
   - O(columns) complexity

2. `calculate_holes(board)` → int
   - Count empty cells below filled cells
   - O(rows × columns) complexity

3. `calculate_bumpiness(board)` → int
   - Sum |height[i] - height[i+1]|
   - O(columns) complexity

4. `calculate_complete_lines(board)` → int
   - Count fully filled rows
   - O(rows × columns) complexity

**AI Logic:**
- `evaluate_board(board)` → float
  - Combine heuristics with weights
  - Score = w1×height + w2×lines + w3×holes + w4×bumpiness

- `get_all_possible_moves(game, piece)` → [(rotation, column)]
  - Generate all valid placements

- `get_best_move(game, piece)` → (rotation, column)
  - Try all moves
  - Return move with best score

**Initial Weights (from research):**
```python
WEIGHTS = {
    'height': -0.51,
    'lines': +0.76,
    'holes': -0.36,
    'bumpiness': -0.18
}
```

### Phase 4: Main Runner (main.py)

**Features:**
- Initialize game
- Run AI in loop until game over
- Display board state periodically
- Show statistics (lines cleared, pieces placed)
- Configurable speed and verbosity

### Phase 5: Visualization

**Text-based board display:**
```
┌──────────┐
│..........│
│..........│
│..........│
│....■■....│
│....■■....│
└──────────┘
Lines: 0 | Pieces: 5
```

**Optional:** Add color with ANSI codes

### Phase 6: Testing & Refinement

- Unit tests for heuristics
- Test edge cases (empty board, full board, holes)
- Run AI and measure performance
- Optionally tune weights manually
- Document results

## Success Criteria

- AI can play complete games without crashing
- Clears at least 100 lines consistently
- Runs in real-time (< 100ms per move)
- Code is clean, documented, and under 500 lines

## Future Enhancements (Optional)

1. Add 1-piece lookahead
2. Implement genetic algorithm for weight optimization
3. Add pygame visualization
4. Compare with random player
5. Implement Pierre Dellacherie algorithm
6. Add replay/recording functionality

## Time Estimate

- Phase 1-2 (Game engine): 1-2 hours
- Phase 3 (AI): 1-2 hours
- Phase 4-5 (Runner & viz): 1 hour
- Phase 6 (Testing): 1 hour
- **Total: 4-6 hours**
