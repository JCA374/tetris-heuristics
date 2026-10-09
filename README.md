# Tetris AI: heuristics, regime switching and a genetic algorithm

A Tetris bot that scores every possible drop with a weighted sum of board
features (height, lines, holes, bumpiness, wells, hole depth). The weights are evolved by a genetic algorithm. The current
experiment asks whether a **regime-switching** model, which uses different
weights depending on the board (e.g. "holes ≥ X → repair weights", "height ≥ Y
→ danger weights"), beats a single set of weights.

No dependencies are needed for the core, training or the terminal demo.
Games run in a small C core (`tetris/fastcore.c`, compiled automatically with
the system `cc` on first use, ~100× faster). It plays move-for-move like the
Python engine, which remains the fallback when no compiler is available.
`matplotlib` (training plot), `pygame` (graphical demo) and `pytest` are optional.

## Quick start

```bash
python demo.py                                  # watch the best model in models/
python demo.py --model models/regime_v2.json    # shows the active regime live
python demo.py --list                           # all models and their weights
python demo_pygame.py --model models/single_v2.json

python -m pytest tests                          # test suite
```

## Train and compare

```bash
# Same settings for both models, so they see the same training seeds
python training/train.py --model single --workers 8 --out models/single_v2.json
python training/train.py --model regime --workers 8 --out models/regime_v2.json
python training/train.py --model regime --quick          # 10-second smoke test
python training/watch.py                                 # live plot of running trainings (--text for terminal)
python training/train.py --model single --features height,lines,holes,bumpiness   # original 4 features only

# Paired benchmark on held-out seeds
python experiments/compare.py models/baseline_single_v1.json models/single_v2.json models/regime_v2.json --games 50
```

## Analyse games for new features

```bash
python experiments/record_games.py models/baseline_single_v1.json --games 500
python experiments/analyze_games.py runs/games/baseline_single_v1.jsonl.gz   # -> results/game_analysis/<model>/report.html
```

The report is how `wells` and `hole_depth` were found. The method (record
failures, measure warning power and added information, then validate) is
described in [docs/ANALYSIS_METHOD.md](docs/ANALYSIS_METHOD.md). Reuse it for
future feature searches.

Each training run writes `runs/<timestamp>_<model>/` (checkpoint, final model,
`evolution.png`). Comparisons write `results/compare_<timestamp>.json`. Both
folders are git-ignored. Models worth keeping go in `models/`.

## Results

All numbers are lines cleared on held-out test seeds (`experiments/compare.py`,
paired, 50 games, 3M-piece cap unless noted). The model JSON files in `models/`
are the ones measured. `*` = the 95% CI of the paired difference excludes 0.

| model | features | mean lines | median | vs single_v4 (paired) |
|---|---|---:|---:|---|
| `single_v4` | 5 (no lines) | **413,254** | 272,173 | reference (4/50 games capped) |
| `single_v3_gen11` | 6 (lines ≈ 0) | 430,538 | 333,190 | +17k (−140k..+169k), same model in practice |
| `regime_v4` | 5, 3 regimes | 247,897 | 180,388 | **−165k (−275k..−58k) \*** |
| `regime_v2` | 4, 3 regimes | 2,687 | 1,560 | (vs single_v2: +160, not significant) |
| `single_v2` | 4 (lines fixed) | 2,527 | 1,432 | |
| `baseline_single_v1` | 3 effective (old lines bug) | 1,785 | 1,467 | the old GA reported 5,968: winner's curse |

**Answer to the research question (so far): no.** A regime-switching policy
did not beat a single weight set. With 4 features it was +6% (not
significant); with 5 features it is significantly *worse* (−40%).
- `regime_v4` hardly switches: normal 98%, repair (holes ≥ 7) 2%, danger
  (height ≥ 15) 0%. Its *normal* weights drifted away from the good single
  model (height 0, hole_depth −0.9), and that is where it lost.
- It started from the single model copied into every regime, so it could have
  stayed equal. With 20 genes, 4 games per evaluation and lines per game
  spread almost as wide as the mean, selection followed noise: train 308k →
  validation 276k → test 248k.
- `single_v4` ≈ `single_v3_gen11` (practically identical weights): 40 more
  generations did not improve the single model either. The 5-feature linear
  model looks converged.

Other findings:
- **Features matter far more than regimes.** Adding `wells` and `hole_depth`
  (found by analysing 500 recorded baseline deaths, see docs/HEURISTICS.md)
  gave ~200× more lines (1.8k → 413k).
- **`lines` ablation:** with 4 features, removing `lines` cost −784 lines
  (significant). With 6 features, a no-lines copy of regime_v3 scored +3,085
  (not significant) and single_v3 had evolved `lines` ≈ 0, so v4 drops it.
- **Board height** (single_v3, median lines): 10 rows → 530, 12 → 2,620,
  14 → 8,572, 16 → 11,994.

Ideas not tried yet: more games per evaluation (or a shorter board to make
games shorter and fitness less noisy), regimes on a stat that actually varies
in good play (e.g. `wells`, `bumpiness`), and 2-piece lookahead.

## Layout

```
tetris/            engine and AI
  game.py          board, drop, line clear, simulate_move (non-destructive)
  pieces.py        7 tetrominoes, seeded uniform / 7-bag generators
  features.py      height, lines, holes, bumpiness, wells, hole_depth (+ regime stats)
  policy.py        Policy: ordered regime rules -> weight sets; JSON load/save
  play.py          play_game(policy, seed, ...), GameRecorder, seed ranges
  fastcore.c/.py   C port of the hot path (drop, features, regimes, move search) + ctypes bridge
training/          ga.py (generic named-gene GA), train.py (CLI), watch.py (live plot)
experiments/       compare.py (paired benchmark), record_games.py + analyze_games.py
models/            saved models (JSON)
demo.py            terminal demo     demo_pygame.py  graphical demo
docs/              HEURISTICS.md (how it works) + earlier research notes
                   (those refer to the old src/ layout)
```

See [docs/HEURISTICS.md](docs/HEURISTICS.md) for the features, how regimes are
chosen, and how the GA keeps noise under control.
