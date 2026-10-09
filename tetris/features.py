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

Three features added in Oct 2026, after the single_v4 failure analysis showed the
board features were used up and most holes come from S/Z pieces:
- landing_height: how high the last piece landed (floor row of its bottom + half its
                  height; Dellacherie). Move feature, set by TetrisGame.place_piece.
- eroded_cells:   rows completed by the last move x the piece's own cells in those
                  rows (Dellacherie). Rewards clears that use the piece itself.
- sz_fit:         how many of S and Z could land on the surface without creating a
                  hole (0-2). Surfaces with room for S/Z avoid forced S/Z holes.

Models without weights for a feature use 0 (see Policy), so older models behave
exactly as before (zero-weight terms are skipped, so scores are bit-identical).
"""

FEATURES = ('height', 'lines', 'holes', 'bumpiness', 'wells', 'hole_depth',
            'landing_height', 'eroded_cells', 'sz_fit')


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


def sz_fit(heights):
    """Number of S/Z pieces (0-2) with at least one hole-free placement on this surface."""
    s = z = 0
    n = len(heights)
    for c in range(n - 1):
        a, b = heights[c], heights[c + 1]
        if not s and (a == b + 1 or (c + 2 < n and a == b and heights[c + 2] == a + 1)):
            s = 1
        if not z and (b == a + 1 or (c + 2 < n and b == heights[c + 2] and a == b + 1)):
            z = 1
        if s and z:
            break
    return s + z


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
        'landing_height': game.last_landing,
        'eroded_cells': game.last_eroded,
        'sz_fit': sz_fit(heights),
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
    if weights['landing_height']:
        score += weights['landing_height'] * game.last_landing
    if weights['eroded_cells']:
        score += weights['eroded_cells'] * game.last_eroded
    if weights['sz_fit']:
        score += weights['sz_fit'] * sz_fit(heights)
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
