"""
Genetic algorithm over a named-gene genome.

A genome is a flat dict of genes derived from a policy rule template
(tetris.policy.TEMPLATES):
    '<regime>.<feature>'  weight for that feature in that regime   (float)
    '<regime>.threshold'  switch threshold for a conditional regime (int)

With all 6 features the single model has 6 genes and the 3-regime model 3*6 + 2 = 20
(with the original 4 features: 4 and 14). Features left out are fixed at weight 0.

Noise control (Tetris line counts vary ~10x between games of the same policy):
- Common random numbers: every individual in a generation plays the same
  seeds, so selection compares strategies rather than piece luck.
- Archive: every evaluation of a genome is accumulated, and selection uses the
  accumulated mean; elites survive and are re-evaluated each generation, so a
  lucky genome keeps being tested until its mean converges.
- Final pick: top archive candidates are re-played on separate validation
  seeds and the best validation mean wins.
"""

import json
import os
import random
import statistics
import time
import multiprocessing as mp
from datetime import datetime

from tetris.features import FEATURES
from tetris.policy import Policy, TEMPLATES
from tetris.play import play_game, TRAIN_SEED_BASE, VALIDATION_SEED_BASE

# Weights are scale-invariant, so only the ratios matter; bounds are generous.
WEIGHT_BOUNDS = {
    'height': (-5.0, 0.0),
    'lines': (0.0, 5.0),
    'holes': (-10.0, 0.0),
    'bumpiness': (-5.0, 0.0),
    'wells': (-5.0, 0.0),
    'hole_depth': (-5.0, 0.0),
}
THRESHOLD_BOUNDS = {
    'holes': (1, 10),
    'max_height': (4, 18),
    'agg_height': (10, 150),
    'bumpiness': (2, 30),
    'wells': (1, 30),
    'hole_depth': (1, 40),
}


# --- genome <-> policy ---------------------------------------------------------

def gene_spec(template, features=FEATURES):
    """{gene_name: (low, high, is_int)} for a rule template and feature subset."""
    spec = {}
    for rule in template:
        name = rule['name']
        if 'stat' in rule:
            low, high = THRESHOLD_BOUNDS[rule['stat']]
            spec[f'{name}.threshold'] = (low, high, True)
        for feature in features:
            low, high = WEIGHT_BOUNDS[feature]
            spec[f'{name}.{feature}'] = (low, high, False)
    return spec


def genome_to_policy(template, genome, meta=None):
    rules = []
    weights = {}
    for rule in template:
        rule = dict(rule)
        name = rule['name']
        if 'stat' in rule:
            rule['threshold'] = int(genome[f'{name}.threshold'])
        rules.append(rule)
        weights[name] = {f: genome.get(f'{name}.{f}', 0.0) for f in FEATURES}
    return Policy(rules, weights, meta)


def genome_from_policy(template, spec, policy, rng):
    """
    Seed genome from an existing model. Regimes the model doesn't have get the
    model's default (last-rule) weights, so a single model copied into a regime
    template behaves exactly like the single model. Thresholds come from the
    model when present, otherwise random.
    """
    default = policy.weights[policy.rules[-1]['name']]
    model_rules = {r['name']: r for r in policy.rules}
    genome = {}
    for rule in template:
        name = rule['name']
        w = policy.weights.get(name, default)
        for f in FEATURES:
            if f'{name}.{f}' in spec:
                genome[f'{name}.{f}'] = clamp(spec[f'{name}.{f}'], w[f])
        if 'stat' in rule:
            src = model_rules.get(name)
            low, high, _ = spec[f'{name}.threshold']
            t = src['threshold'] if src and 'threshold' in src else rng.randint(low, high)
            genome[f'{name}.threshold'] = clamp(spec[f'{name}.threshold'], t)
    return genome


def clamp(bounds, value):
    low, high, is_int = bounds
    value = max(low, min(high, value))
    return int(round(value)) if is_int else value


def genome_key(genome):
    return tuple(sorted((k, round(v, 9)) for k, v in genome.items()))


# --- worker -------------------------------------------------------------------

def _play_task(args):
    index, template, genome, seed, max_pieces, lookahead, randomizer = args
    policy = genome_to_policy(template, genome)
    result = play_game(policy, seed=seed, max_pieces=max_pieces,
                       lookahead=lookahead, randomizer=randomizer)
    return index, result


# --- GA -----------------------------------------------------------------------

class GeneticAlgorithm:
    def __init__(self, template_name='single', population_size=50, games=5,
                 max_pieces=20000, lookahead=False, randomizer='random', workers=1,
                 init_policy=None, rng_seed=None, validation_games=30, candidates=5,
                 features=FEATURES, freeze=()):
        """freeze: regime names whose weights stay fixed at the init model's values."""
        self.template_name = template_name
        self.template = TEMPLATES[template_name]
        self.features = tuple(features)
        self.spec = gene_spec(self.template, self.features)
        self.population_size = population_size
        self.games = games
        self.max_pieces = max_pieces
        self.lookahead = lookahead
        self.randomizer = randomizer
        self.workers = workers
        self.init_policy = init_policy
        self.validation_games = validation_games
        self.candidates = candidates
        self.rng = random.Random(rng_seed)
        self.frozen = {}              # gene -> fixed value
        if freeze:
            if init_policy is None:
                raise ValueError('freezing regimes needs an init model')
            unknown = set(freeze) - {r['name'] for r in self.template}
            if unknown:
                raise ValueError(f"no such regime in '{template_name}': {', '.join(sorted(unknown))}")
            seed = genome_from_policy(self.template, self.spec, init_policy, random.Random(0))
            self.frozen = {k: v for k, v in seed.items() if k.split('.')[0] in freeze}

        self.mutation_rate = 0.2      # per-gene chance to mutate
        self.mutation_scale = 0.1     # sigma as fraction of the gene's range
        self.crossover_rate = 0.7
        self.elite_size = 5
        self.tournament_size = 5

        self.archive = {}             # genome_key -> {'genome', 'lines': [...]}
        self.history = []
        self.pool = None
        self.run_dir = None

    # -- population -----------------------------------------------------------

    def random_genome(self):
        genome = {}
        for name, (low, high, is_int) in self.spec.items():
            genome[name] = self.rng.randint(low, high) if is_int else self.rng.uniform(low, high)
        genome.update(self.frozen)
        return genome

    def initial_population(self):
        population = []
        if self.init_policy is not None:
            seed = genome_from_policy(self.template, self.spec, self.init_policy, self.rng)
            population.append(seed)
            # Half the population: perturbed copies of the init model
            while len(population) < self.population_size // 2:
                population.append(self.mutate(seed, rate=0.5))
        while len(population) < self.population_size:
            population.append(self.random_genome())
        return population

    def mutate(self, genome, rate=None):
        rate = self.mutation_rate if rate is None else rate
        child = dict(genome)
        for name, bounds in self.spec.items():
            if name not in self.frozen and self.rng.random() < rate:
                low, high, _ = bounds
                child[name] = clamp(bounds, child[name] + self.rng.gauss(0, self.mutation_scale * (high - low)))
        return child

    def crossover(self, a, b):
        return {name: (a if self.rng.random() < 0.5 else b)[name] for name in self.spec}

    def tournament(self, population, fitnesses):
        picks = self.rng.sample(range(len(population)), self.tournament_size)
        return population[max(picks, key=lambda i: fitnesses[i])]

    def next_generation(self, population, fitnesses):
        order = sorted(range(len(population)), key=lambda i: fitnesses[i], reverse=True)
        new_population = [dict(population[i]) for i in order[:self.elite_size]]
        while len(new_population) < self.population_size:
            if self.rng.random() < self.crossover_rate:
                child = self.crossover(self.tournament(population, fitnesses),
                                       self.tournament(population, fitnesses))
            else:
                child = dict(self.tournament(population, fitnesses))
            new_population.append(self.mutate(child))
        return new_population

    # -- evaluation -----------------------------------------------------------

    def play_many(self, genomes, seeds, max_pieces=None):
        """Play every genome on every seed. Returns per-genome lists of game results."""
        max_pieces = self.max_pieces if max_pieces is None else max_pieces
        tasks = [(i, self.template, g, s, max_pieces, self.lookahead, self.randomizer)
                 for i, g in enumerate(genomes) for s in seeds]
        results = [[] for _ in genomes]
        if self.workers > 1:
            if self.pool is None:
                self.pool = mp.Pool(self.workers)
            iterator = self.pool.imap_unordered(_play_task, tasks)
        else:
            iterator = map(_play_task, tasks)
        for index, result in iterator:
            results[index].append(result)
        return results

    def record(self, genome, results):
        entry = self.archive.setdefault(genome_key(genome), {'genome': dict(genome), 'lines': []})
        entry['lines'].extend(r['lines'] for r in results)
        return statistics.mean(entry['lines'])

    def archive_best(self, min_games):
        entries = [e for e in self.archive.values() if len(e['lines']) >= min_games]
        return sorted(entries, key=lambda e: statistics.mean(e['lines']), reverse=True)

    # -- main loop --------------------------------------------------------------

    def run(self, generations, out_path=None, verbose=True, plot=True):
        self.run_dir = os.path.join('runs', f"{datetime.now():%Y%m%d_%H%M%S}_{self.template_name}")
        os.makedirs(self.run_dir, exist_ok=True)
        if verbose:
            print(f"GA: model={self.template_name} features={','.join(self.features)} "
                  f"genes={len(self.spec) - len(self.frozen)} pop={self.population_size} "
                  f"games={self.games} cap={self.max_pieces} lookahead={self.lookahead} "
                  f"randomizer={self.randomizer} workers={self.workers}")
            print(f"Run directory: {self.run_dir}")

        population = self.initial_population()
        start = time.time()

        try:
            for gen in range(1, generations + 1):
                gen_start = time.time()
                seeds = [TRAIN_SEED_BASE + (gen - 1) * self.games + i for i in range(self.games)]
                results = self.play_many(population, seeds)
                fitnesses = [statistics.mean(r['lines'] for r in res) for res in results]
                # Select on the archive mean over *all* games a genome has played, not just this
                # generation's: lucky genomes keep getting replayed (elites) until they regress.
                selection = [self.record(genome, res) for genome, res in zip(population, results)]

                best_i = max(range(len(population)), key=lambda i: fitnesses[i])
                leaders = self.archive_best(min_games=2 * self.games)
                leader = leaders[0] if leaders else None
                entry = {
                    'generation': gen,
                    'best': fitnesses[best_i],
                    'mean': statistics.mean(fitnesses),
                    'median': statistics.median(fitnesses),
                    'best_genome': population[best_i],
                    'leader_mean': statistics.mean(leader['lines']) if leader else None,
                    'leader_games': len(leader['lines']) if leader else 0,
                    'leader_genome': leader['genome'] if leader else None,
                    'seconds': time.time() - gen_start,
                }
                self.history.append(entry)
                self.save_checkpoint(population, fitnesses)

                if verbose:
                    lead = (f"leader {entry['leader_mean']:.0f} over {entry['leader_games']} games"
                            if leader else "leader n/a")
                    print(f"gen {gen:3d}/{generations}  best {entry['best']:7.0f}  "
                          f"mean {entry['mean']:7.0f}  {lead}  ({entry['seconds']:.0f}s)")
                    if self.template_name != 'single':
                        g = leader['genome'] if leader else population[best_i]
                        th = '  '.join(f"{k}={v}" for k, v in g.items() if k.endswith('.threshold'))
                        print(f"          thresholds: {th}")

                if gen < generations:
                    population = self.next_generation(population, selection)

            policy = self.select_final(verbose)
        finally:
            if self.pool is not None:
                self.pool.close()
                self.pool.join()
                self.pool = None

        policy.meta.update({
            'name': os.path.splitext(os.path.basename(out_path))[0] if out_path else self.template_name,
            'trained': datetime.now().isoformat(timespec='seconds'),
            'run_dir': self.run_dir,
            'generations': generations,
            'population': self.population_size,
            'games_per_individual': self.games,
            'max_pieces': self.max_pieces,
            'lookahead': self.lookahead,
            'randomizer': self.randomizer,
            'init_model': self.init_policy.meta.get('name') if self.init_policy else None,
            'features': list(self.features),
            'training_minutes': round((time.time() - start) / 60, 1),
        })
        policy.save(os.path.join(self.run_dir, 'model.json'))
        if out_path:
            policy.save(out_path)
        if plot:
            self.save_plot()
        if verbose:
            print(f"\nFinal model ({policy.meta['validation_mean']:.0f} lines mean on "
                  f"{self.validation_games} validation games):")
            print(policy.describe())
            print(f"Saved: {out_path or os.path.join(self.run_dir, 'model.json')}")
        return policy

    def select_final(self, verbose):
        """Re-play the top archive candidates on validation seeds and keep the best."""
        pool = self.archive_best(min_games=2 * self.games)[:self.candidates]
        if len(pool) < self.candidates:
            seen = {genome_key(e['genome']) for e in pool}
            for e in self.archive_best(min_games=1):
                if genome_key(e['genome']) not in seen:
                    pool.append(e)
                    seen.add(genome_key(e['genome']))
                if len(pool) >= self.candidates:
                    break
        genomes = [e['genome'] for e in pool]
        seeds = [VALIDATION_SEED_BASE + i for i in range(self.validation_games)]
        if verbose:
            print(f"\nValidating {len(genomes)} candidates on {len(seeds)} validation seeds...")
        results = self.play_many(genomes, seeds)
        scores = [statistics.mean(r['lines'] for r in res) for res in results]
        best = max(range(len(genomes)), key=lambda i: scores[i])
        if verbose:
            for i, (e, s) in enumerate(zip(pool, scores)):
                mark = '*' if i == best else ' '
                print(f"  {mark} candidate {i + 1}: train {statistics.mean(e['lines']):7.0f} "
                      f"({len(e['lines'])} games)  validation {s:7.0f}")
        return genome_to_policy(self.template, genomes[best], meta={
            'validation_mean': scores[best],
            'validation_games': len(seeds),
            'train_mean': statistics.mean(pool[best]['lines']),
            'train_games': len(pool[best]['lines']),
        })

    # -- output -------------------------------------------------------------------

    def save_checkpoint(self, population, fitnesses):
        data = {
            'template': self.template_name,
            'features': list(self.features),
            'frozen': sorted(self.frozen),
            'parameters': {
                'population_size': self.population_size, 'games': self.games,
                'max_pieces': self.max_pieces, 'lookahead': self.lookahead,
                'randomizer': self.randomizer, 'mutation_rate': self.mutation_rate,
                'mutation_scale': self.mutation_scale, 'crossover_rate': self.crossover_rate,
                'elite_size': self.elite_size, 'tournament_size': self.tournament_size,
            },
            'history': self.history,
            'population': [{'genome': g, 'fitness': f} for g, f in zip(population, fitnesses)],
        }
        with open(os.path.join(self.run_dir, 'checkpoint.json'), 'w') as f:
            json.dump(data, f, indent=1)

    def save_plot(self):
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            return
        gens = [h['generation'] for h in self.history]
        thresholds = [k for k in self.spec if k.endswith('.threshold')]
        fig, axes = plt.subplots(2 if thresholds else 1, 1, figsize=(10, 8 if thresholds else 5),
                                 squeeze=False)
        ax = axes[0][0]
        ax.plot(gens, [h['best'] for h in self.history], label='best of generation', alpha=0.6)
        ax.plot(gens, [h['mean'] for h in self.history], label='population mean')
        ax.plot(gens, [h['leader_mean'] for h in self.history], label='archive leader (multi-gen mean)',
                linewidth=2)
        ax.set_xlabel('generation')
        ax.set_ylabel('lines cleared')
        ax.set_title(f'GA - {self.template_name} model')
        ax.legend()
        ax.grid(alpha=0.3)
        if thresholds:
            ax = axes[1][0]
            for name in thresholds:
                ax.plot(gens, [(h['leader_genome'] or h['best_genome'])[name] for h in self.history],
                        label=name, marker='.')
            ax.set_xlabel('generation')
            ax.set_ylabel('threshold')
            ax.set_title('Regime thresholds of the leader')
            ax.legend()
            ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(self.run_dir, 'evolution.png'), dpi=120)
        plt.close(fig)
