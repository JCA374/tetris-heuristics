# GA Performance Benchmarking

This directory contains tests for evaluating and optimizing GA performance.

## test_ga_performance.py

Comprehensive benchmark suite to find optimal GA configuration for your system.

### What It Tests

1. **Worker Count (Parallelization)**
   - Tests 1, 2, 4, 8, and max CPU workers
   - Measures speedup and efficiency
   - Recommends optimal parallelization

2. **Population Size**
   - Tests populations: 10, 20, 30, 50
   - Measures convergence rate and time efficiency
   - Finds best balance of speed vs quality

### Quick Start

```bash
# Fast test (~2 minutes) - Start here!
python tests/test_ga_performance.py --quick

# Test worker parallelization (~5 minutes)
python tests/test_ga_performance.py --workers

# Test population sizes (~10 minutes)
python tests/test_ga_performance.py --population

# Complete benchmark (~15 minutes)
python tests/test_ga_performance.py --full
```

### Understanding Results

#### Worker Benchmarks

```
Workers  Time/Gen    Speedup   Final Fitness  Eval/sec
1        45.2s       1.00x     328.4          22.1
2        24.1s       1.87x     331.2          41.5
4        13.8s       3.27x     329.8          72.5
8        12.4s       3.64x     327.6          80.6
```

**Metrics:**
- **Time/Gen**: Average seconds per generation
- **Speedup**: How much faster vs 1 worker (2.00x = twice as fast)
- **Final Fitness**: Best performance achieved (should be similar across workers)
- **Eval/sec**: Game evaluations per second (higher = faster)

**What to look for:**
- ✅ Speedup should increase with workers (ideally close to worker count)
- ✅ Speedup/Workers > 0.7 = good parallelization efficiency
- ⚠️ If speedup < 1.5x with 4 workers, parallelization may not help

#### Population Benchmarks

```
Pop Size   Time/Gen    Final Best  Convergence  Eval/sec
10         5.2s        284.2       +8.4/gen     57.7
20         10.8s       312.6       +12.1/gen    55.6
30         16.4s       328.4       +15.3/gen    54.9
50         28.1s       346.8       +18.7/gen    53.3
```

**Metrics:**
- **Time/Gen**: Seconds per generation (increases linearly with population)
- **Final Best**: Best fitness achieved (higher = better)
- **Convergence**: Fitness improvement per generation (higher = faster learning)
- **Eval/sec**: Should be roughly constant (slight decrease with overhead)

**What to look for:**
- ✅ Larger populations achieve better final fitness
- ✅ Larger populations have better convergence rates
- ⚠️ Diminishing returns after ~50-80 population

### Recommendations

The script automatically provides recommendations like:

```
💡 RECOMMENDATIONS:
═══════════════════════════════════════════════════

✅ Best Speedup: 4 workers (3.27x faster)
✅ Best Efficiency: 4 workers (0.82x speedup per worker)

✅ Parallelization helps! Use 4 workers for best speed.

---

✅ Best Convergence: Population=50 (+18.7 lines/gen improvement)
✅ Best Final Fitness: Population=50 (346.8 lines)
✅ Best Time Efficiency: Population=30 (56.2 lines/min improvement)

📝 General Guidance:
   • Small population (10-20): Fast testing, less diversity
   • Medium population (30-50): Balanced, recommended for most cases
   • Large population (50+): Better exploration, slower per generation

═══════════════════════════════════════════════════
🎯 FINAL RECOMMENDATIONS
═══════════════════════════════════════════════════

✅ Recommended Configuration:
   python train_ga.py \
       --population 30 \
       --workers 4 \
       --generations 100

   Expected: ~56 lines/min improvement
   Time estimate: ~27.3 minutes for 100 generations
```

### Options

| Option | Description | Time |
|--------|-------------|------|
| `--quick` | Fast test: 3 worker configs, 3 gens, pop=15 | ~2 min |
| `--workers` | Test worker parallelization (1-4/8 workers) | ~5 min |
| `--population` | Test population sizes (10-50) | ~10 min |
| `--full` | Complete benchmark (workers + populations) | ~15 min |
| `--generations N` | Generations per test (default: 5) | Varies |
| `--games N` | Games per evaluation (default: 2) | Varies |
| `--save` | Save results to JSON file | - |

### Interpreting Results for Your System

#### Good Parallelization (Multi-core CPU)
```
Workers=4, Speedup=3.2x → Use parallelization!
Recommendation: Use --workers 4 in train_ga.py
```

#### Poor Parallelization (Limited cores or overhead)
```
Workers=4, Speedup=1.3x → Don't use parallelization
Recommendation: Use --workers 1 (serial mode)
```

#### Population Size Tradeoffs

**Small population (10-20):**
- ⚡ Fast generations
- ⚠️ Less diversity → may miss good solutions
- 👍 Good for: Quick testing, initial experiments

**Medium population (30-50):**
- ⚖️ Balanced speed and quality
- ✅ Good diversity
- 👍 Good for: Most training runs

**Large population (50+):**
- 🐌 Slower generations
- ✅ Better diversity → finds better solutions
- ✅ Better convergence rate
- 👍 Good for: Final high-quality training

### Saving Results

Use `--save` to save benchmark results to JSON:

```bash
python tests/test_ga_performance.py --full --save
```

Creates files in `tests/`:
- `benchmark_workers_full_YYYYMMDD_HHMMSS.json`
- `benchmark_population_full_YYYYMMDD_HHMMSS.json`

JSON format:
```json
{
  "benchmark_type": "workers",
  "timestamp": "2025-11-12T18:30:45.123456",
  "system_info": {
    "cpu_count": 8,
    "platform": "linux"
  },
  "results": [
    {
      "population_size": 30,
      "workers": 4,
      "generations": 10,
      "total_time": 138.4,
      "avg_time_per_gen": 13.8,
      "final_best_fitness": 329.8,
      "convergence_rate": 15.3,
      "evaluations_per_second": 72.5
    }
  ]
}
```

### Note on train_ga.py

**IMPORTANT**: The current `train_ga.py` does NOT have worker/parallelization support built-in yet!

This benchmark script uses a **modified GA class** (`ParallelGA`) that extends the original with multiprocessing support.

If benchmarks show parallelization helps significantly, you can:
1. Copy the `ParallelGA` class to `train_ga.py`
2. Add `--workers` argument to the CLI
3. Use `ga.evaluate_population()` instead of list comprehension

Example integration:
```python
# In train_ga.py main():
parser.add_argument('--workers', type=int, default=1,
                   help='Number of parallel workers (default: 1)')

# Use ParallelGA instead of GeneticAlgorithm:
ga = ParallelGA(
    population_size=args.population,
    games_per_individual=args.games,
    use_lookahead=args.lookahead,
    workers=args.workers  # NEW!
)
```

### Tips

1. **Always run --quick first** to get a feel for your system's performance
2. **Use --save** to keep records of different configurations
3. **Run during low-activity times** for accurate CPU measurements
4. **Compare multiple runs** - results can vary ±10% due to randomness
5. **Consider memory**: Large populations + many workers = high memory usage

### Example Workflow

```bash
# Step 1: Quick test to see baseline
python tests/test_ga_performance.py --quick

# Step 2: If parallelization helps, test workers thoroughly
python tests/test_ga_performance.py --workers --save

# Step 3: Find optimal population size
python tests/test_ga_performance.py --population --save

# Step 4: Use recommendations in actual training
python train_ga.py --population 50 --generations 100  # (when --workers added)
```

### Common Results by System Type

**Laptop (4 cores, 8 threads):**
- Best workers: 4-8
- Speedup: 2.5-3.5x
- Recommended population: 30-50

**Desktop (8+ cores):**
- Best workers: 8-12
- Speedup: 4-6x
- Recommended population: 50-80

**Server (16+ cores):**
- Best workers: 16-24
- Speedup: 8-12x
- Recommended population: 80-100

**Single core / Low memory:**
- Best workers: 1 (serial)
- Speedup: 1.0x
- Recommended population: 20-30
