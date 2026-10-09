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

## Regime-switching policies (`tetris/policy.py`): concluded

> **Status (Oct 2026): concluded, not developed further.** No regime model beat
> the single model: 3 regimes lost −40% (significant), a 2-regime model with the
> normal weights frozen was +2% (95% CI −6%..+10%, 1,000 games), and repair
> weights trained on recorded crisis boards did not generalise (76% recovery on
> training boards, 71% on held-out boards = no gain). The code below still works
> so old models load and play; new work targets the single model.

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
`holes`, `bumpiness`, `wells`, `hole_depth`. Supported operators: `>=`, `>`, `<=`, `<`.

A single-weight model is just a policy with one default rule. A regime model
whose regimes all share one weight set plays move-for-move like that single
model (tested in `tests/test_policy.py`).

To add a scenario, add a template to `TEMPLATES` in `tetris/policy.py`. If it
uses a new stat, add threshold bounds in `training/ga.py`. Then train with
`--model <template>`.

## Training (`training/ga.py`)

Two choices: the **fitness** (what a genome is scored on) and the **optimizer**.

### Fitness: full games or multilevel splitting

`--fitness games` scores a genome by lines per full game. For strong models
that is expensive and noisy: about one death per million pieces (~9 CPU-seconds
per game) and a per-game spread as wide as the mean (sd of log lines 1.25).

`--fitness splitting` (`tetris/splitting.py`) estimates the expected game
length from short episodes instead. Deaths follow a ladder of hole counts.
Measured on single_v4 from clean boards:

| holes reached | pieces until it happens | P(death from there) |
|---|---:|---:|
| ≥ 2 | 108 | 0 |
| ≥ 6 | 2,324 | 0.1% |
| ≥ 10 | 29,210 | 2.1% |

So `pieces per death ≈ T / (P(6→10) · P(10→14) · P(14→18) · P(18→death))`,
where T is the mean time from a clean board to 6 holes and each P is "reach the
next level before recovering to a clean board (no holes, height ≤ 8)". Each
factor is a common event: 40 episodes from recorded clean boards
(`experiments/make_start_states.py`) measure T and give level-6 boards, and
each level runs 8 continuations from up to 40 boards. The crisis boards are
reached by the evaluated policy's own play, so nothing is learned from a fixed
set of states.

Checked against full games: it ranks single_v4 > no hole depth > no height >
single_v2 > baseline like full games do, the gaps match (log ratio 0.17 vs 0.19
real, 0.43 vs 0.52), and single_v4's scale is close (1.45M vs ~1.2M pieces per
death). One estimate costs ~4 CPU-seconds with sd(log) ≈ 0.45, worth ~8 full
games: about 17× more information per CPU-second. The fitness value is
ln(pieces per death); logs print it as estimated lines (÷ 2.5 pieces per line).

### Optimizers

GA (`--optimizer ga`, the default):

- **Genome:** named genes such as `default.holes` (weights) and `repair.threshold`
  (an integer switch point). The single model has one gene per feature (6, or fewer with `--features`);
  the 3-regime model has 3× that plus 2 thresholds (20 with all 6 features).
  Features left out are fixed at weight 0.
- **Operators:** tournament selection (k=5), uniform crossover (70%), Gaussian
  mutation (20% per gene, σ = 10% of the gene's range, thresholds rounded),
  and 5 elites.
- **Common random numbers:** every individual in a generation plays the same
  seeds, so selection compares strategies, not piece luck.
- **Archive:** each evaluation of a genome is accumulated, and selection (elites
  and tournaments) uses that accumulated mean, not just the current generation.
  Elites are re-played every generation, so a lucky genome keeps being tested
  until it regresses. (Before Oct 9, 2026, selection used only the current
  generation's games, so a genome with two lucky generations could drop out of
  the elite and stay at the top of the archive untested.)
- **Final pick:** the top archive candidates are re-played on separate
  validation seeds, and the best validation mean is saved.
- **Seeding:** half of the population starts from `--init` (default: the
  baseline). For the regime template the baseline weights are copied into
  every regime, so the regime model starts exactly where the single model
  does and only diverges where switching helps.

Cross-entropy method (`--optimizer cem`), the standard for Tetris weights
(Szita & Lőrincz, 2006): each generation samples the population from a
Gaussian per gene (individual 0 is the mean itself), keeps the best 25%, and
refits mean and spread. Extra noise (3% of each gene's range, decaying to 0 at
80% of the run) keeps the search from collapsing early. With `--init` it starts
at that model with a spread of 10% of each range. Every sample is new, so there
is no lucky-archive problem; the final pick validates the final mean against
the best samples.

Seed ranges never overlap (`tetris/play.py`): test 0…, validation 1,000,000…,
training 2,000,000…, analysis 3,000,000…, splitting training 4,000,000…,
splitting validation 5,000,000…, site chart 6,000,000…, splitting test
7,000,000….

## Speed: the C core

With `wells` and `hole_depth` the models got good enough that games last
hundreds of thousands of lines, and the Python engine (~1,500 pieces/s) became
the bottleneck: v3 training saturated its 20k-piece cap. `tetris/fastcore.c`
ports the hot path (column tops, drop, line clear, bit-parallel `board_stats`
using popcount on row bitmasks, `evaluate`, regime selection, 1-ply lookahead,
move search) and runs at ~140k pieces/s per core. It makes exactly the same
decisions as Python (0 mismatches over 104k compared pieces; enforced by
`tests/test_fastcore.py`), so results from both engines are interchangeable.

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
