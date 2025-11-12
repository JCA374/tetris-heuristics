#!/usr/bin/env python3
"""
GA Performance Benchmark - Find Optimal Population and Workers

Tests different combinations of:
- Population sizes (10, 20, 30, 50, 80, 100)
- Worker counts (1, 2, 4, 8, auto)
- With/without parallelization

Measures:
- Time per generation
- Convergence rate (fitness improvement)
- CPU utilization
- Final fitness achieved

Run with:
    python tests/test_ga_performance.py --quick      # Fast test
    python tests/test_ga_performance.py --full       # Comprehensive test
    python tests/test_ga_performance.py --workers    # Test parallelization only
"""

import sys
import os
import time
import json
import multiprocessing as mp
from datetime import datetime
from statistics import mean, stdev

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tetris_game import TetrisGame
from tetris_ai import TetrisAI

# Add parent directory for train_ga
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from train_ga import GeneticAlgorithm


def evaluate_fitness_worker(args):
    """
    Worker function for parallel fitness evaluation.

    Args:
        args: Tuple of (weights, games_per_individual, use_lookahead)

    Returns:
        Average lines cleared
    """
    weights, games_per_individual, use_lookahead = args
    ai = TetrisAI(weights=weights)
    total_lines = 0

    for _ in range(games_per_individual):
        game = TetrisGame()
        ai.play_game(game, use_lookahead=use_lookahead)
        total_lines += game.lines_cleared

    return total_lines / games_per_individual


class ParallelGA(GeneticAlgorithm):
    """GA with optional multiprocessing support."""

    def __init__(self, population_size=50, games_per_individual=5,
                 use_lookahead=False, workers=1):
        """
        Initialize GA with worker support.

        Args:
            workers: Number of parallel workers (1 = no parallelization)
        """
        super().__init__(population_size, games_per_individual, use_lookahead)
        self.workers = workers
        self.pool = None

    def evaluate_population(self, population):
        """
        Evaluate entire population (with optional parallelization).

        Args:
            population: List of weight dicts

        Returns:
            List of fitness scores
        """
        if self.workers <= 1:
            # Serial evaluation (original method)
            return [self.evaluate_fitness(ind) for ind in population]

        # Parallel evaluation
        if self.pool is None:
            self.pool = mp.Pool(processes=self.workers)

        # Prepare arguments for workers
        args_list = [
            (ind, self.games_per_individual, self.use_lookahead)
            for ind in population
        ]

        fitnesses = self.pool.map(evaluate_fitness_worker, args_list)
        return fitnesses

    def cleanup(self):
        """Close multiprocessing pool."""
        if self.pool is not None:
            self.pool.close()
            self.pool.join()
            self.pool = None


def benchmark_population_size(pop_size, generations=10, games=3, workers=1):
    """
    Benchmark a specific population size.

    Args:
        pop_size: Population size to test
        generations: Number of generations
        games: Games per individual
        workers: Number of parallel workers

    Returns:
        Dict with benchmark results
    """
    print(f"\n{'='*70}")
    print(f"Testing Population={pop_size}, Workers={workers}")
    print(f"{'='*70}")

    ga = ParallelGA(
        population_size=pop_size,
        games_per_individual=games,
        use_lookahead=False,
        workers=workers
    )

    # Create initial population
    population = ga.create_initial_population(use_seeds=False)

    # Track metrics
    gen_times = []
    fitness_history = []
    best_fitness_history = []

    overall_start = time.time()

    for gen in range(generations):
        gen_start = time.time()

        # Evaluate fitness
        fitnesses = ga.evaluate_population(population)

        # Track statistics
        max_fitness = max(fitnesses)
        avg_fitness = mean(fitnesses)
        min_fitness = min(fitnesses)

        fitness_history.append(avg_fitness)
        best_fitness_history.append(max_fitness)

        gen_time = time.time() - gen_start
        gen_times.append(gen_time)

        print(f"  Gen {gen+1}/{generations}: "
              f"Best={max_fitness:.1f}, Avg={avg_fitness:.1f}, "
              f"Time={gen_time:.2f}s")

        # Evolution (skip on last generation)
        if gen < generations - 1:
            # Selection, crossover, mutation (simplified)
            new_population = []

            # Elitism - keep top 5
            sorted_pop = sorted(zip(population, fitnesses),
                              key=lambda x: x[1], reverse=True)
            new_population.extend([ind for ind, _ in sorted_pop[:5]])

            # Fill rest with tournament selection + crossover
            while len(new_population) < pop_size:
                parent1 = ga.tournament_selection(population, fitnesses)
                parent2 = ga.tournament_selection(population, fitnesses)
                offspring = ga.crossover(parent1, parent2)
                offspring = ga.mutate(offspring)
                new_population.append(offspring)

            population = new_population

    overall_time = time.time() - overall_start

    # Cleanup
    ga.cleanup()

    # Calculate convergence rate (fitness improvement per generation)
    if len(best_fitness_history) > 1:
        convergence_rate = (best_fitness_history[-1] - best_fitness_history[0]) / generations
    else:
        convergence_rate = 0

    results = {
        'population_size': pop_size,
        'workers': workers,
        'generations': generations,
        'total_time': overall_time,
        'avg_time_per_gen': mean(gen_times),
        'std_time_per_gen': stdev(gen_times) if len(gen_times) > 1 else 0,
        'final_best_fitness': best_fitness_history[-1],
        'final_avg_fitness': fitness_history[-1],
        'convergence_rate': convergence_rate,
        'improvement': best_fitness_history[-1] - best_fitness_history[0],
        'evaluations_per_second': (pop_size * generations * games) / overall_time
    }

    return results


def benchmark_workers(pop_size=20, generations=5, games=2):
    """
    Test different worker counts with fixed population.

    Args:
        pop_size: Population size
        generations: Number of generations
        games: Games per individual

    Returns:
        List of benchmark results
    """
    cpu_count = mp.cpu_count()
    worker_counts = [1, 2, 4, min(8, cpu_count)]
    worker_counts = sorted(set(worker_counts))  # Remove duplicates

    print(f"\n{'='*70}")
    print(f"🔬 WORKER BENCHMARKS")
    print(f"{'='*70}")
    print(f"System CPUs: {cpu_count}")
    print(f"Testing workers: {worker_counts}")
    print(f"Population: {pop_size}, Generations: {generations}, Games: {games}")

    results = []
    for workers in worker_counts:
        result = benchmark_population_size(pop_size, generations, games, workers)
        results.append(result)

    return results


def benchmark_populations(worker_count=1, generations=5, games=2):
    """
    Test different population sizes with fixed workers.

    Args:
        worker_count: Number of workers
        generations: Number of generations
        games: Games per individual

    Returns:
        List of benchmark results
    """
    pop_sizes = [10, 20, 30, 50]

    print(f"\n{'='*70}")
    print(f"📊 POPULATION SIZE BENCHMARKS")
    print(f"{'='*70}")
    print(f"Workers: {worker_count}, Generations: {generations}, Games: {games}")

    results = []
    for pop_size in pop_sizes:
        result = benchmark_population_size(pop_size, generations, games, worker_count)
        results.append(result)

    return results


def print_summary(results, benchmark_type="workers"):
    """
    Print formatted summary of benchmark results.

    Args:
        results: List of benchmark result dicts
        benchmark_type: "workers" or "population"
    """
    print(f"\n{'='*70}")
    print(f"📈 SUMMARY - {benchmark_type.upper()} BENCHMARK")
    print(f"{'='*70}\n")

    if benchmark_type == "workers":
        # Workers benchmark
        print(f"{'Workers':<8} {'Time/Gen':<12} {'Speedup':<10} {'Final Fitness':<15} {'Eval/sec':<12}")
        print("-" * 70)

        baseline_time = results[0]['avg_time_per_gen']

        for r in results:
            speedup = baseline_time / r['avg_time_per_gen']
            print(f"{r['workers']:<8} "
                  f"{r['avg_time_per_gen']:.2f}s        "
                  f"{speedup:.2f}x      "
                  f"{r['final_best_fitness']:.1f}          "
                  f"{r['evaluations_per_second']:.1f}")

        # Recommendations
        print(f"\n{'='*70}")
        print("💡 RECOMMENDATIONS:")
        print(f"{'='*70}")

        # Find best speedup
        best_speedup = max(results, key=lambda x: baseline_time / x['avg_time_per_gen'])
        print(f"✅ Best Speedup: {best_speedup['workers']} workers "
              f"({baseline_time / best_speedup['avg_time_per_gen']:.2f}x faster)")

        # Efficiency (speedup / workers)
        best_efficiency = max(results,
                            key=lambda x: (baseline_time / x['avg_time_per_gen']) / x['workers'])
        efficiency = (baseline_time / best_efficiency['avg_time_per_gen']) / best_efficiency['workers']
        print(f"✅ Best Efficiency: {best_efficiency['workers']} workers "
              f"({efficiency:.2f}x speedup per worker)")

        # Check if parallelization helps
        if best_speedup['workers'] == 1:
            print("\n⚠️  WARNING: Parallelization shows NO benefit!")
            print("   Recommendation: Use workers=1 (serial mode)")
        else:
            print(f"\n✅ Parallelization helps! Use {best_speedup['workers']} workers for best speed.")

    else:
        # Population benchmark
        print(f"{'Pop Size':<10} {'Time/Gen':<12} {'Final Best':<12} {'Convergence':<14} {'Eval/sec':<12}")
        print("-" * 70)

        for r in results:
            print(f"{r['population_size']:<10} "
                  f"{r['avg_time_per_gen']:.2f}s        "
                  f"{r['final_best_fitness']:.1f}       "
                  f"{r['convergence_rate']:+.1f}/gen     "
                  f"{r['evaluations_per_second']:.1f}")

        # Recommendations
        print(f"\n{'='*70}")
        print("💡 RECOMMENDATIONS:")
        print(f"{'='*70}")

        # Best convergence
        best_convergence = max(results, key=lambda x: x['convergence_rate'])
        print(f"✅ Best Convergence: Population={best_convergence['population_size']} "
              f"({best_convergence['convergence_rate']:+.1f} lines/gen improvement)")

        # Best final fitness
        best_fitness = max(results, key=lambda x: x['final_best_fitness'])
        print(f"✅ Best Final Fitness: Population={best_fitness['population_size']} "
              f"({best_fitness['final_best_fitness']:.1f} lines)")

        # Time efficiency (fitness improvement per minute)
        for r in results:
            r['fitness_per_minute'] = (r['improvement'] * 60) / r['total_time']

        best_time_efficiency = max(results, key=lambda x: x['fitness_per_minute'])
        print(f"✅ Best Time Efficiency: Population={best_time_efficiency['population_size']} "
              f"({best_time_efficiency['fitness_per_minute']:.1f} lines/min improvement)")

        print(f"\n📝 General Guidance:")
        print(f"   • Small population (10-30): Fast testing, less diversity")
        print(f"   • Medium population (30-50): Balanced, recommended for most cases")
        print(f"   • Large population (80-100): Better exploration, slower per generation")


def save_results(results, benchmark_type, filename=None):
    """
    Save benchmark results to JSON.

    Args:
        results: List of benchmark result dicts
        benchmark_type: "workers" or "population"
        filename: Optional custom filename
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_{benchmark_type}_{timestamp}.json"

    filepath = os.path.join("tests", filename)

    data = {
        'benchmark_type': benchmark_type,
        'timestamp': datetime.now().isoformat(),
        'system_info': {
            'cpu_count': mp.cpu_count(),
            'platform': sys.platform
        },
        'results': results
    }

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n💾 Results saved to: {filepath}")


def main():
    """Main entry point for GA performance benchmarks."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Benchmark GA Performance - Find Optimal Settings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/test_ga_performance.py --quick          # Fast test (~2 min)
  python tests/test_ga_performance.py --workers        # Test parallelization (~5 min)
  python tests/test_ga_performance.py --population     # Test population sizes (~10 min)
  python tests/test_ga_performance.py --full           # Complete benchmark (~15 min)
        """
    )

    parser.add_argument('--quick', action='store_true',
                       help='Quick test (3 gens, pop=15, workers=1,2,4) - ~2 min')
    parser.add_argument('--workers', action='store_true',
                       help='Benchmark different worker counts (~5 min)')
    parser.add_argument('--population', action='store_true',
                       help='Benchmark different population sizes (~10 min)')
    parser.add_argument('--full', action='store_true',
                       help='Full benchmark (workers + population) (~15 min)')
    parser.add_argument('--generations', type=int, default=5,
                       help='Generations per test (default: 5)')
    parser.add_argument('--games', type=int, default=2,
                       help='Games per individual (default: 2)')
    parser.add_argument('--save', action='store_true',
                       help='Save results to JSON file')

    args = parser.parse_args()

    # Default: show help if no options
    if not (args.quick or args.workers or args.population or args.full):
        parser.print_help()
        print("\n💡 Tip: Start with --quick to see how it works!")
        return

    print(f"\n{'='*70}")
    print("🔬 GA PERFORMANCE BENCHMARK")
    print(f"{'='*70}")
    print(f"System CPUs: {mp.cpu_count()}")
    print(f"Generations: {args.generations}")
    print(f"Games/individual: {args.games}")
    print(f"{'='*70}\n")

    if args.quick:
        print("🚀 QUICK TEST MODE")
        print("   Testing: Workers=1,2,4 with Population=15")

        results = []
        for workers in [1, 2, 4]:
            result = benchmark_population_size(15, 3, 2, workers)
            results.append(result)

        print_summary(results, "workers")

        if args.save:
            save_results(results, "quick")

    elif args.workers:
        results = benchmark_workers(
            pop_size=30,
            generations=args.generations,
            games=args.games
        )

        print_summary(results, "workers")

        if args.save:
            save_results(results, "workers")

    elif args.population:
        # Determine worker count
        cpu_count = mp.cpu_count()
        workers = min(4, cpu_count) if cpu_count >= 4 else 1

        print(f"Using {workers} workers for population benchmark")

        results = benchmark_populations(
            worker_count=workers,
            generations=args.generations,
            games=args.games
        )

        print_summary(results, "population")

        if args.save:
            save_results(results, "population")

    elif args.full:
        print("🎯 FULL BENCHMARK MODE")
        print("   This will take ~15 minutes...\n")

        # Test workers first
        print("\n" + "="*70)
        print("PHASE 1: WORKER BENCHMARKS")
        print("="*70)

        worker_results = benchmark_workers(
            pop_size=30,
            generations=args.generations,
            games=args.games
        )

        print_summary(worker_results, "workers")

        # Find best worker count
        baseline_time = worker_results[0]['avg_time_per_gen']
        best_workers = max(worker_results,
                          key=lambda x: baseline_time / x['avg_time_per_gen'])['workers']

        print(f"\n✅ Using {best_workers} workers for population benchmark...")

        # Test populations
        print("\n" + "="*70)
        print("PHASE 2: POPULATION BENCHMARKS")
        print("="*70)

        pop_results = benchmark_populations(
            worker_count=best_workers,
            generations=args.generations,
            games=args.games
        )

        print_summary(pop_results, "population")

        # Save both
        if args.save:
            save_results(worker_results, "workers_full")
            save_results(pop_results, "population_full")

        # Final recommendations
        print("\n" + "="*70)
        print("🎯 FINAL RECOMMENDATIONS")
        print("="*70)

        best_pop = max(pop_results, key=lambda x: x['fitness_per_minute'])

        print(f"\n✅ Recommended Configuration:")
        print(f"   python train_ga.py \\")
        print(f"       --population {best_pop['population_size']} \\")
        print(f"       --workers {best_workers} \\")
        print(f"       --generations 100")
        print(f"\n   Expected: ~{best_pop['fitness_per_minute']:.0f} lines/min improvement")
        print(f"   Time estimate: ~{(100 * best_pop['avg_time_per_gen'] / 60):.1f} minutes for 100 generations")


if __name__ == '__main__':
    main()
