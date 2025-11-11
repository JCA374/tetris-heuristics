# 🎮 Demo Guide - Watch the AI Play

Three different ways to watch the Tetris AI in action!

---

## 1. 🖥️ Terminal Demo (Colored, No Dependencies)

**File:** `demo_enhanced.py`

Beautiful terminal visualization with ANSI colors. Works everywhere, no installation needed!

### Features
- 🎨 Color-coded pieces (each tetromino has its color)
- 📊 Live statistics with progress bars
- 🔮 Next piece preview (with lookahead)
- 📈 Session tracking across multiple games
- ⚡ Speed presets (slow/normal/fast/turbo)
- 🎯 Auto-restart with stats accumulation

### Quick Start
```bash
# Default settings
python demo_enhanced.py

# With lookahead (10× better performance)
python demo_enhanced.py --lookahead

# Slow mode for presentations
python demo_enhanced.py --speed slow

# Fast benchmarking
python demo_enhanced.py --speed turbo
```

### Speed Presets

| Preset   | Delay | Moves/sec | Best For                    |
|----------|-------|-----------|------------------------------|
| `slow`   | 300ms | 3.3/sec   | Presentations, watching AI think |
| `normal` | 150ms | 6.7/sec   | Default viewing experience   |
| `fast`   | 75ms  | 13.3/sec  | Quick testing                |
| `turbo`  | 25ms  | 40/sec    | Performance benchmarking     |

### Options
```bash
python demo_enhanced.py --lookahead --speed slow     # Slow with lookahead
python demo_enhanced.py --delay 200                  # Custom 200ms delay
python demo_enhanced.py --max-pieces 100             # Stop after 100 pieces
```

---

## 2. 🎨 Pygame Demo (Graphical, Requires pygame)

**File:** `demo_pygame.py`

Real graphical Tetris with smooth animations, 3D-shaded blocks, and actual colors!

### Features
- 🎨 Real graphics with 3D shading
- 🎯 Smooth animations
- 📊 Live statistics panel
- 🔮 Visual next piece preview
- ⏸️ Pause/Resume (SPACE)
- 🔄 Auto-restart
- 📈 Session tracking

### Installation
```bash
pip install pygame
```

### Quick Start
```bash
# Basic usage
python demo_pygame.py

# With lookahead (recommended)
python demo_pygame.py --lookahead

# Faster gameplay
python demo_pygame.py --speed 2.0

# Perfect demo setup
python demo_pygame.py --lookahead --speed 1.0
```

### Speed Options

| Speed | Delay  | Best For                     |
|-------|--------|------------------------------|
| 0.5   | 1000ms | Slow, watch AI think         |
| 1.0   | 500ms  | Default, good viewing speed  |
| 2.0   | 250ms  | Faster gameplay              |
| 4.0   | 125ms  | Quick testing                |
| 10.0  | 50ms   | Maximum speed                |

### Controls

| Key   | Action           |
|-------|------------------|
| SPACE | Pause/Resume     |
| Q     | Quit             |

### Visual Layout
```
┌────────────────────────────────────────────┐
│           TETRIS AI                         │
│         🔮 LOOKAHEAD ON                     │
├────────────────────────────────────────────┤
│                           ┌───────────────┐ │
│  ┌──────────────┐         │  CURRENT      │ │
│  │              │         │  ┌─────┐      │ │
│  │              │         │  │█████│      │ │
│  │              │         │  └─────┘      │ │
│  │    GAME      │         │     O         │ │
│  │    BOARD     │         └───────────────┘ │
│  │    10×20     │         ┌───────────────┐ │
│  │              │         │  NEXT         │ │
│  │              │         │  ┌───────┐    │ │
│  │              │         │  │███████│    │ │
│  │              │         │  └───────┘    │ │
│  │              │         │     I         │ │
│  └──────────────┘         └───────────────┘ │
│                           ┌───────────────┐ │
│                           │  GAME STATS   │ │
│                           │  Lines: 42    │ │
│                           │  Score: 1,680 │ │
│                           │  Pieces: 108  │ │
│                           │               │ │
│                           │  SESSION      │ │
│                           │  Best: 524    │ │
│                           │  Average: 449 │ │
│                           │  Games: 3     │ │
│                           └───────────────┘ │
└────────────────────────────────────────────┘
```

### Color Scheme
- **I-piece** (line) - Bright Cyan
- **O-piece** (square) - Bright Yellow
- **T-piece** - Purple/Magenta
- **S-piece** - Bright Green
- **Z-piece** - Bright Red
- **J-piece** - Bright Blue
- **L-piece** - Orange

---

## 3. 📊 Model Comparison (Terminal, No Dependencies)

**File:** `demo.py`

Compare different weight strategies side-by-side with statistics!

### Features
- 🆚 Compare multiple weight sets
- 📊 Statistical analysis
- 📈 Performance benchmarks
- 🎯 List all available models

### Quick Start
```bash
# Watch default model
python demo.py

# Compare all models (5 games each)
python demo.py --compare --games 5

# List available models
python demo.py --list

# Benchmark specific model
python demo.py --model balanced --games 10
```

### Available Models
- **balanced** - Empirically best (892 lines avg)
- **defensive** - High hole penalty (755 lines avg)
- **current** - Lee 2013 GA-optimized (513 lines avg)
- **aggressive** - Line-focused (variable performance)

---

## 📊 Demo Comparison

| Feature              | Terminal (enhanced) | Pygame | Comparison |
|---------------------|---------------------|--------|------------|
| Dependencies        | None                | pygame | None       |
| Graphics            | ANSI colors         | Real   | Basic      |
| Animation           | Text-based          | Smooth | None       |
| Speed control       | ✅ Presets          | ✅ Numeric | ❌         |
| Pause/Resume        | ❌                  | ✅ SPACE | ❌         |
| Model comparison    | ❌                  | ❌      | ✅         |
| Session stats       | ✅                  | ✅      | ❌         |
| Next piece preview  | ✅                  | ✅      | ❌         |
| Works over SSH      | ✅                  | ❌      | ✅         |

---

## 🎯 Recommended Setups

### For Presentations
```bash
# Terminal (works anywhere)
python demo_enhanced.py --lookahead --speed slow

# Pygame (if you have display)
python demo_pygame.py --lookahead --speed 0.5
```

### For Benchmarking
```bash
# Terminal (fastest)
python demo_enhanced.py --lookahead --speed turbo --max-pieces 500

# Pygame (visual)
python demo_pygame.py --lookahead --speed 10.0
```

### For Understanding Strategy
```bash
# Terminal (watch decisions)
python demo_enhanced.py --lookahead --speed slow

# Pygame (pause and examine)
python demo_pygame.py --lookahead --speed 1.0
```

### For Comparing Strategies
```bash
# Model comparison
python demo.py --compare --games 10
```

---

## 🔧 Troubleshooting

### Terminal Demo Issues

**Colors not showing:**
- Terminal may not support ANSI colors
- Try different terminal (e.g., Windows Terminal on Windows)

**Too fast/slow:**
```bash
python demo_enhanced.py --delay 100  # Custom delay
```

### Pygame Demo Issues

**"No module named 'pygame'":**
```bash
pip install pygame
```

**Window doesn't open:**
- Need graphical display (won't work over SSH without X forwarding)
- Use terminal demo instead

**Game runs too fast/slow:**
```bash
python demo_pygame.py --speed 2.0  # Adjust speed
```

---

## 💡 Tips

1. **Best visual experience**: Use `--lookahead` to see next piece preview
2. **Presentation mode**: Use `--speed slow` or `--speed 0.5`
3. **Benchmarking**: Use `--speed turbo` or `--speed 10.0` and let it run
4. **Understanding AI**: Use slow speed and watch decision-making
5. **Quick testing**: Use `--max-pieces 50` to stop early

---

## 🎬 Example Commands

```bash
# Watch beautiful terminal demo
python demo_enhanced.py --lookahead

# Watch gorgeous pygame graphics
python demo_pygame.py --lookahead

# Compare all strategies scientifically
python demo.py --compare --games 10

# Quick presentation demo (terminal)
python demo_enhanced.py --lookahead --speed slow --max-pieces 100

# Quick presentation demo (pygame)
python demo_pygame.py --lookahead --speed 1.0
```

---

**Choose your demo style and enjoy watching the AI play!** 🎮✨
