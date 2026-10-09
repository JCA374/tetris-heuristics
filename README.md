# Tetris AI: heuristics, data-driven features and noise-aware training

A Tetris bot that scores every possible drop with a weighted sum of board
features (height, holes, bumpiness, wells, hole depth). The weights are tuned
by a genetic algorithm or the cross-entropy method. The project has gone from
1,785 to about 500,000 lines per game by recording how the bot dies,
finding the features that predict it, and measuring every change on held-out
games.

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
python demo.py --model models/single_v4.json
python demo.py --list                           # all models and their weights
python demo_pygame.py --model models/single_v4.json   # left half of the screen; UP/DOWN speed, M = max (~30k moves/s); slows down by itself at 14 holes

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
python training/train.py --model single --features height,holes,bumpiness,wells,hole_depth \
    --init models/single_v4.json --fitness splitting --optimizer cem --workers 8 --out models/X.json
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
| `single_v4` | 5 (no lines) | **493,138** | 336,772 | 1,000 games, 10M-piece cap (50 games: 413,254) |
| `single_v3_gen11` | 6 (lines ≈ 0) | 430,538 | 333,190 | 50 games; same model as v4 in practice |
| `single_v2` | 4 (lines fixed) | 2,527 | 1,432 | 50 games |
| `baseline_single_v1` | 3 effective (old lines bug) | 1,785 | 1,467 | 50 games; the old GA reported 5,968: winner's curse |

What made the difference:
- **Features found from data.** Adding `wells` and `hole_depth`, found by
  analysing 500 recorded baseline deaths, gave ~200× more lines (2.5k → 413k+).
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
  The GA is the default (its archive re-tests promising genomes; plain CEM
  needs far more evaluations per sample under this much noise).

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
