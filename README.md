# Tetris AI with Heuristics

A simple, computationally efficient Tetris AI implementation using heuristic evaluation.

## Overview

This project implements a Tetris AI that plays the game using a heuristic-based approach. The AI evaluates all possible piece placements using four key metrics and selects the best move.

## Features

- **Simple 4-feature heuristic evaluation**
  - Aggregate Height (minimize)
  - Complete Lines (maximize)
  - Holes (minimize)
  - Bumpiness (minimize)

- **Efficient implementation**
  - No external dependencies (pure Python)
  - Fast move evaluation
  - Text-based visualization

- **Well-documented code**
  - Clear structure
  - Comprehensive comments
  - Unit tests

## Quick Start

```bash
# Run the AI
python src/main.py

# Run with custom settings
python src/main.py --games 5 --verbose
```

## Project Structure

```
tetris-heuristics/
├── src/
│   ├── tetris_pieces.py    # Tetromino definitions
│   ├── tetris_game.py      # Core game engine
│   ├── tetris_ai.py        # AI with heuristics
│   └── main.py             # Runner script
├── tests/
│   └── test_heuristics.py  # Unit tests
├── RESEARCH.md             # Background research
├── IMPLEMENTATION_PLAN.md  # Design decisions
└── README.md              # This file
```

## How It Works

1. **Game Engine**: Implements standard Tetris rules (10×20 board, 7 pieces, line clearing)
2. **Heuristic Evaluation**: Scores each board state using weighted features
3. **Move Selection**: Tries all possible placements and picks the best one
4. **Repeat**: Continues until game over

### Scoring Formula

```
Score = -0.51 × height + 0.76 × lines - 0.36 × holes - 0.18 × bumpiness
```

## Performance

Expected performance with default weights:
- Lines cleared: 100-2000+ per game
- Move calculation: < 100ms per piece
- No external dependencies required

## Customization

Modify weights in `src/tetris_ai.py`:

```python
WEIGHTS = {
    'height': -0.51,
    'lines': +0.76,
    'holes': -0.36,
    'bumpiness': -0.18
}
```

## Future Enhancements

- [ ] 1-piece lookahead
- [ ] Genetic algorithm for weight optimization
- [ ] Pygame visualization
- [ ] Performance benchmarking
- [ ] Pierre Dellacherie algorithm implementation

## References

See [RESEARCH.md](RESEARCH.md) for detailed background research and academic references.

## License

MIT License
