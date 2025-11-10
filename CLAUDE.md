# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Tetris AI using heuristic evaluation** (not deep learning). Current implementation averages 513 lines per game. Research analysis shows path to 100,000-35M lines through systematic improvements.

**Key Philosophy:** Feature engineering > Algorithm sophistication. Research proves heuristic approaches outperform deep learning by 1000× in Tetris.

## Essential Commands

### Running & Testing
```bash
# Run AI (default weights, no visualization)
python src/main.py
python src/main.py --games 10 --verbose

# Watch AI play in real-time (new demo system)
python demo.py
python demo.py --model balanced        # Best performing model
python demo.py --compare --games 5     # Benchmark all models

# Run test suite (15 tests, all should pass)
python tests/test_heuristics.py
```

### Quick Testing
```bash
# Fast validation (10 pieces only)
python src/main.py --test --no-board

# Compare models quickly
python demo.py --list    # See available weight sets
```

## Architecture

### Core Components

**1. TetrisGame (`src/tetris_game.py`)**
- Standard 10×20 board, 7 tetromino pieces
- Handles: piece placement, collision detection, line clearing, scoring
- Key method: `simulate_move()` - returns new game state without modifying original (critical for AI evaluation)
- Board representation: 2D array where 0=empty, non-zero=filled

**2. TetrisPiece (`src/tetris_pieces.py`)**
- Defines all 7 pieces (I, O, T, S, Z, J, L) with rotation states
- I/O have 1-2 rotations; T/S/Z/J/L have 2-4 rotations
- Coordinates stored as (row, col) relative to reference point

**3. TetrisAI (`src/tetris_ai.py`)**
- **Current:** 4-feature heuristic (height, lines, holes, bumpiness)
- **Evaluation:** Linear weighted sum of features
- **Search:** Exhaustive (tries all ~20-40 possible placements per piece)
- **Weights:** GA-optimized from Lee (2013) research
- **NO learning:** Fixed weights, no online adaptation

**4. Demo System (`demo.py`)**
- Real-time visualization with multiple pre-configured weight sets
- Model comparison mode with statistical analysis
- Found "balanced" strategy outperforms current by 2.7×

### Data Flow

```
Game Loop:
1. Get next piece → TetrisPiece
2. AI.get_best_move(game, piece)
   a. game.get_all_possible_moves(piece) → ~20-40 (rotation, column) pairs
   b. For each move:
      - game.simulate_move(piece, rotation, col) → simulated board
      - AI.evaluate_board(simulated) → score (weighted heuristics)
   c. Return move with highest score
3. game.place_piece(piece, rotation, col)
   - Drops piece to lowest valid position
   - Clears completed lines
   - Updates score
4. Repeat until game_over
```

## Implementation Roadmap (From Research Analysis)

### Current Status: Phase 0
- **Performance:** 513 lines average
- **Features:** 4 basic heuristics
- **Lookahead:** None (evaluates only current piece)

### Phase 1: One-Piece Lookahead (HIGHEST PRIORITY)
- **Goal:** 5,000-10,000 lines (10× improvement)
- **Time:** 1-2 days
- **Changes:**
  - Add `SevenBagGenerator` for fair piece distribution
  - Track `next_piece` in game state
  - Modify `get_best_move()` to evaluate current + next piece
  - Add `_evaluate_with_lookahead()` method (~40×40=1600 evaluations)
- **See:** `DETAILED_IMPLEMENTATION_GUIDE.md` for complete code

### Phase 2: Dellacherie Features (HIGH PRIORITY)
- **Goal:** 100,000-660,000 lines (200-1000× improvement)
- **Time:** 2-3 days
- **Add 6 strategic features:**
  - Landing Height: where piece lands (lower = better)
  - Eroded Cells: piece cells cleared immediately (rewards efficiency)
  - Row/Column Transitions: surface roughness (detect holes early)
  - Wells: deep vertical gaps (heavily penalized)
  - Hole Depth: buried vs shallow holes
  - **Rows with Holes:** weight=-24.04, MOST IMPACTFUL FEATURE
- **Weights:** Hand-tuned Dellacherie or CEM-optimized available in research

### Phase 3: Genetic Algorithm Training
- **Goal:** 1-5M lines through weight optimization
- **Time:** 1-2 weeks training
- Not yet implemented

### Phase 4: Cross-Entropy Method
- **Goal:** 10-35M lines (world-class)
- **Time:** 2-4 weeks training
- Research shows CEM with 8 features achieves 35M lines

## Critical Design Decisions

### Why Heuristics Over Deep Learning
- **Research finding:** Best deep RL ~1,000 lines vs heuristics 35M lines = 99.998% performance gap
- Tetris has discoverable strategic principles that experts can articulate
- Feature engineering is tractable; end-to-end learning from sparse rewards fails

### Why No Lookahead Currently
- **Computational cost:** 0-piece (current) vs 1-piece (160× slower) vs 2-piece (26,000× slower)
- Phase 1 adds 1-piece lookahead with ~1600 evaluations (still fast at 10-20ms/move)
- 2-piece lookahead impractical except for research purposes

### Weight Set Design
- `DEFAULT_WEIGHTS`: Lee (2013) GA-optimized for 4 features
- `demo.py` includes 4 weight sets; "balanced" empirically best (892 lines avg)
- Dellacherie weights available but features not yet implemented

## Working with This Codebase

### When Adding Features
1. **Add feature calculation method** to `TetrisAI` class
2. **Update weights dict** with new feature
3. **Modify `evaluate_board()`** to include feature if needed
4. **Add tests** to `tests/test_heuristics.py`
5. **Benchmark** using `demo.py --compare` before/after

### When Modifying Game Logic
- **ALWAYS preserve `simulate_move()`** - AI depends on non-destructive simulation
- Test with `python tests/test_heuristics.py`
- Verify all 15 tests pass (particularly `test_game_simulation`)

### When Tuning Weights
1. Add weight set to `demo.py` WEIGHT_SETS dict
2. Run comparison: `python demo.py --compare --games 10`
3. Document in weight set: source, expected performance, feature set

## Test Suite

**15 tests, all passing:**
- Heuristic calculations (5): empty board, height, holes, bumpiness, lines
- Game mechanics (4): line clearing, multiple clears, scoring, simulation
- AI behavior (3): move selection, all pieces, move generation
- Edge cases (3): game over, boundaries, multiple holes

**Run specific test:**
```python
# In test_heuristics.py, tests are functions starting with test_
# Run full suite: python tests/test_heuristics.py
# For single test, modify __main__ to call specific function
```

## Documentation Structure

- **README.md:** Project overview, quick start
- **RESEARCH.md:** Original deep research on Tetris AI approaches
- **RESEARCH_ANALYSIS.md:** Analysis of research docs, identifies missing features
- **DETAILED_IMPLEMENTATION_GUIDE.md:** Step-by-step Phase 1 & 2 code
- **QUICK_START.md:** Command reference
- **TEST_SUITE_SUMMARY.md:** Test coverage details
- **docs/:** ChatGPT and Claude research papers (PDFs)

## Performance Baselines

| Implementation | Lines | Notes |
|----------------|-------|-------|
| Current (4 features, no lookahead) | 513 | Baseline |
| Balanced strategy (tuned weights) | 892 | From demo.py testing |
| Target Phase 1 (+ lookahead) | 5,000 | 10× improvement |
| Target Phase 2 (+ Dellacherie) | 100,000-660,000 | 200-1000× improvement |

## Important Research Findings

1. **"Rows with Holes" is the secret weapon** - weight -24.04, most impactful feature ever discovered
2. **Feature quality >> algorithm sophistication** - Same algorithm, different features = 100× performance difference
3. **One-piece lookahead is mandatory** - All competitive AIs use at least 1-piece
4. **7-bag randomization matters** - Prevents piece droughts/floods, more fair than pure random

## Common Pitfalls

1. **Don't break `simulate_move()`** - Must return new game state without modifying original
2. **Don't add online learning** - Fixed weights are the design; training happens offline
3. **Don't optimize prematurely** - Phase 1 (lookahead) before Phase 2 (features) before Phase 3 (training)
4. **Test after changes** - All 15 tests must pass; game simulation is fragile
