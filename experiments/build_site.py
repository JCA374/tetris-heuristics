#!/usr/bin/env python3
"""
Build the project page docs/index.html (GitHub Pages: Settings -> Pages -> branch, /docs).

Collects training histories (runs/*/checkpoint.json), model comparisons
(results/compare_*.json), failure analyses (results/game_analysis/*/summary.json)
and recorded games (runs/games/*.jsonl.gz) into one JSON blob, and inlines it
into experiments/site_template.html. The page is self-contained apart from the
charting library (Observable Plot from jsDelivr), so it also works from file://.

runs/ and results/ are git-ignored, so the page is the published record of them:
rebuild and commit docs/index.html after new results.

    python experiments/build_site.py            # collect data (~1 min) and build
    python experiments/build_site.py --reuse    # rebuild from the cached data (template edits)
"""

import glob
import gzip
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from tetris import fastcore
from tetris.policy import Policy

# Training runs shown on the page: run dir -> (label, story)
RUNS = {
    'runs/20261008_140426_single': ('v2 single', '4 features, lines fixed'),
    'runs/20261008_140426_regime': ('v2 regime', '4 features, 3 regimes'),
    'runs/20261008_172813_single': ('v3 single', '6 features (+wells, hole depth), 20k-piece cap'),
    'runs/20261008_172813_regime': ('v3 regime', '6 features, 3 regimes, 20k-piece cap'),
    'runs/20261008_213752_single': ('v4 single', '5 features, C engine, 1M-piece cap'),
    'runs/20261008_213752_regime': ('v4 regime', '5 features, 3 regimes, 1M-piece cap'),
    'runs/20261009_102648_repair': ('v5 repair', '2 regimes, normal frozen at v4 single'),
    'runs/20261009_154956_single_split': ('v6 GA', 'single model, splitting fitness, GA'),
    'runs/20261009_154956_single_cem_split': ('v6 CEM', 'single model, splitting fitness, cross-entropy'),
    'runs/20261009_201504_single_split': ('v7 single', '8 features (+landing height, eroded cells, S/Z fit), splitting fitness, GA'),
    'runs/20261009_214729_single_split': ('v8 single', '5 nonzero features of v7, start boards from v7, splitting fitness, GA'),
}
OPTIMIZER_SCREEN = 'results/compare_splitting_20261009_162211.json'   # 150 splitting estimates
OPTIMIZER_FULL = 'results/compare_20261009_180915.json'               # 1000 full games, v4 vs v6 GA
V7_SCREEN = 'results/compare_splitting_20261009_210541.json'          # 200 splitting estimates, v4 vs v7
V7_PAIR = {'single_v4', 'single_v7'}                                   # full games: newest compare of exactly these
V8_SCREEN = 'results/compare_splitting_20261009_232400.json'          # 200 splitting estimates, v7 vs v8
V8_PAIR = {'single_v7', 'single_v8'}
ABLATION_V7 = 'results/compare_splitting_20261010_022913.json'        # v7 with one move feature removed
# Measured with tetris/splitting.py-style episodes on single_v4 from clean boards (160 per level)
LADDER = [{'holes': 2, 'pieces': 108, 'p_death': 0.0}, {'holes': 4, 'pieces': 518, 'p_death': 0.001},
          {'holes': 6, 'pieces': 2324, 'p_death': 0.001}, {'holes': 8, 'pieces': 10488, 'p_death': 0.004},
          {'holes': 10, 'pieces': 29210, 'p_death': 0.021}]
# Splitting estimate (median of 12, pieces per death / 2.5) vs full-game mean lines (50 held-out games)
ESTIMATOR_CHECK = [
    {'model': 'single_v4', 'estimated': 1449010 / 2.5, 'real': 413254},
    {'model': 'without hole depth', 'estimated': 1223742 / 2.5, 'real': 340279},
    {'model': 'without height', 'estimated': 945267 / 2.5, 'real': 246553},
    {'model': 'single_v2', 'estimated': 3435 / 2.5, 'real': 2527},
    {'model': 'baseline_single_v1', 'estimated': 2950 / 2.5, 'real': 1785},
]
MAIN_COMPARE = 'results/compare_20261008_235146.json'      # all models, 50 games, 3M cap
ABLATION_V4 = 'results/compare_20261009_102631.json'       # drop one feature from single_v4
LINES_ABLATION = 'runs/ablation/compare_20261008_210928.json'
REPAIR_COMPARES = ['results/compare_20261009_130945.json']  # + the newest 1000-game one if present
MODELS = ['baseline_single_v1', 'single_v2', 'regime_v2', 'single_v4', 'regime_v4', 'repair_v5', 'single_v7', 'single_v8']


def load_json(path):
    with open(path) as f:
        return json.load(f)


def load_games(path):
    with gzip.open(path, 'rt') as f:
        header = json.loads(f.readline())['header']
        return header, [json.loads(line) for line in f]


def holes(board):
    seen, n = [False] * 10, 0
    for row in board:
        for c, ch in enumerate(row):
            if ch != '.':
                seen[c] = True
            elif seen[c]:
                n += 1
    return n


def hole_columns(board):
    seen, cols = [False] * 10, [0] * 10
    for row in board:
        for c, ch in enumerate(row):
            if ch != '.':
                seen[c] = True
            elif seen[c]:
                cols[c] += 1
    return cols


def compare_summary(path):
    r = load_json(path)
    out = {'settings': r['settings'], 'reference': r['reference'], 'models': []}
    for name, m in r['models'].items():
        paired = m.get('paired_vs_reference') or {}
        out['models'].append({
            'name': name, 'mean': m['summary']['mean'], 'median': m['summary']['median'],
            'ci': m['summary']['mean_ci95'], 'capped': m.get('capped_games', 0),
            'diff': paired.get('mean_diff'), 'diff_ci': paired.get('mean_diff_ci95'),
            'wins': paired.get('wins'), 'losses': paired.get('losses'),
            'significant': paired.get('significant'), 'regime_usage': m.get('regime_usage'),
            'lines': m['lines_per_seed'],
        })
    return out


def training_runs():
    runs = []
    for run_dir, (label, story) in RUNS.items():
        path = os.path.join(run_dir, 'checkpoint.json')
        if not os.path.exists(path):
            continue
        c = load_json(path)
        p = c['parameters']
        split = str(c.get('fitness', 'lines')).startswith('est.')
        conv = (lambda v: None if v is None else math.exp(v) / 2.5) if split else (lambda v: v)
        runs.append({
            'id': os.path.basename(run_dir), 'label': label, 'story': story, 'template': c['template'],
            'features': c.get('features') or ['height', 'lines', 'holes', 'bumpiness'],
            'population': p['population_size'], 'games': p['games'], 'cap': None if split else p['max_pieces'],
            'fitness': 'splitting' if split else 'games', 'optimizer': c.get('optimizer', 'ga'),
            'history': [{'g': h['generation'], 'best': conv(h['best']), 'mean': conv(h['mean']),
                         'leader': conv(h['leader_mean']), 'leader_games': h['leader_games'],
                         'thresholds': {k: v for k, v in (h['leader_genome'] or h['best_genome']).items()
                                        if k.endswith('.threshold')}}
                        for h in c['history']],
        })
    return runs


def analysis(model):
    path = f'results/game_analysis/{model}/summary.json'
    if not os.path.exists(path):
        return None
    s = load_json(path)
    return {
        'games': s['games'], 'game_overs': s['game_overs'], 'lines_mean': s['lines_mean'],
        'lines_median': s['lines_median'], 'model_auc': s['model_eval_auc'],
        'features': [{'feature': k, 'auc': v['auc'],
                      'added': None if v['partial_corr'] is None else -v['partial_corr']}
                     for k, v in s['feature_stats'].items()],
        'hole_rate_by_piece': s['hole_rate_by_piece'], 'killer_share': s['killer_share'],
        'onset': s['onset'], 'midgame': s['midgame_medians'], 'at_death': s['final_board_medians'],
        'regime_share_whole': s.get('regime_share_whole'), 'regime_share_last': s.get('regime_share_last'),
    }


def recordings(model, rng):
    """Boards, droughts, hole columns and regime run-up from runs/games/<model>.jsonl.gz."""
    path = f'runs/games/{model}.jsonl.gz'
    if not os.path.exists(path):
        return None
    header, games = load_games(path)
    dead = [g for g in games if g['record']['game_over']]
    pick = sorted(rng.sample(dead, min(8, len(dead))), key=lambda g: g['lines'])
    drought = Counter(min(g['record']['pieces_since_seen'].get('I', 0), 40) for g in dead)
    cols = [0] * 10
    for g in dead:
        for c, n in enumerate(hole_columns(g['record']['final_board'])):
            cols[c] += n
    out = {
        'boards': [{'lines': g['lines'], 'board': g['record']['final_board'],
                    'killer': g['record']['killer_piece']} for g in pick],
        'i_drought': [{'pieces': k, 'games': drought.get(k, 0)} for k in range(41)],
        'dead': len(dead),
        'hole_columns': [n / max(sum(cols), 1) for n in cols],
        'lines': [g['lines'] for g in games],
    }
    rules = header['policy']['rules']
    if len(rules) > 1:
        names = [r['name'] for r in rules]
        steps = 300
        share = {n: [0] * steps for n in names}
        count = [0] * steps
        for g in dead:
            rec = g['record']['recent'][-steps:]
            off = steps - len(rec)
            for j, r in enumerate(rec):
                count[off + j] += 1
                share[r['regime']][off + j] += 1
        out['regime_runup'] = [{'before': j - steps + 1, 'regime': n, 'share': share[n][j] / count[j]}
                               for n in names for j in range(steps) if count[j]]
    return out


def crisis_recovery(rng):
    """single_v4: share of boards from the run-up to death that recover with fresh pieces."""
    path = 'runs/games/single_v4.jsonl.gz'
    if not (os.path.exists(path) and fastcore.available()):
        return None
    _, games = load_games(path)
    dead = [g for g in games if g['record']['game_over']]
    policy = Policy.load('models/single_v4.json')
    result = defaultdict(list)
    seed = 6_000_000
    for d in (5, 10, 20, 30, 40, 60, 80, 100, 150, 200, 300):
        for g in dead:
            rec = g['record']['recent']
            if len(rec) < d:
                continue
            board = rec[len(rec) - d]['board']
            if holes(board) == 0:
                continue
            for _ in range(2):
                seed += 1
                result[d].append(fastcore.play_from(policy, board, seed=seed, max_pieces=1000)['recovered'])
    return [{'before': d, 'rate': sum(v) / len(v), 'n': len(v)} for d, v in sorted(result.items())]


def models():
    out = []
    for name in MODELS:
        path = f'models/{name}.json'
        if os.path.exists(path):
            p = Policy.load(path)
            out.append({'name': name, 'rules': p.rules, 'weights': p.weights})
    return out


CACHE = 'results/site_data.json'


def main():
    if '--reuse' in sys.argv and os.path.exists(CACHE):
        data = load_json(CACHE)
    else:
        data = collect()
        with open(CACHE, 'w') as f:
            json.dump(data, f)
    with open('experiments/site_template.html') as f:
        html = f.read()
    blob = json.dumps(data, separators=(',', ':')).replace('</', '<\\/')
    html = html.replace('/*__DATA__*/null', blob)
    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w') as f:
        f.write(html)
    print(f'Wrote docs/index.html ({os.path.getsize("docs/index.html") / 1e3:.0f} kB)')


def newest_compare(models):
    """Newest results/compare_*.json comparing exactly these models (None if there is none)."""
    paths = [p for p in sorted(glob.glob('results/compare_2*.json')) if set(load_json(p)['models']) == models]
    return paths[-1] if paths else None


def collect():
    rng = random.Random(1)
    repair = list(REPAIR_COMPARES)
    for path in sorted(glob.glob('results/compare_*.json')):
        if path not in repair and set(load_json(path)['models']) == {'single_v4', 'repair_v5'}:
            repair.append(path)
    v7_full = newest_compare(V7_PAIR)
    v8_full = newest_compare(V8_PAIR)
    data = {
        'built': date.today().isoformat(),
        'runs': training_runs(),
        'compare': compare_summary(MAIN_COMPARE),
        'ablation_v4': compare_summary(ABLATION_V4),
        'lines_ablation': compare_summary(LINES_ABLATION) if os.path.exists(LINES_ABLATION) else None,
        'repair': [compare_summary(p) for p in repair if os.path.exists(p)],
        'analysis': {m: analysis(m) for m in ('baseline_single_v1', 'single_v4', 'regime_v4', 'single_v7')},
        'recordings': {m: recordings(m, rng) for m in ('baseline_single_v1', 'single_v4', 'regime_v4')},
        'crisis': crisis_recovery(rng),
        'models': models(),
        'splitting': {'ladder': LADDER, 'check': ESTIMATOR_CHECK},
        'optimizer': {
            'screen': load_json(OPTIMIZER_SCREEN) if os.path.exists(OPTIMIZER_SCREEN) else None,
            'full': compare_summary(OPTIMIZER_FULL) if os.path.exists(OPTIMIZER_FULL) else None,
        },
        'v7': {
            'screen': load_json(V7_SCREEN) if os.path.exists(V7_SCREEN) else None,
            'full': compare_summary(v7_full) if v7_full else None,
            'ablation': load_json(ABLATION_V7) if os.path.exists(ABLATION_V7) else None,
        },
        'v8': {
            'screen': load_json(V8_SCREEN) if os.path.exists(V8_SCREEN) else None,
            'full': compare_summary(v8_full) if v8_full else None,
        },
    }
    for screen in (data['optimizer']['screen'], data['v7']['screen'], data['v7']['ablation'], data['v8']['screen']):
        for d in screen['models'].values() if screen else []:
            d.pop('log_pieces', None)
    return data


if __name__ == '__main__':
    main()
