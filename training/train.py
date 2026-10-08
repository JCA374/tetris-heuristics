#!/usr/bin/env python3
"""
Train a single-weight or regime-switching model with the GA.

Examples:
    python training/train.py --model single --workers 8 --out models/single_v2.json
    python training/train.py --model regime --workers 8 --out models/regime_v2.json
    python training/train.py --model regime --quick          # smoke test
    python training/train.py --bench --workers 8             # games/second on this machine

For a fair comparison, train both models with identical settings: they then
play the same training seeds generation by generation.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tetris.policy import Policy, TEMPLATES
from training.ga import GeneticAlgorithm


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--model', choices=sorted(TEMPLATES), default='single',
                        help='rule template to evolve (default: single)')
    parser.add_argument('--generations', '-g', type=int, default=50)
    parser.add_argument('--population', '-p', type=int, default=50)
    parser.add_argument('--games', type=int, default=5, help='games per individual per generation')
    parser.add_argument('--max-pieces', type=int, default=20000, help='piece cap per training game')
    parser.add_argument('--lookahead', action='store_true', help='1-piece lookahead (~20x slower)')
    parser.add_argument('--randomizer', choices=['random', 'bag'], default='random')
    parser.add_argument('--workers', '-w', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--init', default='models/baseline_single_v1.json',
                        help="model to seed half the population with ('none' for pure random)")
    parser.add_argument('--validation-games', type=int, default=30)
    parser.add_argument('--seed', type=int, default=0, help='GA random seed')
    parser.add_argument('--out', help='where to save the final model (always also in runs/)')
    parser.add_argument('--quick', action='store_true', help='smoke test: 3 gens, pop 10, 2 games, cap 500')
    parser.add_argument('--bench', action='store_true', help='measure games/second and exit')
    args = parser.parse_args()

    if args.quick:
        args.generations, args.population, args.games = 3, 10, 2
        args.max_pieces, args.validation_games = 500, 4

    init_policy = None if args.init == 'none' else Policy.load(args.init)

    ga = GeneticAlgorithm(
        template_name=args.model, population_size=args.population, games=args.games,
        max_pieces=args.max_pieces, lookahead=args.lookahead, randomizer=args.randomizer,
        workers=args.workers, init_policy=init_policy, rng_seed=args.seed,
        validation_games=args.validation_games,
    )

    if args.bench:
        genomes = [ga.random_genome() for _ in range(args.workers * 2)]
        start = time.time()
        results = ga.play_many(genomes, seeds=[1, 2], max_pieces=2000)
        elapsed = time.time() - start
        pieces = sum(r['pieces'] for res in results for r in res)
        print(f"{len(genomes) * 2} games, {pieces} pieces in {elapsed:.1f}s with {args.workers} workers "
              f"-> {pieces / elapsed:.0f} pieces/s")
        if ga.pool:
            ga.pool.close()
        return

    ga.run(args.generations, out_path=args.out)


if __name__ == '__main__':
    main()
