# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Heuristic Tetris AI (no deep learning). Every drop is scored with a weighted sum
of 4 features (height, lines, holes, bumpiness), and the weights are evolved
with a GA. Current research question: does a **regime-switching** policy
(different weight sets chosen by board-state rules) beat a single weight set?
See README.md for results and docs/HEURISTICS.md for the design.

## Commands

```bash
python -m pytest tests                                    # all tests (fast, ~5s)
python demo.py [--model models/X.json] [--delay 0]        # terminal demo
python training/train.py --model single|regime --workers 8 --out models/X.json
python training/train.py --model regime --quick           # smoke test
python experiments/compare.py models/A.json models/B.json --games 50
```

## Architecture

- `tetris/game.py` `TetrisGame`: board is a list of rows (row 0 = top), 0 = empty,
  otherwise the piece name. `simulate_move()` must stay non-destructive. The AI
  depends on it. `get_drop_row` uses column tops with a scan fallback, and
  `tests/test_engine.py` checks it against the reference scan.
- `tetris/features.py`: `evaluate(game, lines, weights)` is the hot path. `lines`
  is passed in (lines cleared by the move), because cleared rows are gone from
  the simulated board.
- `tetris/policy.py` `Policy`: ordered rules (`stat`/`op`/`threshold`, and the last one
  is the default) with one weight set per regime. The regime is selected from the
  **pre-move** board, then used for all candidates and lookahead.
  `Policy.single(w)` is a one-rule policy. `TEMPLATES` defines the trainable rule sets.
- `tetris/play.py` `play_game(policy, seed, max_pieces, lookahead, randomizer)`.
  Seed ranges: test 0…, validation 1M…, train 2M…. Never mix them.
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
- New board scenarios: add a template to `TEMPLATES` (plus threshold bounds in
  `training/ga.py` for new stats). No code changes elsewhere.
- `runs/`, `results/` and `logs/` are git-ignored. Keep models worth keeping in `models/`.
