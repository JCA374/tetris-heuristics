# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Heuristic Tetris AI (no deep learning). Every drop is scored with a weighted sum
of 6 features (height, lines, holes, bumpiness, wells, hole_depth), and the
weights are evolved with a GA. Current research question: does a **regime-switching** policy
(different weight sets chosen by board-state rules) beat a single weight set?
See README.md for results and docs/HEURISTICS.md for the design.

## Commands

```bash
python -m pytest tests                                    # all tests (fast, ~5s)
python demo.py [--model models/X.json] [--delay 0]        # terminal demo
python training/train.py --model single|regime --workers 8 --out models/X.json
python training/train.py --model regime --quick           # smoke test
python experiments/compare.py models/A.json models/B.json --games 50
python experiments/record_games.py models/X.json --games 500         # board logs
python experiments/analyze_games.py runs/games/X.jsonl.gz            # feature research report
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
- `tetris/policy.py` `Policy`: ordered rules (`stat`/`op`/`threshold`, and the last one
  is the default) with one weight set per regime. The regime is selected from the
  **pre-move** board, then used for all candidates and lookahead.
  `Policy.single(w)` is a one-rule policy. `TEMPLATES` defines the trainable rule sets.
- `tetris/play.py` `play_game(policy, seed, max_pieces, lookahead, randomizer, recorder)`.
  Seed ranges: test 0…, validation 1M…, train 2M…, analysis 3M…. Never mix them.
- `tetris/fastcore.c` (+ `fastcore.py` ctypes bridge): C port of drop, line clear,
  `board_stats`/`evaluate`, regime selection and move search. `play_game` uses it
  automatically unless `on_move`/`recorder` hooks are given (`engine='python'` forces
  Python). Pieces still come from the Python generators, so seeds match. It must stay
  **bit-identical** to Python: same move order, strict `>` tie-break, same float
  summation order, built with `-ffp-contract=off`; `tests/test_fastcore.py` checks it.
  Built to `tetris/_build/` (git-ignored), keyed by source hash.
- `training/ga.py`: genes `<regime>.<feature>` and `<regime>.threshold`. Uses
  common random numbers per generation, an archive of accumulated evaluations,
  and a final pick on validation seeds.

## Conventions

- Core code is stdlib-only. matplotlib and pygame are optional imports.
- Performance matters (GA plays millions of pieces). Benchmark with
  `python training/train.py --bench` after touching game.py or features.py, and
  make sure moves stay identical (seeded games give the same lines).
- To compare models, always use `experiments/compare.py` (paired, held-out seeds,
  ≥ 50 games). Single games or 5-game means are far too noisy.
- New features: add to `FEATURES`/`board_stats`/`evaluate` in `tetris/features.py`
  and to `WEIGHT_BOUNDS` in `training/ga.py`, **and** to `fastcore.c` (`N_FEAT`,
  `board_stats`, `evaluate`) and `fastcore.py` (the FEATURES assert); run
  `tests/test_fastcore.py`. Check the definition against
  `experiments/analyze_games.py` if it came from there.
- New board scenarios: add a template to `TEMPLATES` (plus threshold bounds in
  `training/ga.py` for new stats). New stats must also go into `STATS` in
  `fastcore.py` and `select_regime` in `fastcore.c`.
- Strong models play hundreds of thousands of lines per game; always pass a
  `--max-pieces` cap and watch for capped games (they hide differences).
- `runs/`, `results/` and `logs/` are git-ignored. Keep models worth keeping in `models/`.
