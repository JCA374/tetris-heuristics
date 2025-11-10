# Quick Start Guide

## 🚀 Getting Started

### Run the AI
```bash
# Basic usage
python src/main.py

# Run 10 games
python src/main.py --games 10

# Quick test (10 pieces)
python src/main.py --test
```

### Watch the AI Play (NEW!)
```bash
# Watch with default settings
python demo.py

# Watch balanced strategy (best performer)
python demo.py --model balanced

# Faster animation
python demo.py --delay 50

# Compare all models
python demo.py --compare --games 3
```

### Run Tests
```bash
# All 15 tests
python tests/test_heuristics.py
```

---

## 🎮 Demo Commands

| Command | Description |
|---------|-------------|
| `python demo.py` | Watch current model play |
| `python demo.py --model balanced` | Watch balanced strategy |
| `python demo.py --model aggressive` | Watch aggressive strategy |
| `python demo.py --delay 100` | Faster animation (100ms) |
| `python demo.py --max-pieces 50` | Stop after 50 pieces |
| `python demo.py --compare` | Compare all models |
| `python demo.py --list` | List all available models |

---

## 📊 Available Models

| Model | Performance | Use Case |
|-------|-------------|----------|
| **balanced** | 892 lines avg | **Best overall** |
| **defensive** | 755 lines avg | Survival focused |
| **current** | 332 lines avg | GA-optimized (Lee 2013) |
| **aggressive** | 385 lines avg | Line clearing focus |

---

## 📁 Project Structure

```
tetris-heuristics/
├── src/
│   ├── main.py           # CLI runner
│   ├── tetris_ai.py      # AI implementation
│   ├── tetris_game.py    # Game engine
│   └── tetris_pieces.py  # Piece definitions
├── tests/
│   └── test_heuristics.py  # 15 unit tests
├── demo.py               # Interactive demo (NEW!)
├── RESEARCH.md           # Original research
├── RESEARCH_ANALYSIS.md  # Update plan
└── README.md             # Main documentation
```

---

## 🎯 What's Next?

See `RESEARCH_ANALYSIS.md` for the full improvement roadmap:

- **Phase 1**: One-piece lookahead → 10× improvement (5,000+ lines)
- **Phase 2**: Dellacherie features → 1000× improvement (100,000+ lines)
- **Phase 3**: Genetic algorithm → 1-5M lines
- **Phase 4**: Cross-Entropy Method → 10-35M lines (world-class)

---

## 🆘 Quick Troubleshooting

**Tests failing?**
```bash
python tests/test_heuristics.py
```

**Demo not working?**
```bash
python demo.py --list  # Check if models load
```

**Performance issues?**
```bash
python demo.py --compare --games 3  # Benchmark
```

---

## 📚 Documentation

- `README.md` - Project overview
- `RESEARCH.md` - Background research on Tetris AI
- `RESEARCH_ANALYSIS.md` - Detailed update plan
- `TEST_SUITE_SUMMARY.md` - Test coverage details
- `IMPLEMENTATION_PLAN.md` - Original design document
- `TEST_RESULTS.md` - Performance benchmarks
