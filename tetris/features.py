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
"""

FEATURES = ('height', 'lines', 'holes', 'bumpiness')


def board_stats(game):
    """
    Single pass over the board.

    Returns:
        (heights, holes) where heights is a per-column list
    """
    board = game.board
    first = 0  # skip the fully empty rows at the top
    while first < game.height and not any(board[first]):
        first += 1
    heights = []
    holes = 0
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
        holes += empty - top  # every empty cell below the top is a hole
    if not heights:
        heights = [0] * game.width
    return heights, holes


def bumpiness(heights):
    return sum(abs(heights[i] - heights[i + 1]) for i in range(len(heights) - 1))


def compute_features(game, lines=0):
    """All four features as a dict."""
    heights, holes = board_stats(game)
    return {
        'height': sum(heights),
        'lines': lines,
        'holes': holes,
        'bumpiness': bumpiness(heights),
    }


def evaluate(game, lines, weights):
    """Weighted sum of features (higher is better). Hot path: avoids building dicts."""
    if game.game_over:
        return float('-inf')
    heights, holes = board_stats(game)
    return (weights['height'] * sum(heights)
            + weights['lines'] * lines
            + weights['holes'] * holes
            + weights['bumpiness'] * bumpiness(heights))


# Board statistics that regime rules can condition on (computed on the board
# *before* the current piece is placed).
def regime_stats(game):
    heights, holes = board_stats(game)
    return {
        'max_height': max(heights),
        'agg_height': sum(heights),
        'holes': holes,
        'bumpiness': bumpiness(heights),
    }
