# Heuristics, regimes and training

## How a move is chosen

For every piece the AI tries every (rotation, column) drop, simulates the board
after it, and scores that board with a weighted sum of features. The highest
score wins. With `--lookahead` each candidate is scored by the best placement
of the *next* piece on top of it (≈ 30×30 simulations per piece).

```
score = w_height * aggregate_height
      + w_lines  * lines_cleared_by_the_move
      + w_holes  * holes
      + w_bump   * bumpiness
      + w_wells  * cumulative_wells
      + w_depth  * hole_depth
```

## Features (`tetris/features.py`)

| feature | definition | sign |
|---|---|---|
| `height` | sum of the 10 column heights | negative: keep the stack low |
| `lines` | lines cleared by the move being evaluated (both moves with lookahead) | positive: reward clears |
| `holes` | empty cells with a filled cell somewhere above them in the same column | negative: holes are hard to clear |
| `bumpiness` | sum of `|h[i] - h[i+1]|` over adjacent columns | negative: a flat surface fits more pieces |
| `wells` | sum of `d(d+1)/2` over columns, where `d` is how far a column sits below its lower neighbour (walls count as infinitely high) | negative: deep 1-wide gaps need an I-piece |
| `hole_depth` | for every hole, the filled cells above it in its column | negative: buried holes are permanent |

`wells` and `hole_depth` were added in October 2026 after analysing 500 recorded
baseline games (see *Finding new features* below). Models saved without weights
for them get 0, so they play exactly as before.

Weights are scale-invariant: multiplying all of them by the same positive
number picks the same moves. Only the ratios matter.

> **Historic bug (fixed Oct 2026):** the old evaluator counted *full rows on the
> board after the move*, but `place_piece()` clears those rows first, so the
> feature was always 0 and the `lines` weight did nothing. Every model trained
> before the fix effectively had three features. `models/baseline_single_v1.json`
> stores `lines = 0.0` so it plays exactly as it did then.

## Regime-switching policies (`tetris/policy.py`)

A policy is an ordered list of rules, each naming a regime with its own weight
set. The last rule is the unconditional default:

```json
"rules": [
  {"name": "repair", "stat": "holes",      "op": ">=", "threshold": 3},
  {"name": "danger", "stat": "max_height", "op": ">=", "threshold": 12},
  {"name": "normal"}
]
```

Before each piece the rules are checked top to bottom against the **current
board**, and the first match wins. That regime's weights then score every
candidate move for this piece. The regime is chosen from the pre-move board on
purpose: if each candidate picked its own regime, scores from different weight
sets would be compared against each other, which is meaningless.

Stats a rule can test (`features.regime_stats`): `max_height`, `agg_height`,
`holes`, `bumpiness`. Supported operators: `>=`, `>`, `<=`, `<`.

A single-weight model is just a policy with one default rule. A regime model
whose regimes all share one weight set plays move-for-move like that single
model (tested in `tests/test_policy.py`).

To add a scenario, add a template to `TEMPLATES` in `tetris/policy.py`. If it
uses a new stat, add threshold bounds in `training/ga.py`. Then train with
`--model <template>`.

## Training (`training/ga.py`)

- **Genome:** named genes such as `normal.holes` (weights) and `repair.threshold`
  (an integer switch point). The single model has 4 genes; the 3-regime model has 14.
- **Operators:** tournament selection (k=5), uniform crossover (70%), Gaussian
  mutation (20% per gene, σ = 10% of the gene's range, thresholds rounded),
  and 5 elites.
- **Common random numbers:** every individual in a generation plays the same
  seeds, so selection compares strategies, not piece luck.
- **Archive:** each evaluation of a genome is accumulated. Elites are re-played
  every generation, so their mean converges instead of being one lucky sample.
- **Final pick:** the top archive candidates are re-played on separate
  validation seeds, and the best validation mean is saved.
- **Seeding:** half of the population starts from `--init` (default: the
  baseline). For the regime template the baseline weights are copied into
  every regime, so the regime model starts exactly where the single model
  does and only diverges where switching helps.

Seed ranges never overlap (`tetris/play.py`): test 0…, validation 1,000,000…,
training 2,000,000….

## Finding new features

```bash
python experiments/record_games.py models/baseline_single_v1.json --games 500
python experiments/analyze_games.py runs/games/baseline_single_v1.jsonl.gz
```

`record_games.py` saves, per game, the final board, the last 300 boards before
the end (with move, regime and lines cleared), a snapshot every 100 pieces, the
piece that could not be placed, and piece droughts at death. `analyze_games.py`
computes ~15 candidate features on every board and writes
`results/game_analysis/<model>/report.html` with: a gallery of final boards,
cell/hole heatmaps, feature trajectories before death, warning power (AUC) and
added information beyond the current features (partial correlation), death
causes, and how the spiral starts from the last healthy board.

What the baseline analysis found (500 games):
- Deaths are slow spirals: typically 30-70 pieces from the last healthy board.
- 53% of deaths happen 12+ pieces into an I-piece drought (16% expected by
  chance), and the I-piece is almost never the one that can't be placed: the
  board becomes I-dependent.
- 47% of holes at death are in the two wall columns (20% if spread evenly).
- Strongest added information beyond height/holes/bumpiness: hole depth
  (+0.13 partial correlation with dying sooner) and cumulative wells (+0.12).

## Why scores need many games

Lines per game for a fixed policy span roughly 10× (e.g. 175 to 4,500 for the
baseline over 16 seeds). A 5-game mean is very noisy, and the best of
thousands of noisy means is badly inflated. The old GA reported 5,968 lines
for a model whose held-out mean is about 1,850. That is why
`experiments/compare.py` uses many games and paired, same-seed comparisons.
