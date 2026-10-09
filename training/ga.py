"""
Weight search over a named-gene genome: a genetic algorithm (default) or the
cross-entropy method (--optimizer cem), with full games or multilevel-splitting
estimates (tetris/splitting.py) as fitness.

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

Fitness:
- 'games': lines per full game (mean over `games` games).
- 'splitting': ln(estimated pieces per death) from tetris/splitting.estimate, starting
  from recorded clean boards (`starts`); `games` = estimates per genome per generation.
  About 17x more information per CPU-second than full games for strong policies.

Cross-entropy method (Szita & Lorincz 2006, the standard for Tetris weights): sample
the population from a Gaussian per gene, keep the best quarter, refit mean and
spread, add decreasing extra noise so the search does not collapse early.
"""

import json
import math
import os
import random
import statistics
import time
import multiprocessing as mp
from datetime import datetime

from tetris.features import FEATURES
from tetris.policy import Policy, TEMPLATES
from tetris import fastcore, splitting
from tetris.play import (play_game, TRAIN_SEED_BASE, VALIDATION_SEED_BASE,
                         SPLIT_TRAIN_SEED_BASE, SPLIT_VALIDATION_SEED_BASE)

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

_STARTS = None      # clean start boards for splitting estimates (set per worker process)


def _init_worker(starts):
    global _STARTS
    _STARTS = starts


def _play_task(args):
    """One evaluation: a seed (full game, fitness = lines) or ('split', seed) (splitting estimate)."""
    index, template, genome, episode, max_pieces, lookahead, randomizer = args
    policy = genome_to_policy(template, genome)
    if isinstance(episode, tuple):
        est = splitting.estimate(policy, _STARTS, seed=episode[1], lookahead=lookahead, randomizer=randomizer)
        result = {'fitness': est['log_pieces'], 'lines': est['pieces_per_death'] / 2.5, 'pieces': est['pieces']}
    else:
        result = play_game(policy, seed=episode, max_pieces=max_pieces,
                           lookahead=lookahead, randomizer=randomizer)
        result['fitness'] = result['lines']
    return index, result


# --- GA -----------------------------------------------------------------------

class GeneticAlgorithm:
    def __init__(self, template_name='single', population_size=50, games=5,
                 max_pieces=20000, lookahead=False, randomizer='random', workers=1,
                 init_policy=None, rng_seed=None, validation_games=30, candidates=5,
                 features=FEATURES, freeze=(), fitness='games', starts=None, optimizer='ga'):
        """
        freeze: regime names whose weights stay fixed at the init model's values.
        fitness: 'games' or 'splitting' (needs `starts`: clean boards as row bitmasks,
            from experiments/make_start_states.py, and the C core).
        optimizer: 'ga' or 'cem'.
        """
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
        if fitness not in ('games', 'splitting') or optimizer not in ('ga', 'cem'):
            raise ValueError(f'unknown fitness {fitness!r} or optimizer {optimizer!r}')
        self.fitness = fitness
        self.optimizer = optimizer
        self.starts = starts
        if fitness == 'splitting':
            if not starts:
                raise ValueError('splitting fitness needs start boards')
            if not fastcore.available():
                raise RuntimeError('splitting fitness needs the C core: ' + str(fastcore.build_error()))
            _init_worker(starts)
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
        # cross-entropy method
        self.cem_elite_fraction = 0.25
        self.cem_init_spread = 0.1    # initial sigma as fraction of the gene's range (around --init)
        self.cem_extra_noise = 0.03   # added sigma (fraction of range), decays to 0 at 80% of the run
        self.cem_mean = None
        self.cem_sigma = None

        self.archive = {}             # genome_key -> {'genome', 'scores': [fitness per episode]}
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
                self.pool = mp.Pool(self.workers, initializer=_init_worker, initargs=(self.starts,))
            iterator = self.pool.imap_unordered(_play_task, tasks,
                                                chunksize=max(1, len(tasks) // (self.workers * 16)))
        else:
            iterator = map(_play_task, tasks)
        for index, result in iterator:
            results[index].append(result)
        return results

    def record(self, genome, results):
        entry = self.archive.setdefault(genome_key(genome), {'genome': dict(genome), 'scores': []})
        entry['scores'].extend(r['fitness'] for r in results)
        return statistics.mean(entry['scores'])

    def archive_best(self, min_games):
        entries = [e for e in self.archive.values() if len(e['scores']) >= min_games]
        return sorted(entries, key=lambda e: statistics.mean(e['scores']), reverse=True)

    def fmt(self, value):
        """Fitness for printing: lines (games) or estimated lines per game (splitting, geometric mean)."""
        if self.fitness == 'splitting':
            return f'{math.exp(value) / 2.5:9,.0f}'
        return f'{value:9,.0f}'

    def fitness_label(self):
        return 'est. lines per game (splitting)' if self.fitness == 'splitting' else 'lines'

    def train_episodes(self, gen):
        if self.fitness == 'splitting':
            return [('split', SPLIT_TRAIN_SEED_BASE + (gen - 1) * self.games + i) for i in range(self.games)]
        return [TRAIN_SEED_BASE + (gen - 1) * self.games + i for i in range(self.games)]

    def validation_episodes(self):
        if self.fitness == 'splitting':
            return [('split', SPLIT_VALIDATION_SEED_BASE + i) for i in range(self.validation_games)]
        return [VALIDATION_SEED_BASE + i for i in range(self.validation_games)]

    # -- cross-entropy method -------------------------------------------------------

    def free_genes(self):
        return [k for k in self.spec if k not in self.frozen]

    def cem_start(self):
        self.cem_mean, self.cem_sigma = {}, {}
        seed = (genome_from_policy(self.template, self.spec, self.init_policy, self.rng)
                if self.init_policy is not None else None)
        for k in self.free_genes():
            low, high, _ = self.spec[k]
            self.cem_mean[k] = seed[k] if seed else (low + high) / 2
            self.cem_sigma[k] = (self.cem_init_spread if seed else 0.3) * (high - low)

    def cem_sample(self):
        """The current mean plus population_size - 1 Gaussian samples around it."""
        population = []
        for i in range(self.population_size):
            genome = dict(self.frozen)
            for k in self.free_genes():
                v = self.cem_mean[k] if i == 0 else self.rng.gauss(self.cem_mean[k], self.cem_sigma[k])
                genome[k] = clamp(self.spec[k], v)
            population.append(genome)
        return population

    def cem_update(self, population, fitnesses, gen, generations):
        n = max(2, round(self.cem_elite_fraction * len(population)))
        elite = [population[i] for i in sorted(range(len(population)), key=lambda i: fitnesses[i], reverse=True)[:n]]
        decay = max(0.0, 1 - gen / (0.8 * generations))
        for k in self.free_genes():
            low, high, _ = self.spec[k]
            values = [g[k] for g in elite]
            self.cem_mean[k] = statistics.mean(values)
            self.cem_sigma[k] = statistics.pstdev(values) + self.cem_extra_noise * decay * (high - low)

    # -- main loop --------------------------------------------------------------

    def run(self, generations, out_path=None, verbose=True, plot=True):
        tag = self.template_name + ('' if self.optimizer == 'ga' else f'_{self.optimizer}') + \
            ('_split' if self.fitness == 'splitting' else '')
        base = os.path.join('runs', f"{datetime.now():%Y%m%d_%H%M%S}_{tag}")
        self.run_dir, n = base, 1
        while True:                 # unique even when several runs start in the same second
            try:
                os.makedirs(self.run_dir)
                break
            except FileExistsError:
                n += 1
                self.run_dir = f'{base}_{n}'
        if verbose:
            print(f"GA: model={self.template_name} features={','.join(self.features)} "
                  f"genes={len(self.spec) - len(self.frozen)} pop={self.population_size} "
                  f"games={self.games} cap={self.max_pieces} lookahead={self.lookahead} "
                  f"randomizer={self.randomizer} workers={self.workers}")
            print(f"Run directory: {self.run_dir}")

        if self.optimizer == 'cem':
            self.cem_start()
            population = self.cem_sample()
        else:
            population = self.initial_population()
        start = time.time()

        try:
            for gen in range(1, generations + 1):
                gen_start = time.time()
                results = self.play_many(population, self.train_episodes(gen))
                fitnesses = [statistics.mean(r['fitness'] for r in res) for res in results]
                # Select on the archive mean over *all* games a genome has played, not just this
                # generation's: lucky genomes keep getting replayed (elites) until they regress.
                selection = [self.record(genome, res) for genome, res in zip(population, results)]

                best_i = max(range(len(population)), key=lambda i: fitnesses[i])
                if self.optimizer == 'cem':
                    # every genome is new each generation; the CEM mean (individual 0) is the "leader"
                    leader = self.archive[genome_key(population[0])]
                else:
                    leaders = self.archive_best(min_games=2 * self.games)
                    leader = leaders[0] if leaders else None
                entry = {
                    'generation': gen,
                    'best': fitnesses[best_i],
                    'mean': statistics.mean(fitnesses),
                    'median': statistics.median(fitnesses),
                    'best_genome': population[best_i],
                    'leader_mean': statistics.mean(leader['scores']) if leader else None,
                    'leader_games': len(leader['scores']) if leader else 0,
                    'leader_genome': leader['genome'] if leader else None,
                    'seconds': time.time() - gen_start,
                }
                self.history.append(entry)
                self.save_checkpoint(population, fitnesses)

                if verbose:
                    lead = (f"leader {self.fmt(entry['leader_mean'])} over {entry['leader_games']} games"
                            if leader else "leader n/a")
                    print(f"gen {gen:3d}/{generations}  best {self.fmt(entry['best'])}  "
                          f"mean {self.fmt(entry['mean'])}  {lead}  ({entry['seconds']:.0f}s)")
                    if self.template_name != 'single':
                        g = leader['genome'] if leader else population[best_i]
                        th = '  '.join(f"{k}={v}" for k, v in g.items() if k.endswith('.threshold'))
                        print(f"          thresholds: {th}")

                if gen < generations:
                    if self.optimizer == 'cem':
                        self.cem_update(population, fitnesses, gen, generations)
                        population = self.cem_sample()
                    else:
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
            print(f"\nFinal model ({self.fmt(policy.meta['validation_mean']).strip()} "
                  f"{self.fitness_label()} on {policy.meta['validation_games']} validation evaluations):")
            print(policy.describe())
            print(f"Saved: {out_path or os.path.join(self.run_dir, 'model.json')}")
        return policy

    def select_final(self, verbose):
        """Re-play the top archive candidates on validation seeds and keep the best."""
        pool = self.archive_best(min_games=2 * self.games)[:self.candidates]
        if self.optimizer == 'cem':
            # the final mean is the CEM's answer; also try the best single samples
            mean = dict(self.frozen, **{k: clamp(self.spec[k], v) for k, v in self.cem_mean.items()})
            pool = [self.archive.get(genome_key(mean), {'genome': mean, 'scores': []})]
        if len(pool) < self.candidates:
            seen = {genome_key(e['genome']) for e in pool}
            for e in self.archive_best(min_games=1):
                if genome_key(e['genome']) not in seen:
                    pool.append(e)
                    seen.add(genome_key(e['genome']))
                if len(pool) >= self.candidates:
                    break
        genomes = [e['genome'] for e in pool]
        seeds = self.validation_episodes()
        if verbose:
            print(f"\nValidating {len(genomes)} candidates on {len(seeds)} validation episodes...")
        results = self.play_many(genomes, seeds)
        scores = [statistics.mean(r['fitness'] for r in res) for res in results]
        best = max(range(len(genomes)), key=lambda i: scores[i])
        if verbose:
            for i, (e, s) in enumerate(zip(pool, scores)):
                mark = '*' if i == best else ' '
                train = self.fmt(statistics.mean(e['scores'])) if e['scores'] else '      n/a'
                print(f"  {mark} candidate {i + 1}: train {train} "
                      f"({len(e['scores'])} games)  validation {self.fmt(s)}")
        return genome_to_policy(self.template, genomes[best], meta={
            'validation_mean': scores[best],
            'validation_games': len(seeds),
            'train_mean': statistics.mean(pool[best]['scores']) if pool[best]['scores'] else None,
            'train_games': len(pool[best]['scores']),
            'fitness': self.fitness_label(),
            'optimizer': self.optimizer,
        })

    # -- output -------------------------------------------------------------------

    def save_checkpoint(self, population, fitnesses):
        data = {
            'template': self.template_name,
            'features': list(self.features),
            'frozen': sorted(self.frozen),
            'fitness': self.fitness_label(),
            'optimizer': self.optimizer,
            'cem': ({'mean': self.cem_mean, 'sigma': self.cem_sigma} if self.optimizer == 'cem' else None),
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
