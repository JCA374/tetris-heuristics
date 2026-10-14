# Tetris AI: heuristics, data-driven features and noise-aware training

A Tetris bot that scores every possible drop with a weighted sum of features:
board features (holes, bumpiness, wells, ...) and move features (landing
height, S/Z fit). The weights are tuned by a genetic algorithm. The project has
gone from 1,785 to **about 6 million lines per game** by recording how the bot
dies, finding the features that predict it, and measuring every change on
held-out games. That worked twice: two board features took it to ~500,000
lines, three move features then multiplied that by about 5, and retraining
with only the weights that matter added another 25%.

**Current focus: one weight set (single model).** The regime-switching
experiments (different weights per board situation) are finished; they never
beat the single model (see Results). The code still loads and plays those
models, but new work targets the single model.

Project page with all charts: `docs/index.html` (GitHub Pages:
https://jca374.github.io/tetris-heuristics/, built from `/docs` on this branch).

No dependencies are needed for the core, training or the terminal demo.
Games run in a small C core (`tetris/fastcore.c`, compiled automatically with
the system `cc` on first use, ~100× faster). It plays move-for-move like the
Python engine, which remains the fallback when no compiler is available.
`matplotlib` (training plot), `numpy` (analysis), `pygame` (graphical demo) and
`pytest` are optional.

## Quick start

```bash
python demo.py                                  # watch the best model in models/
python demo.py --model models/single_v8.json
python demo.py --list                           # all models and their weights
python demo_pygame.py --model models/single_v8.json   # left half of the screen; UP/DOWN speed, M = max (~100k moves/s on an idle machine); slows down by itself at 14 holes
python experiments/make_video.py                # ~105 s silent explainer -> docs/video/tetris_explainer.mp4

python -m pytest tests                          # test suite (~1 min)
```

## Train

Strong models die about once per million pieces, so a full game is one very
noisy data point (per-game spread ≈ the mean). Training therefore uses
**multilevel splitting** by default for strong models (`tetris/splitting.py`):

1. Start from clean boards recorded from real play and run until the board
   reaches 6 holes. That measures how often trouble starts.
2. From those boards, run several continuations with fresh pieces. Count how
   often each reaches 10 holes before recovering, then 14 from 10, then 18
   from 14, then game over from 18.
3. Expected pieces per death ≈ time to the first level ÷ the product of those
   probabilities.

Every step is a common event, so a few hundred short episodes estimate it. The
crisis boards come from the evaluated model's own play, so there is no fixed
crisis dataset to run out of or overfit. Measured on single_v4: one estimate
(~4 CPU-seconds) is as informative as ~8 full games (~70 CPU-seconds), and it
ranks models the same way full games do.

```bash
# clean start boards from recorded games (once per source model)
python experiments/record_games.py models/single_v4.json --games 500
python experiments/make_start_states.py runs/games/single_v4.jsonl.gz      # -> runs/starts/single_v4.json

# train the single model; optimizer: ga (default) or cem (cross-entropy method)
python training/train.py --model single --features holes,bumpiness,wells,landing_height,sz_fit \
    --init models/single_v7.json --starts runs/starts/single_v7.json --fitness splitting --workers 8 --out models/X.json
python training/train.py --model single --fitness games --games 8      # full games as fitness
python training/train.py --model single --quick                        # smoke test
python training/watch.py                    # live plot (5-min refresh + button, --text for terminal)
```

## Compare

```bash
# fast screen with splitting estimates (paired, held-out estimate seeds)
python experiments/compare_splitting.py models/single_v4.json models/X.json --estimates 100
# final answer: full games, paired, held-out seeds (>= 1000 games to see ~10% differences)
python experiments/compare.py models/single_v4.json models/X.json --games 1000 --max-pieces 10000000   # running averages every 60s (--report-every)
```

## Analyse games for new features

```bash
python experiments/record_games.py models/single_v4.json --games 500
python experiments/analyze_games.py runs/games/single_v4.jsonl.gz   # -> results/game_analysis/<model>/report.html
```

The report is how `wells` and `hole_depth` were found. The method (record
failures, measure warning power and added information, then validate) is
described in [docs/ANALYSIS_METHOD.md](docs/ANALYSIS_METHOD.md). Reuse it for
future feature searches.

## Project page

```bash
python experiments/build_site.py          # collect results (~1 min) -> docs/index.html
python experiments/build_site.py --reuse  # re-render after template edits
```

Training runs (`runs/`) and results (`results/`) are git-ignored; the page is
their published record. Models worth keeping go in `models/`.

## Results

All numbers are lines cleared on held-out test seeds (`experiments/compare.py`,
paired). `*` = the 95% CI of the paired difference excludes 0.

| model | features | mean lines | median | note |
|---|---|---:|---:|---|
| `single_v8` | 5 (holes, bumpiness, wells, landing height, S/Z fit) | **≥ 5,879,365** | 4,180,864 | 104 games vs v9, 50M-piece cap: 4 capped; 243 games vs v7, 20M cap: ≥ 4,280,028 (66 capped) |
| `single_v9` | 6 (v8 + hole depth, which stayed 0) | ≥ 6,227,082 | 3,799,098 | same 104 games: +6% vs v8, not significant (53/51 wins) |
| `single_v7` | 8 (+landing height, eroded cells, S/Z fit) | ≥ 2,498,084 | 2,831,910 | 200 games vs v4, 10M-piece cap: 82 capped; same 243 games as v8: ≥ 3,415,456 |
| `single_v4` | 5 (no lines) | 493,138 | 336,772 | 1,000 games, 10M-piece cap (50 games: 413,254) |
| `single_v3_gen11` | 6 (lines ≈ 0) | 430,538 | 333,190 | 50 games; same model as v4 in practice |
| `single_v2` | 4 (lines fixed) | 2,527 | 1,432 | 50 games |
| `baseline_single_v1` | 3 effective (old lines bug) | 1,785 | 1,467 | 50 games; the old GA reported 5,968: winner's curse |

What made the difference:
- **Features found from data.** Adding `wells` and `hole_depth`, found by
  analysing 500 recorded baseline deaths, gave ~200× more lines (2.5k → 413k+).
- **Move features, found the same way (v7).** The single_v4 analysis showed S/Z
  pieces make the holes and other pieces made holes even when a hole-free spot
  existed. `landing_height`, `eroded_cells` and `sz_fit` gave **+407% (95% CI
  +363%..+451%), 176 wins / 24 losses** on 200 paired held-out games, even with
  41% of v7's games stopped at the cap.
- **Honest measurement.** Per-game results spread as wide as the mean, so 5-game
  scores are meaningless; every comparison is paired on held-out seeds.
- **Feature ablation (single_v4, 50 games):** without holes, bumpiness or wells
  the bot collapses (−100%); without height −40% (significant); without hole
  depth −18% (not significant). `lines` mattered with 4 features (−31%) but the
  GA set it to ~0 once wells and hole depth existed, so it is dropped.
- **Board features are used up.** The same failure analysis on single_v4 finds
  no candidate board feature that adds information (all |partial r| < 0.02).
- **Death is mostly piece luck.** Boards taken 10 pieces before a recorded
  death recover about half the time with different pieces. S and Z pieces make
  most holes; over half of those holes were unavoidable without knowing the
  next piece.

### Optimizer test (single model, splitting fitness)

GA vs cross-entropy, same budget (24 individuals × 2 splitting estimates × 25
generations), both starting from single_v4:
- Cross-entropy drifted (stronger holes, weaker height penalty) and picked lucky
  samples: 1.3–1.5M estimated lines in training, 0.33–0.57M on validation.
  Splitting screen vs single_v4: 0.91× (0.79–1.03).
- The GA stayed next to single_v4 (holes −7.720 vs −7.737). Splitting screen:
  1.18× (1.04–1.33), but **1,000 full games: +0.3% (95% CI −8%..+9%),
  487 wins / 511 losses: no difference.** The borderline splitting result was a
  false positive, so splitting is a screen and full games decide.
- Conclusion: single_v4 is as good as these 5 features get. The next gains have
  to come from new information (move features, lookahead), not the optimizer.
  The move features then delivered exactly that (below).
  The GA is the default (its archive re-tests promising genomes; plain CEM
  needs far more evaluations per sample under this much noise).

### Move features (single_v7)

Trained from single_v4 with 8 features, same GA + splitting setup (40
generations × 30 individuals × 3 estimates, 45 minutes):
- Splitting screen: **11.1× (95% CI 9.5–13.0×)** estimated lines vs single_v4.
- Full games, 200 pairs, 10M-piece cap: single_v4 492,628, single_v7 ≥ 2,498,084
  mean lines (median 2.83M), **+407%, 176/24 wins**. 82 v7 games hit the cap.
- Weights: `landing_height` replaced `height` (height → 0), `sz_fit` +1.15,
  `eroded_cells` and `hole_depth` 0; holes −8.6, wells −1.0, bumpiness −0.77.
- The splitting estimate overstates v7 (~6M lines) but ranks it right. Unlike
  the +18% optimizer result, this effect is far outside the noise on both.
- **Ablation** (v7 with one feature off, no retraining, splitting screen):
  without `landing_height` 0.01×, with v4's `height` in its place 0.03×,
  without `sz_fit` 0.70× (0.52–0.93). Landing height carries the gain; S/Z fit
  adds ~30%.
- **single_v8** = v7 retrained with only its 5 nonzero weights, on start boards
  from v7's own play: splitting screen 1.32× (1.06–1.64); **243 full-game pairs,
  20M-piece cap: +25% (95% CI +11%..+39%), 144/98 wins**, with more v8 games
  capped (66 vs 28), so the true gap is larger. `sz_fit` grew to 1.67.
- **Failure analysis of single_v7** (500 games, 470 deaths, mean 4.0M lines;
  report in `docs/analysis/single_v7/report.html`): S/Z still make the most
  holes but fewer (9.5% of their moves, v4 12%); spirals now start with the
  surface degrading (the first move after the last healthy board made a hole
  in 29% of games, v4 56%); **hole depth adds information again (+0.11)**,
  while v7/v8 have it at 0.
- **single_v9 = v8 + hole depth** (allowed either sign, start boards from v8's
  play): the GA kept hole depth at **0**. Splitting screen 1.12× (0.91–1.36);
  104 full-game pairs, 50M-piece cap: +6% (95% CI −20%..+31%), 53/51 wins. No
  difference, so single_v8 stays the best model. Hole depth predicts trouble but
  does not help choose moves. The same games put v8 at 5.9M mean lines (4 of
  104 capped). Next: the next-piece preview (lookahead).

### Regime switching (concluded)

The original question was whether different weight sets per situation (e.g.
"holes ≥ X → repair weights", "height ≥ Y → danger weights") beat one set.
**Answer: no.**
- 4 features: `regime_v2` 2,687 vs `single_v2` 2,527 (+6%, not significant).
- 5 features, 3 regimes: `regime_v4` 247,897 vs `single_v4` 413,254
  (−40%, significant). The GA set the danger trigger so high it never fired;
  the normal weights drifted under noise.
- 2 regimes, normal frozen at single_v4 (`repair_v5`): 1,000 paired games,
  +2% (95% CI −6%..+10%), 490 wins / 503 losses. Repair only triggers at
  7 holes (1% of moves), too late to matter.
- Repair weights trained on recorded crisis boards: 76% recovery on training
  boards but 71% on held-out boards, the same as single_v4. It learned the
  boards, not a skill.

## Layout

```
tetris/            engine and AI
  game.py          board, drop, line clear, simulate_move (non-destructive)
  pieces.py        7 tetrominoes, seeded uniform / 7-bag generators
  features.py      height, lines, holes, bumpiness, wells, hole_depth (+ board stats)
  policy.py        Policy: weight set(s) + optional regime rules; JSON load/save
  play.py          play_game, record_game (fast recorder), GameRecorder, seed ranges
  fastcore.c/.py   C port of the hot path + episodes from any board with stop rules
  splitting.py     multilevel-splitting estimate of expected game length
training/          ga.py (GA / cross-entropy over named genes), train.py (CLI), watch.py (live plot)
experiments/       compare.py (full games), compare_splitting.py (fast screen),
                   record_games.py + analyze_games.py (failure analysis),
                   make_start_states.py, build_site.py + site_template.html (project page)
models/            saved models (JSON)
demo.py            terminal demo     demo_pygame.py  graphical demo
docs/              index.html (project page), HEURISTICS.md (how it works),
                   ANALYSIS_METHOD.md (failure-analysis method), earlier research notes
```

See [docs/HEURISTICS.md](docs/HEURISTICS.md) for the features, training and
how noise is kept under control.
