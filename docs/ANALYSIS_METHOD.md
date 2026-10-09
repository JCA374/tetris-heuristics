# Failure-analysis report: the method

`experiments/record_games.py` + `experiments/analyze_games.py` produce
`results/game_analysis/<model>/report.html` ("Game analysis: <model>"). That
report is how `wells` and `hole_depth` were found. Adding them took the model
from ~1.8k to ~400k lines. Use this method again for any new feature search
here, and as the template for data analysis in other ML projects.

## The idea

Don't guess features. **Record how the model fails, then measure which
candidate signals warn of the failure and which add information beyond what
the model already sees.**

## Steps

1. **Record failures with context** (`record_games.py`). Per game: the final
   state, a rolling window of the last N states before failure (here 300 boards,
   with the action, regime and reward), periodic mid-run snapshots (every 100
   pieces) as the "normal" baseline, and the context at failure (killer piece,
   piece droughts). Use a dedicated seed range (analysis 3M…), never
   train/validation/test seeds. Save it compressed (`.jsonl.gz`, header + one
   record per line). Make the window long enough to see the run-up: 40 boards
   was too short, 300 showed it.
2. **Compute many candidate features** vectorised (numpy) on every logged state:
   the model's current features plus ~12 candidates.
3. **Build the report.** One figure per question, each with a one-line caption:
   1. *What does failure look like?* A gallery of final states, sorted by outcome.
   2. *Where does it happen?* Heatmaps (cells and holes, normal vs at death).
   3. *What drifts before failure?* Trajectories over the last N steps: median
      line, interquartile band, and a dashed typical mid-game level. Current
      features in blue, candidates in orange.
   4. *What predicts failure?* Left: **AUC** of each feature alone for "fails
      within K steps" on mid-game snapshots, with the model's own score as a
      reference line. Right: **partial correlation** with time-to-failure after
      regressing out the current features. This is the key chart: it shows what
      is *new* information.
   5. *What causes it?* Killer-piece share, drought length at death vs chance,
      and which actions create damage.
   6. *How does the spiral start?* The last healthy state (75th-percentile
      thresholds) followed by +10 and +30 steps, plus the distance from onset
      to death.
4. **Top summary table**: per feature, the mid-game median, the median at
   failure, AUC, added information, and the step where it leaves its normal
   range (first point where the median exceeds the mid-game 90th percentile).
   Also write a `summary.json` with every number, so findings can be quoted
   exactly.
5. **Translate into hypotheses, then test them properly**: add the feature,
   retrain, and compare paired on held-out seeds (`experiments/compare.py`).
   A report finding is a lead, not a result.

## Style

- dataviz reference palette: surface `#fcfcfb`, ink `#0b0b0b` / `#52514e`,
  grid `#e4e3df`, categorical `#2a78d6 #eb6834 #1baf7a #eda100 #e87ba4 #008300
  #4a3aa7 #e34948` in fixed order, one-hue blue ramp for heatmaps.
- Recessive grid, no top/right spines, direct value labels on bar ends.
- A self-contained static HTML page: title, a one-line subtitle with sample
  sizes and definitions, the summary table, then `<section>`s of
  heading + caption + figure. PNGs sit next to it.
- Every chart answers one plain-language question, which is its title.
