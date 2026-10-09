"""
Estimate expected game length with multilevel splitting (rare-event simulation).

A strong policy dies about once per million pieces, so a full game gives one
noisy sample per ~10 CPU-seconds. Deaths follow a ladder of hole counts: the
board gets into trouble (holes >= L1) every few thousand pieces, and from there
it either recovers to a clean board or climbs to the next level (L2, L3, ...),
until it dies. So

    pieces per death  ~=  T  /  P(L1 -> L2) * P(L2 -> L3) * ... * P(Lk -> death)

where T is the mean number of pieces from a clean board to the first level, and
each P(Li -> Li+1) is the chance, starting from a board that just reached Li,
of reaching Li+1 before recovering. Every factor is a common event, so a few
hundred short episodes estimate it well. The boards at each level come from the
policy's own play (on-policy), so there is no fixed crisis dataset to run out
of or to overfit.

Episodes run in the C core (fastcore.play_from) and need it.
"""

import math
import random

from . import fastcore

LEVELS = (6, 10, 14, 18)        # hole counts; the last step is "reach game over"
RECOVER_MAX_HEIGHT = 8          # recovered = no holes and max height <= this


def estimate(policy, starts, seed, levels=LEVELS, n_start=40, n_split=8, max_states=40,
             start_cap=200_000, step_cap=20_000, lookahead=False, randomizer='random'):
    """
    Args:
        policy: Policy to evaluate
        starts: list of clean boards (row bitmasks) to start from
        seed: base seed for all piece sequences of this estimate
        n_start: episodes from clean boards (measures T, yields level-1 boards)
        n_split: continuations per board at every level
        max_states: boards kept per level (sampled) to split from

    Returns dict(log_pieces, pieces_per_death, t_first, steps=[(level, p, n)], pieces)
    with log_pieces = ln(estimated pieces per death), the fitness to maximise.
    """
    rng = random.Random(seed)
    seed_base = seed * 1_000_003
    counter = 0
    total = 0

    def episode(board, stop, recover):
        nonlocal counter, total
        counter += 1
        r = fastcore.play_from(policy, board, seed=seed_base + counter, max_pieces=step_cap if recover >= 0 else start_cap,
                               lookahead=lookahead, randomizer=randomizer,
                               recover_max_height=recover, stop_holes=stop)
        total += r['pieces']
        return r

    # 1. Clean board -> first level
    times, states = [], []
    for _ in range(n_start):
        r = episode(starts[rng.randrange(len(starts))], levels[0], -1)
        times.append(r['pieces'])
        if r['outcome'] in ('crisis', 'game_over'):
            states.append((r['rows'], r['outcome'] == 'game_over'))
    t_first = sum(times) / len(times)
    if not states:                         # never got into trouble within the cap
        return _result(t_first * 10 / 0.5 ** len(levels), t_first, [], total)

    # 2. Level by level: P(reach the next level, or die, before recovering)
    steps = []                 # (level, p_hit, share of hits that were deaths, episodes)
    died_first = sum(dead for _, dead in states) / len(states)    # died before even reaching L1
    reach = [rows for rows, dead in states if not dead]
    for i, level in enumerate(levels):
        if not reach:
            break
        nxt = levels[i + 1] if i + 1 < len(levels) else 0          # 0 = only death counts
        if len(reach) > max_states:
            reach = rng.sample(reach, max_states)
        hits = deaths = n = 0
        new = []
        for rows in reach:
            for _ in range(n_split):
                r = episode(rows, nxt, RECOVER_MAX_HEIGHT)
                n += 1
                if r['outcome'] == 'game_over':
                    hits += 1
                    deaths += 1
                elif nxt and r['outcome'] == 'crisis':
                    hits += 1
                    new.append(r['rows'])
        p = (hits + 0.5) / (n + 1)      # smoothed so one lucky level never gives p = 0
        steps.append((level, p, deaths / hits if hits else 0.0, n))
        reach = new

    # P(death | at level i) = p_i * (d_i + (1 - d_i) * P(death | at level i+1)); the last level only counts deaths
    q = 1.0 if len(steps) == len(levels) else 0.5 ** (len(levels) - len(steps))   # unexplored deeper levels
    for level, p, d, n in reversed(steps):
        q = p * (d + (1 - d) * q) if level != levels[-1] else p
    p_death = died_first + (1 - died_first) * q
    return _result(t_first / p_death, t_first, steps, total)


def _result(pieces, t_first, steps, total):
    return {'log_pieces': math.log(pieces), 'pieces_per_death': pieces, 't_first': t_first,
            'steps': steps, 'pieces': total}
