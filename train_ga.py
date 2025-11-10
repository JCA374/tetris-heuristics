#!/usr/bin/env python3
"""
Genetic Algorithm for Tetris Weight Optimization

Uses a genetic algorithm to evolve optimal weights for the heuristic evaluation function.
Each "individual" is a set of 4 weights (height, lines, holes, bumpiness).

Process:
1. Create random population of weight sets
2. Evaluate fitness by playing Tetris games
3. Select best performers (tournament selection)
4. Create offspring through crossover and mutation
5. Repeat for many generations

Expected results:
- 50-100 generations: Competitive weights
- 200-500 generations: High-quality weights (1-5M lines)
"""

import random
import sys
import os
import time
import json
from collections import defaultdict

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tetris_game import TetrisGame
from tetris_ai import TetrisAI

# Try to import matplotlib for visualization
try:
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    from matplotlib.patches import Rectangle
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class GeneticAlgorithm:
    """Genetic Algorithm for evolving Tetris AI weights."""

    def __init__(self, population_size=50, games_per_individual=5, use_lookahead=False):
        """
        Initialize GA.

        Args:
            population_size: Number of individuals in population
            games_per_individual: Games to play for fitness evaluation
            use_lookahead: Enable one-piece lookahead during evaluation
        """
        self.population_size = population_size
        self.games_per_individual = games_per_individual
        self.use_lookahead = use_lookahead
        self.generation = 0

        # GA parameters
        self.mutation_rate = 0.2  # 20% chance to mutate
        self.mutation_strength = 0.3  # How much to mutate
        self.crossover_rate = 0.7  # 70% of offspring from crossover
        self.elite_size = 5  # Keep top 5 unchanged
        self.tournament_size = 5  # Tournament selection size

        # Weight bounds (reasonable ranges)
        self.bounds = {
            'height': (-2.0, 0.0),      # Always negative (minimize)
            'lines': (0.0, 2.0),        # Always positive (maximize)
            'holes': (-2.0, 0.0),       # Always negative (minimize)
            'bumpiness': (-2.0, 0.0)    # Always negative (minimize)
        }

        # Statistics
        self.best_ever_fitness = 0
        self.best_ever_weights = None
        self.history = []

    def create_random_individual(self):
        """Create a random set of weights within bounds."""
        weights = {}
        for feature, (low, high) in self.bounds.items():
            weights[feature] = random.uniform(low, high)
        return weights

    def create_initial_population(self):
        """Create initial random population with some seeded good weights."""
        population = []

        # Add known good weights as seeds
        seeds = [
            # Lee (2013) - our current default
            {'height': -0.510066, 'lines': 0.760666, 'holes': -0.35663, 'bumpiness': -0.184483},
            # Defensive strategy
            {'height': -0.600000, 'lines': 0.500000, 'holes': -0.800000, 'bumpiness': -0.300000},
            # Aggressive (prioritize lines)
            {'height': -0.400000, 'lines': 1.000000, 'holes': -0.300000, 'bumpiness': -0.150000},
            # Balanced
            {'height': -0.550000, 'lines': 0.650000, 'holes': -0.550000, 'bumpiness': -0.250000},
        ]

        for seed in seeds:
            if len(population) < self.population_size:
                population.append(seed)

        # Fill rest with random
        while len(population) < self.population_size:
            population.append(self.create_random_individual())

        return population

    def evaluate_fitness(self, weights):
        """
        Evaluate fitness by playing multiple games.

        Args:
            weights: Dict of weights to evaluate

        Returns:
            Average lines cleared (fitness score)
        """
        ai = TetrisAI(weights=weights)
        total_lines = 0

        for _ in range(self.games_per_individual):
            game = TetrisGame()
            ai.play_game(game, use_lookahead=self.use_lookahead)
            total_lines += game.lines_cleared

        avg_lines = total_lines / self.games_per_individual
        return avg_lines

    def tournament_selection(self, population, fitnesses):
        """
        Select an individual using tournament selection.

        Args:
            population: List of weight dicts
            fitnesses: List of fitness scores

        Returns:
            Selected individual (weights dict)
        """
        # Randomly select tournament_size individuals
        tournament_indices = random.sample(range(len(population)), self.tournament_size)

        # Find best in tournament
        best_idx = max(tournament_indices, key=lambda i: fitnesses[i])
        return population[best_idx].copy()

    def crossover(self, parent1, parent2):
        """
        Create offspring by combining two parents.

        Uses uniform crossover - randomly pick each weight from either parent.

        Args:
            parent1: First parent weights dict
            parent2: Second parent weights dict

        Returns:
            Offspring weights dict
        """
        offspring = {}
        for feature in parent1.keys():
            # Randomly choose from which parent to inherit
            if random.random() < 0.5:
                offspring[feature] = parent1[feature]
            else:
                offspring[feature] = parent2[feature]
        return offspring

    def mutate(self, weights):
        """
        Mutate weights by adding random noise.

        Args:
            weights: Weights dict to mutate

        Returns:
            Mutated weights dict
        """
        mutated = weights.copy()

        for feature in mutated.keys():
            if random.random() < self.mutation_rate:
                # Add random noise
                noise = random.gauss(0, self.mutation_strength)
                mutated[feature] += noise

                # Clamp to bounds
                low, high = self.bounds[feature]
                mutated[feature] = max(low, min(high, mutated[feature]))

        return mutated

    def evolve_generation(self, population, fitnesses):
        """
        Create next generation through selection, crossover, and mutation.

        Args:
            population: Current population
            fitnesses: Fitness scores for current population

        Returns:
            New population
        """
        # Sort by fitness
        sorted_pop = [x for _, x in sorted(zip(fitnesses, population), key=lambda pair: pair[0], reverse=True)]

        new_population = []

        # Elitism - keep best individuals unchanged
        for i in range(self.elite_size):
            new_population.append(sorted_pop[i].copy())

        # Create rest through crossover and mutation
        while len(new_population) < self.population_size:
            if random.random() < self.crossover_rate:
                # Crossover
                parent1 = self.tournament_selection(population, fitnesses)
                parent2 = self.tournament_selection(population, fitnesses)
                offspring = self.crossover(parent1, parent2)
            else:
                # Just select one parent
                offspring = self.tournament_selection(population, fitnesses)

            # Mutate
            offspring = self.mutate(offspring)
            new_population.append(offspring)

        return new_population

    def init_visualization(self):
        """Initialize matplotlib figure for real-time visualization."""
        if not MATPLOTLIB_AVAILABLE:
            return None

        plt.ion()  # Turn on interactive mode
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

        # Top plot: Fitness over generations
        ax1.set_xlabel('Generation')
        ax1.set_ylabel('Lines Cleared')
        ax1.set_title('🧬 Genetic Algorithm Evolution')
        ax1.grid(True, alpha=0.3)

        # Bottom plot: Weight evolution
        ax2.set_xlabel('Generation')
        ax2.set_ylabel('Weight Value')
        ax2.set_title('Weight Evolution Over Time')
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        return fig, ax1, ax2

    def update_visualization(self, fig, ax1, ax2):
        """Update the visualization with current generation data."""
        if not MATPLOTLIB_AVAILABLE or not self.history:
            return

        generations = [h['generation'] for h in self.history]
        max_fitness = [h['max_fitness'] for h in self.history]
        avg_fitness = [h['avg_fitness'] for h in self.history]
        min_fitness = [h['min_fitness'] for h in self.history]

        # Clear and redraw fitness plot
        ax1.clear()
        ax1.plot(generations, max_fitness, 'g-', linewidth=2, label='Best', marker='o')
        ax1.plot(generations, avg_fitness, 'b-', linewidth=2, label='Average')
        ax1.fill_between(generations, min_fitness, max_fitness, alpha=0.2, color='blue')
        ax1.set_xlabel('Generation')
        ax1.set_ylabel('Lines Cleared')
        ax1.set_title(f'🧬 Evolution Progress (Best: {max(max_fitness):.0f} lines)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Weight evolution plot
        ax2.clear()
        weight_names = ['height', 'lines', 'holes', 'bumpiness']
        colors = ['red', 'green', 'orange', 'purple']

        for weight_name, color in zip(weight_names, colors):
            values = [h['best_weights'][weight_name] for h in self.history]
            ax2.plot(generations, values, color=color, linewidth=2, label=weight_name, marker='.')

        ax2.set_xlabel('Generation')
        ax2.set_ylabel('Weight Value')
        ax2.set_title('Weight Evolution')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='black', linestyle='--', alpha=0.3)

        plt.tight_layout()
        plt.pause(0.01)  # Small pause to update display

    def save_visualization(self, filename='ga_evolution.png'):
        """Save the final visualization to a file."""
        if not MATPLOTLIB_AVAILABLE:
            return

        plt.ioff()  # Turn off interactive mode
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"\n📊 Evolution graph saved: {filename}")

    def run(self, generations=100, verbose=True, save_checkpoints=True, visualize=False):
        """
        Run the genetic algorithm.

        Args:
            generations: Number of generations to evolve
            verbose: Print progress
            save_checkpoints: Save best weights periodically
        """
        if verbose:
            print("=" * 70)
            print("🧬  GENETIC ALGORITHM - TETRIS WEIGHT OPTIMIZATION")
            print("=" * 70)
            print(f"\nPopulation size: {self.population_size}")
            print(f"Games per individual: {self.games_per_individual}")
            print(f"Lookahead: {'ON' if self.use_lookahead else 'OFF'}")
            print(f"Generations: {generations}")
            print(f"Visualization: {'ON 📊' if visualize else 'OFF'}")
            print(f"\nMutation rate: {self.mutation_rate}")
            print(f"Mutation strength: {self.mutation_strength}")
            print(f"Crossover rate: {self.crossover_rate}")
            print(f"Elite size: {self.elite_size}")
            print(f"Tournament size: {self.tournament_size}")
            print("\n" + "=" * 70)
            print("\nInitializing population...")

        # Initialize visualization if requested
        viz_data = None
        if visualize:
            if not MATPLOTLIB_AVAILABLE:
                print("\n⚠️  Warning: matplotlib not installed. Install with: pip install matplotlib")
                print("    Continuing without visualization...")
            else:
                viz_data = self.init_visualization()
                if verbose:
                    print("📊 Real-time visualization enabled!")

        # Create initial population
        population = self.create_initial_population()

        start_time = time.time()

        for gen in range(generations):
            self.generation = gen
            gen_start = time.time()

            if verbose:
                print(f"\n{'='*70}")
                print(f"Generation {gen + 1}/{generations}")
                print(f"{'='*70}")

            # Evaluate fitness for all individuals
            fitnesses = []
            for i, weights in enumerate(population):
                if verbose:
                    print(f"  Evaluating individual {i + 1}/{self.population_size}...", end='\r')

                fitness = self.evaluate_fitness(weights)
                fitnesses.append(fitness)

            # Statistics
            avg_fitness = sum(fitnesses) / len(fitnesses)
            max_fitness = max(fitnesses)
            min_fitness = min(fitnesses)
            best_idx = fitnesses.index(max_fitness)
            best_weights = population[best_idx]

            # Update best ever
            if max_fitness > self.best_ever_fitness:
                self.best_ever_fitness = max_fitness
                self.best_ever_weights = best_weights.copy()

            # Save to history
            self.history.append({
                'generation': gen + 1,
                'avg_fitness': avg_fitness,
                'max_fitness': max_fitness,
                'min_fitness': min_fitness,
                'best_weights': best_weights.copy()
            })

            gen_time = time.time() - gen_start
            total_time = time.time() - start_time

            if verbose:
                print(f"\n  📊 Generation {gen + 1} Results:")
                print(f"     Best:    {max_fitness:.1f} lines")
                print(f"     Average: {avg_fitness:.1f} lines")
                print(f"     Worst:   {min_fitness:.1f} lines")
                print(f"\n  🏆 Best Ever: {self.best_ever_fitness:.1f} lines")
                print(f"\n  ⏱️  Time: {gen_time:.1f}s this gen, {total_time:.1f}s total")

                print(f"\n  🔬 Best Weights (Gen {gen + 1}):")
                for feature, value in best_weights.items():
                    print(f"     {feature:12s}: {value:+.6f}")

            # Update visualization
            if viz_data:
                fig, ax1, ax2 = viz_data
                self.update_visualization(fig, ax1, ax2)

            # Save checkpoint every 10 generations
            if save_checkpoints and (gen + 1) % 10 == 0:
                self.save_checkpoint(f"ga_checkpoint_gen{gen + 1}.json")

            # Evolve to next generation
            if gen < generations - 1:  # Don't evolve after last generation
                population = self.evolve_generation(population, fitnesses)

        # Final summary
        if verbose:
            print("\n" + "=" * 70)
            print("🎉  GENETIC ALGORITHM COMPLETE!")
            print("=" * 70)
            print(f"\nTotal time: {time.time() - start_time:.1f}s")
            print(f"\n🏆 BEST EVER RESULT:")
            print(f"   Fitness: {self.best_ever_fitness:.1f} lines")
            print(f"\n   Weights:")
            for feature, value in self.best_ever_weights.items():
                print(f"     {feature:12s}: {value:+.6f}")

        # Save final visualization
        if viz_data:
            self.save_visualization('ga_evolution.png')
            if verbose:
                print("\n💡 Tip: Check ga_evolution.png to see the evolution graph!")

        return self.best_ever_weights

    def save_checkpoint(self, filename):
        """Save current state to JSON file."""
        data = {
            'generation': self.generation,
            'best_ever_fitness': self.best_ever_fitness,
            'best_ever_weights': self.best_ever_weights,
            'history': self.history,
            'parameters': {
                'population_size': self.population_size,
                'games_per_individual': self.games_per_individual,
                'use_lookahead': self.use_lookahead,
                'mutation_rate': self.mutation_rate,
                'mutation_strength': self.mutation_strength,
                'crossover_rate': self.crossover_rate,
            }
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\n  💾 Checkpoint saved: {filename}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Genetic Algorithm for Tetris Weight Optimization')
    parser.add_argument('--generations', '-g', type=int, default=50,
                        help='Number of generations (default: 50)')
    parser.add_argument('--population', '-p', type=int, default=50,
                        help='Population size (default: 50)')
    parser.add_argument('--games', type=int, default=5,
                        help='Games per individual for fitness evaluation (default: 5)')
    parser.add_argument('--lookahead', action='store_true',
                        help='Enable one-piece lookahead (much slower but better results)')
    parser.add_argument('--visualize', '-v', action='store_true',
                        help='Show real-time evolution graph (requires matplotlib)')
    parser.add_argument('--quick', action='store_true',
                        help='Quick test: 10 gens, 20 pop, 3 games')

    args = parser.parse_args()

    # Quick test mode
    if args.quick:
        args.generations = 10
        args.population = 20
        args.games = 3
        print("\n🚀 QUICK TEST MODE")

    # Create and run GA
    ga = GeneticAlgorithm(
        population_size=args.population,
        games_per_individual=args.games,
        use_lookahead=args.lookahead
    )

    best_weights = ga.run(generations=args.generations, visualize=args.visualize)

    # Save final results
    ga.save_checkpoint('ga_final_results.json')

    print("\n✅ Done! Best weights saved to ga_final_results.json")
    print("\nTo use these weights:")
    print(f"  python src/main.py --weights {best_weights['height']:.6f},{best_weights['lines']:.6f},{best_weights['holes']:.6f},{best_weights['bumpiness']:.6f}")


if __name__ == '__main__':
    main()
