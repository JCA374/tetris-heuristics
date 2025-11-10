# 🎮 Pygame Graphical Demo Setup

The **demo_pygame.py** connects your AI to a real graphical Tetris game with actual colors, animations, and smooth visuals!

## ✨ Features

- 🎨 **Real graphics** - Colored blocks with 3D shading
- 🎯 **Smooth animations** - Proper game feel
- 📊 **Live statistics** - Game stats and session tracking
- 🔮 **Next piece preview** - Visual lookahead display
- ⏸️ **Pause/Resume** - SPACE to pause
- 🔄 **Auto-restart** - Continuous gameplay

## 📦 Installation

### Step 1: Install Pygame

```bash
# Install pygame
pip install pygame

# Or install from requirements.txt
pip install -r requirements.txt
```

### Step 2: Verify Installation

```bash
python -c "import pygame; print('✓ Pygame installed!')"
```

## 🚀 Running the Demo

### Basic Usage

```bash
# Run with default settings
python demo_pygame.py

# With one-piece lookahead (10× performance)
python demo_pygame.py --lookahead

# Faster gameplay
python demo_pygame.py --speed 2.0

# Fast with lookahead
python demo_pygame.py --lookahead --speed 1.5
```

### Speed Options

The `--speed` parameter controls how fast the AI makes moves:

| Speed | Delay  | Best For                     |
|-------|--------|------------------------------|
| 0.5   | 1000ms | Slow, watch AI think         |
| 1.0   | 500ms  | Default, good viewing speed  |
| 2.0   | 250ms  | Faster gameplay              |
| 4.0   | 125ms  | Quick testing                |
| 10.0  | 50ms   | Maximum speed                |

## 🎮 Controls

| Key   | Action           |
|-------|------------------|
| SPACE | Pause/Resume     |
| Q     | Quit             |

## 🎨 Visual Layout

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

## 🎨 Color Scheme

Each piece has its signature color:

- **I-piece** (line) - Bright Cyan
- **O-piece** (square) - Bright Yellow
- **T-piece** - Purple/Magenta
- **S-piece** - Bright Green
- **Z-piece** - Bright Red
- **J-piece** - Bright Blue
- **L-piece** - Orange

Blocks have 3D shading with lighter top-left edges and darker bottom-right edges for depth.

## 🎯 Recommended Settings

### For Impressive Demo
```bash
python demo_pygame.py --lookahead --speed 1.0
```
Perfect balance - you can see the AI thinking ahead and watch the strategy unfold.

### For Quick Testing
```bash
python demo_pygame.py --lookahead --speed 4.0
```
Fast gameplay to quickly see performance.

### For Watching Strategy
```bash
python demo_pygame.py --lookahead --speed 0.5
```
Slow motion to clearly see decision-making.

## 📊 What You'll See

1. **Colored pieces** dropping in real-time
2. **Current piece** preview showing what's being placed
3. **Next piece** preview (with lookahead enabled)
4. **Live stats** updating after each move
5. **Session tracking** across multiple games
6. **Smooth animations** and visual feedback

## 🔧 Troubleshooting

### "No module named 'pygame'"
```bash
pip install pygame
```

### Game runs too fast/slow
Adjust with `--speed`:
```bash
python demo_pygame.py --speed 0.5  # Slower
python demo_pygame.py --speed 2.0  # Faster
```

### Window doesn't open
Make sure you're not in a headless environment (needs display).

### Permission denied
```bash
chmod +x demo_pygame.py
```

## 🆚 Demo Comparison

| Feature              | demo.py | demo_enhanced.py | demo_pygame.py |
|---------------------|---------|------------------|----------------|
| Terminal-based      | ✅      | ✅               | ❌             |
| Real graphics       | ❌      | ❌               | ✅             |
| Color pieces        | ❌      | ✅               | ✅             |
| 3D shading          | ❌      | ❌               | ✅             |
| Smooth animation    | ❌      | ❌               | ✅             |
| Next piece preview  | ❌      | ✅               | ✅             |
| Session stats       | ❌      | ✅               | ✅             |
| Model comparison    | ✅      | ❌               | ❌             |
| Pause/Resume        | ❌      | ❌               | ✅             |
| Dependencies        | None    | None             | pygame         |

## 💡 Tips

1. **Best visual experience**: Use `--lookahead` to see next piece preview
2. **Presentation mode**: Use `--speed 1.0` or `--speed 0.5`
3. **Benchmarking**: Use `--speed 10.0` and let it run
4. **Understanding AI**: Pause with SPACE to examine the board state

## 🎬 Example Session

```bash
# Start the pygame demo with lookahead
python demo_pygame.py --lookahead

# Watch the AI play!
# - See colored pieces drop
# - Watch stats update in real-time
# - Observe strategy with next piece preview
# - Press SPACE to pause and examine
# - Press Q to quit

# After game over:
# - Automatically restarts
# - Session stats accumulate
# - Best game is tracked
```

Enjoy watching your AI play Tetris with real graphics! 🎮✨

---

**Note**: If you prefer terminal-based demos (no installation needed):
- Use `demo_enhanced.py` for colored terminal output
- Use `demo.py` for model comparisons
