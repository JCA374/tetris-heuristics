# 🎮 Enhanced Demo Guide

The **demo_enhanced.py** is a beautiful, presentation-ready visualization of the Tetris AI with stunning visual effects!

## ✨ Features

- 🎨 **Color-coded pieces** - Each tetromino has its own vibrant color
- 📊 **Live statistics** - Real-time game stats with progress bars
- 🔮 **Next piece preview** - See what's coming (with lookahead)
- 📈 **Session tracking** - Tracks best, average across multiple games
- ⚡ **Speed presets** - From slow presentation mode to turbo
- 🎯 **Auto-restart** - Continuous gameplay with stats tracking

## 🚀 Quick Start

### Basic Usage

```bash
# Run with default settings (normal speed, no lookahead)
python demo_enhanced.py

# Enable one-piece lookahead (10× performance)
python demo_enhanced.py --lookahead

# Slow mode for presentations
python demo_enhanced.py --speed slow

# Fast mode for testing
python demo_enhanced.py --speed turbo
```

### Speed Presets

| Preset   | Delay | Moves/sec | Best For                    |
|----------|-------|-----------|------------------------------|
| `slow`   | 300ms | 3.3/sec   | Presentations, watching AI think |
| `normal` | 150ms | 6.7/sec   | Default viewing experience   |
| `fast`   | 75ms  | 13.3/sec  | Quick testing                |
| `turbo`  | 25ms  | 40/sec    | Performance benchmarking     |

### Custom Delay

```bash
# Custom delay (in milliseconds)
python demo_enhanced.py --delay 200
```

### Limited Pieces

```bash
# Stop each game after 100 pieces (useful for quick demos)
python demo_enhanced.py --max-pieces 100
```

## 🎨 Visual Layout

```
════════════════════════════════════════════════════════════════════
   🎮  TETRIS AI - DEFENSIVE STRATEGY
   🔮  ONE-PIECE LOOKAHEAD ACTIVE
════════════════════════════════════════════════════════════════════

┌────────────────────┐  ━━━━━━━━━━━━━━━━━━━━━━━━━━
│                    │   GAME STATISTICS
│                    │  ━━━━━━━━━━━━━━━━━━━━━━━━━━
│                    │
│                    │   Move: #42
│        ██          │   Lines: 15
│        ██          │   [████████░░░░░░░░░░░░]
│      ████          │   Score: 680
│                    │   Pieces: 42
│                    │
│                    │  ━━━━━━━━━━━━━━━━━━━━━━━━━━
│                    │   SESSION STATS
│                    │  ━━━━━━━━━━━━━━━━━━━━━━━━━━
│                    │
│                    │   Best: 524 lines
│                    │   Avg: 449.3 lines
│  ██████████        │   Games: 3
│  ██████████        │
│  ██████████        │   CURRENT:
│  ██████████        │   ┌────┐
│████████████        │   │████│
│████████████        │   │████│
└────────────────────┘   └────┘
                           O

                         NEXT:
                         ┌────────┐
                         │████████│
                         └────────┘
                           I

════════════════════════════════════════════════════════════════════
  Press Ctrl+C to stop  |  Speed: 6.7 moves/sec
════════════════════════════════════════════════════════════════════
```

## 🎯 Recommended Demos

### For Presentations (Best Visual Impact)

```bash
# Slow with lookahead - great for showing decision-making
python demo_enhanced.py --lookahead --speed slow
```

This clearly shows:
- Which piece is current
- What piece is coming next
- How the AI plans ahead
- Real-time statistics

### For Performance Showcase

```bash
# Normal speed with lookahead - balanced viewing
python demo_enhanced.py --lookahead
```

Shows the AI's impressive performance while still being watchable.

### For Quick Testing

```bash
# Turbo mode, limited pieces
python demo_enhanced.py --speed turbo --max-pieces 50
```

Perfect for quick validation or benchmarking.

## 🎨 Color Scheme

Each piece has its own color for easy identification:

- **I-piece** (line) - Cyan 🩵
- **O-piece** (square) - Yellow 💛
- **T-piece** - Magenta 💜
- **S-piece** - Green 💚
- **Z-piece** - Red ❤️
- **J-piece** - Blue 💙
- **L-piece** - Orange 🧡

## 📊 Statistics Explained

### Game Stats (per current game)
- **Move** - Number of pieces placed
- **Lines** - Lines cleared in this game
- **Progress bar** - Visual representation of lines cleared
- **Score** - Current game score
- **Pieces** - Total pieces placed

### Session Stats (across all games)
- **Best** - Highest lines cleared in any game
- **Avg** - Average lines across all games
- **Games** - Number of games completed

## 🎮 Controls

- **Ctrl+C** - Stop and show session summary
- The demo auto-restarts after each game
- Session statistics persist across games

## 💡 Pro Tips

1. **For impressive demos**: Use `--lookahead --speed slow` to clearly show the AI thinking ahead
2. **For quick testing**: Use `--speed turbo --max-pieces 50`
3. **For benchmarking**: Let it run with `--lookahead` and watch the session stats build up
4. **Terminal size**: Works best with terminal at least 80 characters wide

## 🔄 Comparison: Basic vs Enhanced Demo

| Feature              | demo.py (basic) | demo_enhanced.py |
|----------------------|-----------------|------------------|
| Colors               | ❌              | ✅               |
| Next piece preview   | ❌              | ✅               |
| Progress bars        | ❌              | ✅               |
| Session stats        | ❌              | ✅               |
| Auto-restart         | ❌              | ✅               |
| Speed presets        | ❌              | ✅               |
| Side-by-side layout  | ❌              | ✅               |
| Model comparison     | ✅              | ❌               |

Use **demo.py** for comparing different weight strategies.
Use **demo_enhanced.py** for showcasing your best model!

---

## 🎬 Example Commands

```bash
# Default - good all-around demo
python demo_enhanced.py

# Show off the AI's lookahead capability
python demo_enhanced.py --lookahead --speed slow

# Quick benchmark test
python demo_enhanced.py --lookahead --speed fast --max-pieces 100

# Presentation mode (slow, clear, impressive)
python demo_enhanced.py --lookahead --speed slow

# Performance mode (let it run and track session stats)
python demo_enhanced.py --lookahead
```

Enjoy watching your AI play! 🎮✨
