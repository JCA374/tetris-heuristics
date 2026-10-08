"""
Board features for heuristic evaluation.

The four classic features (Lee 2013):
- height:    aggregate height, sum of column heights (minimize)
- lines:     lines cleared by the move(s) being evaluated (maximize)
- holes:     empty cells with a filled cell above them (minimize)
- bumpiness: sum of |height difference| between adjacent columns (minimize)

`lines` is not a property of the board: completed rows are already cleared by the
time a simulated board exists, so the caller passes how many lines the move cleared.
(Counting full rows on the simulated board, as the old code did, always gave 0.)

Two features added after analysing 500 recorded baseline games (Oct 2026,
experiments/analyze_games.py), the two strongest signals beyond the four above:
- wells:      cumulative wells, sum of d*(d+1)/2 over every column, where d is how far
              the column sits below its lower neighbour (walls count as infinitely
              high). Penalises deep 1-wide gaps that only an I-piece can fill;
              deaths cluster in I-piece droughts.
- hole_depth: for every hole, the number of filled cells above it in its column.
              A hole under one cell is easy to uncover, one under six is permanent.

Models without weights for a feature use 0 (see Policy), so older 4-feature
models behave exactly as before.
"""

FEATURES = ('height', 'lines', 'holes', 'bumpiness', 'wells', 'hole_depth')


def board_stats(game):
    """
    Single pass over the board.

    Returns:
        (heights, holes, hole_depth) where heights is a per-column list
    """
    board = game.board
    first = 0  # skip the fully empty rows at the top
    while first < game.height and not any(board[first]):
        first += 1
    heights = []
    holes = 0
    hole_depth = 0
    for column in zip(*board[first:]):
        n = len(column)
        empty = column.count(0)
        if empty == n:
            heights.append(0)
            continue
        top = 0
        while column[top] == 0:
            top += 1
        heights.append(n - top)
        if empty > top:  # every empty cell below the top is a hole
            holes += empty - top
            filled = 0
            for cell in column[top:]:
                if cell == 0:
                    hole_depth += filled
                else:
                    filled += 1
    if not heights:
        heights = [0] * game.width
    return heights, holes, hole_depth


def bumpiness(heights):
    return sum(abs(heights[i] - heights[i + 1]) for i in range(len(heights) - 1))


def wells(heights):
    """Cumulative wells: sum of d*(d+1)/2 over column depths below the lower neighbour."""
    total = 0
    last = len(heights) - 1
    for i, h in enumerate(heights):
        left = heights[i - 1] if i > 0 else 10 ** 6
        right = heights[i + 1] if i < last else 10 ** 6
        d = min(left, right) - h
        if d > 0:
            total += d * (d + 1) // 2
    return total


def compute_features(game, lines=0):
    """All features as a dict."""
    heights, holes, hole_depth = board_stats(game)
    return {
        'height': sum(heights),
        'lines': lines,
        'holes': holes,
        'bumpiness': bumpiness(heights),
        'wells': wells(heights),
        'hole_depth': hole_depth,
    }


def evaluate(game, lines, weights):
    """Weighted sum of features (higher is better). Hot path: avoids building dicts."""
    if game.game_over:
        return float('-inf')
    heights, holes, hole_depth = board_stats(game)
    score = (weights['height'] * sum(heights)
             + weights['lines'] * lines
             + weights['holes'] * holes
             + weights['bumpiness'] * bumpiness(heights)
             + weights['hole_depth'] * hole_depth)
    if weights['wells']:
        score += weights['wells'] * wells(heights)
    return score


# Board statistics that regime rules can condition on (computed on the board
# *before* the current piece is placed).
def regime_stats(game):
    heights, holes, hole_depth = board_stats(game)
    return {
        'max_height': max(heights),
        'agg_height': sum(heights),
        'holes': holes,
        'bumpiness': bumpiness(heights),
        'wells': wells(heights),
        'hole_depth': hole_depth,
    }
