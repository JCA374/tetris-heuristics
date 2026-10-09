# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Heuristic Tetris AI (no deep learning). Every drop is scored with a weighted sum
of board features (height, holes, bumpiness, wells, hole_depth; `lines` exists
but is 0 in current models), and the weights are tuned with a GA or the
cross-entropy method. **Focus: the single model (one weight set).** The
regime-switching research is concluded (never beat the single model); keep its
code working (old models must load and play) but do not develop it further.
See README.md for results and docs/HEURISTICS.md for the design.

## Commands

```bash
python -m pytest tests                                    # all tests (~1 min)
python demo.py [--model models/X.json] [--delay 0]        # terminal demo
python experiments/record_games.py models/X.json --games 500         # board logs (fast, C core)
python experiments/make_start_states.py runs/games/X.jsonl.gz        # clean start boards for splitting
python training/train.py --model single --features height,holes,bumpiness,wells,hole_depth \
    --init models/X.json --fitness splitting --optimizer cem|ga --workers 8 --out models/Y.json
python training/train.py --model single --quick           # smoke test
python experiments/compare_splitting.py models/A.json models/B.json --estimates 100   # fast screen
python experiments/compare.py models/A.json models/B.json --games 1000 --max-pieces 10000000   # final
python experiments/analyze_games.py runs/games/X.jsonl.gz            # failure-analysis report
python experiments/build_site.py [--reuse]                           # project page docs/index.html
```

## Architecture

- `tetris/game.py` `TetrisGame`: board is a list of rows (row 0 = top), 0 = empty,
  otherwise the piece name. `simulate_move()` must stay non-destructive. The AI
  depends on it. `get_drop_row` uses column tops with a scan fallback, and
  `tests/test_engine.py` checks it against the reference scan.
- `tetris/features.py`: `evaluate(game, lines, weights)` is the hot path. `lines`
  is passed in (lines cleared by the move), because cleared rows are gone from
  the simulated board. Models without a weight for a feature get 0 (Policy),
  so adding features never changes how old models play.
- `tetris/policy.py` `Policy`: ordered rules with one weight set per regime (the
  last rule is the default). A single model is `Policy.single(w)`. `TEMPLATES`
  holds the trainable rule sets ('single' is the one in use).
- `tetris/play.py` `play_game(...)` and `record_game(...)` (C core plays, Python
  replays only the end with a GameRecorder). Seed ranges: test 0…, validation 1M…,
  train 2M…, analysis 3M…, splitting train 4M… / validation 5M… / test 7M…,
  site crisis chart 6M…. Never mix them.
- `tetris/fastcore.c` (+ `fastcore.py` ctypes bridge): C port of drop, line clear,
  `board_stats`/`evaluate`, regime selection and move search, plus `play_until`
  (episodes from any board that stop at a hole level, on recovery or game over;
  `fastcore.play_from`). `play_game` uses the C core automatically unless
  `on_move`/`recorder` hooks are given. It must stay **bit-identical** to Python:
  same move order, strict `>` tie-break, same float summation order, built with
  `-ffp-contract=off`; `tests/test_fastcore.py` checks it.
- `tetris/splitting.py` `estimate(policy, starts, seed)`: multilevel splitting
  estimate of ln(pieces per death) (levels 6/10/14/18 holes, then death). The
  training fitness for strong models; deterministic for a given seed.
- `training/ga.py`: genes `<regime>.<feature>`; optimizer 'ga' (archive-mean
  selection, elites re-evaluated) or 'cem' (cross-entropy: sample, keep top 25%,
  refit, decaying extra noise); fitness 'games' or 'splitting'; common random
  numbers per generation; final pick on validation seeds/estimates.

## Conventions

- Core code is stdlib-only. matplotlib, numpy and pygame are optional imports.
- Performance matters. Benchmark with `python training/train.py --bench` after
  touching game.py or features.py, and make sure moves stay identical.
- Noise: one game's lines spread as wide as the mean (log sd 1.25). Never judge
  from single games or few-game means. Screen with `compare_splitting.py`,
  conclude with `compare.py` (paired, held-out, ≥ 1000 games for ~10% effects).
- Analysis/feature research: follow docs/ANALYSIS_METHOD.md (the user's preferred
  report style: self-contained HTML, one question per chart, dataviz palette).
- New features: add to `FEATURES`/`board_stats`/`evaluate` in `tetris/features.py`
  and to `WEIGHT_BOUNDS` in `training/ga.py`, **and** to `fastcore.c` (`N_FEAT`,
  `board_stats`, `evaluate`) and `fastcore.py` (the FEATURES assert); run
  `tests/test_fastcore.py`. Check the definition against
  `experiments/analyze_games.py` if it came from there.
- Strong models play ~1M pieces per game; always pass a `--max-pieces` cap to
  full-game runs and watch for capped games (they hide differences).
- After new results, update `experiments/build_site.py` (RUNS / compare paths) and
  rebuild `docs/index.html`; the page is the published record of the git-ignored
  runs/results. Charts follow the dataviz palette and docs/ANALYSIS_METHOD.md style.
- `runs/`, `results/` and `logs/` are git-ignored. Keep models worth keeping in `models/`.
