# 🧬 Genetic Algorithm Training Guide

Train your own optimal Tetris AI weights using evolutionary algorithms!

## What is This?

The Genetic Algorithm (GA) **evolves** optimal weights by:
1. Creating a population of random weight sets
2. Playing Tetris games to measure fitness
3. Selecting the best performers
4. Creating "offspring" through crossover and mutation
5. Repeating for many generations

This is **actual machine learning** - the weights improve over time through evolution!

## Quick Start

### Fast Test (2-3 minutes)
```bash
# Quick test: 10 generations, small population
python train_ga.py --quick

# WITH VISUALIZATION - Watch evolution in real-time! 📊
python train_ga.py --quick --visualize
```

### Real Training (1-2 hours)
```bash
# 50 generations, 50 individuals, 5 games each
python train_ga.py --generations 50

# WITH VISUALIZATION - See the magic happen! ✨
python train_ga.py --generations 50 --visualize
```

### High-Quality Training (overnight)
```bash
# 200 generations for best results
python train_ga.py --generations 200 --population 80 --games 10

# WITH VISUALIZATION - Track long-term evolution! 📈
python train_ga.py --generations 200 --visualize
```

### With Lookahead (slower but better)
```bash
# Use lookahead during evaluation (10× slower)
python train_ga.py --generations 50 --lookahead --visualize
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--generations` `-g` | Number of generations | 50 |
| `--population` `-p` | Population size | 50 |
| `--games` | Games per fitness evaluation | 5 |
| `--lookahead` | Enable one-piece lookahead | OFF |
| `--visualize` `-v` | **Show real-time graph!** 📊 | OFF |
| `--seeds` | Seed with 4 known good strategies | OFF (pure evolution) |
| `--no-save-every` | Save only every 10 gens | OFF (saves every gen) |
| `--quick` | Quick test mode | OFF |

## 🧪 Pure Evolution vs Seeded Training

### Pure Evolution (Default)
```bash
# Start with completely random weights
python train_ga.py --generations 50
```

**Characteristics:**
- ✅ Tests if GA can discover strategies from scratch
- ✅ True evolutionary approach
- ✅ May discover novel strategies
- ⏱️ Slower convergence (starts at ~10-100 lines)
- 🎲 Higher variance in results

### Seeded Training
```bash
# Start with 4 known good strategies
python train_ga.py --generations 50 --seeds
```

**Seed Strategies (4 individuals):**
1. **Lee (2013)** - ~513 lines (proven GA-optimized)
2. **Defensive** - ~1,000 lines (high hole penalty)
3. **Aggressive** - Unknown (prioritizes line clears)
4. **Balanced** - Unknown (middle ground)

**Characteristics:**
- ✅ Faster convergence (starts at ~513-1,000 lines)
- ✅ Guaranteed baseline performance
- ✅ Explores multiple strategic directions
- ⚠️ May get stuck in local optima
- ⚠️ Less exploration of novel approaches

### Which Should You Use?

**Use Pure Evolution (default) when:**
- 🔬 You want to test if GA can discover from scratch
- 🎓 You're researching evolutionary algorithms
- 🆕 You want to find novel strategies
- ⏰ You have time for longer training

**Use Seeded (`--seeds`) when:**
- ⚡ You want faster convergence
- 🎯 You want guaranteed good results
- 📈 You're building on proven strategies
- ⏱️ You have limited training time

## 📊 Visualization (NEW!)

Watch evolution happen in real-time with matplotlib graphs!

### Setup
```bash
pip install matplotlib
```

### What You'll See

Five live-updating plots in a window (3×2 grid layout):

**Top Plot - Fitness Evolution (full width):**
- 🟢 **Green line**: Best individual each generation (going up!)
- 🔵 **Blue line**: Population average
- **Shaded area**: Range from worst to best
- **Title**: Shows current best fitness

**Middle Left - Weight Evolution Over Time:**
- 🔴 **Red**: height weight
- 🟢 **Green**: lines weight
- 🟠 **Orange**: holes weight
- 🟣 **Purple**: bumpiness weight
- Watch weights converge as GA finds optimal values!

**Middle Right - Current Generation Stats:**
- 📊 **Bar chart** showing Best/Average/Worst for current generation
- Green (Best), Blue (Average), Red (Worst)
- Values labeled on each bar

**Bottom Left - Current Best Weights:**
- 📊 **Bar chart** showing the 4 weight values from current best individual
- Color-coded: Red (height), Green (lines), Orange (holes), Purple (bumpiness)
- Shows both positive and negative weights clearly with zero line

**Bottom Right - Weight Change from Generation 1:**
- 📊 **Bar chart** showing how much each weight has changed since generation 1
- Blue bars = weight increased, Orange bars = weight decreased
- Helps you see which weights are evolving most!

### Example Output
```
🧬  GENETIC ALGORITHM - TETRIS WEIGHT OPTIMIZATION
══════════════════════════════════════════════════════════════════════

Population size: 50
Games per individual: 5
Lookahead: OFF
Generations: 50
Visualization: ON 📊

📊 Real-time visualization enabled!
```

A matplotlib window opens showing two graphs that update after each generation!

### Saved Graph

After training completes, the final graph is automatically saved as:
- **`ga_evolution.png`** - Publication-quality image of evolution

Perfect for:
- Understanding GA behavior
- Verifying convergence
- Presentations and reports
- Comparing different runs

## How It Works

### 1. Initial Population

The GA starts with a mix of:
- **Known good weights** (Lee 2013, defensive, etc.) - seeds
- **Random weights** - exploration

### 2. Fitness Evaluation

Each individual plays multiple games, and fitness = average lines cleared.

### 3. Selection

**Tournament selection**: Randomly pick 5 individuals, keep the best one.

### 4. Crossover (70% of offspring)

Combine two parents by randomly picking each weight from either parent:
```
Parent 1: height=-0.6, lines=0.7, holes=-0.4, bumpiness=-0.2
Parent 2: height=-0.5, lines=0.8, holes=-0.6, bumpiness=-0.3
         ↓ Random mix ↓
Offspring: height=-0.5, lines=0.7, holes=-0.6, bumpiness=-0.2
```

### 5. Mutation (20% chance per weight)

Add random noise to explore new solutions:
```
Before: height=-0.510066
After:  height=-0.483221  (noise added)
```

### 6. Elitism

Top 5 individuals always survive unchanged to preserve good solutions.

## What You'll See

```
🧬  GENETIC ALGORITHM - TETRIS WEIGHT OPTIMIZATION
══════════════════════════════════════════════════════════════════════

Population size: 50
Games per individual: 5
Lookahead: OFF
Generations: 50

══════════════════════════════════════════════════════════════════════

Generation 1/50
══════════════════════════════════════════════════════════════════════
  Evaluating individual 50/50...

  📊 Generation 1 Results:
     Best:    542.0 lines
     Average: 312.5 lines
     Worst:   89.0 lines

  🏆 Best Ever: 542.0 lines

  ⏱️  Time: 45.3s this gen, 45.3s total

  🔬 Best Weights (Gen 1):
     height      : -0.510066
     lines       : +0.760666
     holes       : -0.356630
     bumpiness   : -0.184483

  💾 Checkpoint saved: ga_checkpoint_gen10.json

...

Generation 50/50
══════════════════════════════════════════════════════════════════════

  📊 Generation 50 Results:
     Best:    1842.0 lines
     Average: 1356.2 lines
     Worst:   892.0 lines

  🏆 Best Ever: 1842.0 lines

🎉  GENETIC ALGORITHM COMPLETE!

✅ Done! Best weights saved to ga_final_results.json
```

## Expected Results

| Generations | Time | Expected Fitness | Quality |
|-------------|------|------------------|---------|
| 10 (quick) | 5-10 min | 800-1,200 lines | Baseline |
| 50 | 1-2 hours | 1,500-2,500 lines | Good |
| 100 | 2-4 hours | 2,000-4,000 lines | Very good |
| 200 | 4-8 hours | 3,000-6,000 lines | Excellent |
| 500+ | 1-2 days | 5,000-10,000 lines | World-class |

With `--lookahead`, results can be 5-10× better but training is 10× slower.

## Using Your Trained Weights

After training completes, the best model is automatically saved to `best_model.json` (plus a copy in the log directory).

### ✨ Easy Way: Use `play_best_model.py`

**This is the easiest way to test your trained model!**

```bash
# Play 10 games with your trained weights
python play_best_model.py --games 10

# Play 5 games and compare to default weights
python play_best_model.py --compare

# Watch one game in slow motion
python play_best_model.py --watch

# Use lookahead (if trained with lookahead)
python play_best_model.py --games 10 --lookahead
```

**What it does:**
- ✅ Automatically loads `best_model.json`
- ✅ Shows model info (fitness, generation, weights)
- ✅ Runs benchmarks and statistics
- ✅ Provides ready-to-use weight strings

### Manual Method: Use weights directly

If you want to use the weights manually:

```bash
# Format: --weights="height,lines,holes,bumpiness"
python src/main.py --weights="-0.623,0.812,-0.734,-0.245" --games 10

# With lookahead
python src/main.py --weights="-0.623,0.812,-0.734,-0.245" --lookahead
```

**Tip**: The script `play_best_model.py` prints the exact command for you!

## Resuming Training

Checkpoints are saved every 10 generations. You can use these to:
1. See progress over time
2. Resume if training is interrupted
3. Compare different runs

## Tips for Best Results

### 1. **More Games = More Accurate**
```bash
python train_ga.py --games 10  # More stable but slower
```

### 2. **Larger Population = More Exploration**
```bash
python train_ga.py --population 100  # Explores more solutions
```

### 3. **More Generations = Better Optimization**
```bash
python train_ga.py --generations 200  # Let evolution do its magic
```

### 4. **Use Lookahead for Best Results**
```bash
python train_ga.py --lookahead --generations 100
# Warning: 10× slower! Use for final training run.
```

### 5. **Quick Test First**
```bash
# Always test with --quick first to verify setup
python train_ga.py --quick
```

## Understanding the Output

**Best**: Highest fitness in this generation
**Average**: Mean fitness of all individuals
**Worst**: Lowest fitness in this generation

**Best Ever**: Best fitness found across all generations (this is what we're optimizing!)

## GA Parameters (Tunable)

You can edit `train_ga.py` to adjust:

```python
self.mutation_rate = 0.2        # 20% chance to mutate
self.mutation_strength = 0.3    # How much noise to add
self.crossover_rate = 0.7       # 70% offspring from crossover
self.elite_size = 5             # Keep top 5 unchanged
self.tournament_size = 5        # Tournament selection size
```

**Higher mutation** = more exploration, less exploitation
**Lower mutation** = refine existing solutions

## Weight Bounds (Search Space)

The GA explores weights within these bounds:

```python
self.bounds = {
    'height': (-2.0, 0.0),      # Always negative (minimize)
    'lines': (0.0, 2.0),        # Always positive (maximize)
    'holes': (-10.0, 0.0),      # Always negative (minimize) - EXPANDED RANGE!
    'bumpiness': (-2.0, 0.0)    # Always negative (minimize)
}
```

### Why Holes Has Extended Range (-10.0)

**Research Finding**: The holes weight is the **most impactful feature** in Tetris AI!

- **Dellacherie's research**: Optimal holes weight around **-24.04** (achieves 660,000 lines!)
- **GA observations**: After 66 generations, GA pushed holes to -2.0 boundary (5,678 lines)
- **Conclusion**: GA was hitting the constraint - needed more room to explore

**Extended range (-10.0) allows GA to:**
- ✅ Discover more aggressive hole-avoidance strategies
- ✅ Match research findings (holes should be heavily penalized)
- ✅ Unlock 10-100× performance improvements
- ✅ Explore strategies that prioritize survival over line clears

**Typical evolved values**:
- Early generations: holes ≈ -0.3 to -0.8 (~500-1,000 lines)
- Mid generations: holes ≈ -1.5 to -3.0 (~2,000-4,000 lines)
- Late generations: holes ≈ -3.0 to -8.0 (~5,000-10,000 lines)
- Research optimum: holes ≈ -24.0 (~660,000 lines with advanced features)

### Boundary Hitting

**How to detect**: If a weight consistently stays at the boundary (e.g., holes = -10.0), it may need more range.

**What to do**: Expand the bound and retrain to let GA explore further.

## Comparison to Current Weights

| Weights | Source | Lines | Method |
|---------|--------|-------|--------|
| Lee (2013) | GA training | 513 | Genetic Algorithm |
| Defensive | Manual tuning | 1,000+ | Hand-crafted |
| **Your GA** | This script | ??? | **YOU TRAINED IT!** |

Will your evolved weights beat the hand-tuned ones? Let's find out! 🏆

## Troubleshooting

### Training is too slow
- Reduce `--games` (less accurate but faster)
- Reduce `--population` (less exploration)
- Don't use `--lookahead` (10× faster)

### Results plateau early
- Increase `--population` (more diversity)
- Increase mutation rate in code
- Train longer (`--generations 200`)

### Weights are unstable
- Increase `--games` (more reliable fitness)
- Increase elite_size in code

## What's Next?

After GA training, you could:
1. **Phase 4: Cross-Entropy Method** - Even more sophisticated optimization
2. **Add Dellacherie features** - 6 more strategic features
3. **Multi-objective GA** - Optimize for speed AND lines
4. **Co-evolution** - Evolve the game difficulty too!

---

**Ready to evolve your AI?** 🧬

```bash
python train_ga.py --quick
```

Watch those weights evolve in real-time!
