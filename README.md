# Tetris AI: heuristics, regime switching and a genetic algorithm

A Tetris bot that scores every possible drop with a weighted sum of board
features. The weights are evolved by a genetic algorithm. The current
experiment asks whether a **regime-switching** model, which uses different
weights depending on the board (e.g. "holes ≥ X → repair weights", "height ≥ Y
→ danger weights"), beats a single set of weights.

No dependencies are needed for the core, training or the terminal demo.
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

# Paired benchmark on held-out seeds
python experiments/compare.py models/baseline_single_v1.json models/single_v2.json models/regime_v2.json --games 50
```

Each training run writes `runs/<timestamp>_<model>/` (checkpoint, final model,
`evolution.png`). Comparisons write `results/compare_<timestamp>.json`. Both
folders are git-ignored. Models worth keeping go in `models/`.

## Results

_Pending: training of `single_v2` and `regime_v2` is in progress._

## Layout

```
tetris/            engine and AI
  game.py          board, drop, line clear, simulate_move (non-destructive)
  pieces.py        7 tetrominoes, seeded uniform / 7-bag generators
  features.py      height, lines, holes, bumpiness (+ stats for regime rules)
  policy.py        Policy: ordered regime rules -> weight sets; JSON load/save
  play.py          play_game(policy, seed, ...), seed ranges
training/          ga.py (generic named-gene GA), train.py (CLI)
experiments/       compare.py (paired benchmark)
models/            saved models (JSON)
demo.py            terminal demo     demo_pygame.py  graphical demo
docs/              HEURISTICS.md (how it works) + earlier research notes
                   (those refer to the old src/ layout)
```

See [docs/HEURISTICS.md](docs/HEURISTICS.md) for the features, how regimes are
chosen, and how the GA keeps noise under control.
