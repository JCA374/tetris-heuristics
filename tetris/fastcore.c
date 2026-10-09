/*
 * Fast game core: a C port of the hot path of tetris/game.py, features.py and
 * policy.py, used by tetris/fastcore.py through ctypes.
 *
 * It must make exactly the same decisions as the Python engine (tests compare
 * them on seeded games), so:
 *  - drop rule: hard drop from row 0 straight down (no sliding), like get_drop_row
 *  - moves are tried rotation-major, column-minor; ties keep the first move
 *  - scores are summed in the same order as features.evaluate (build with
 *    -ffp-contract=off so no fused multiply-add changes the rounding)
 *
 * Board: rows[0] is the top row; bit c of a row is column c.
 */

#include <stdint.h>
#include <string.h>
#include <math.h>

#define MAX_H 32
#define N_FEAT 9          /* height, lines, holes, bumpiness, wells, hole_depth,
                             landing_height, eroded_cells, sz_fit */
#define MAX_RULES 8
#define N_PIECES 7
#define MAX_ROT 4

typedef struct {
    int32_t width, height;
    int32_t game_over, pad;
    int64_t lines, pieces, score;
    uint32_t rows[MAX_H];
    int32_t last_landing2;     /* 2 x landing height of the last placement (exact in halves) */
    int32_t last_eroded;       /* eroded cells of the last placement */
} Game;

typedef struct {
    int32_t n_rules;
    int32_t stat[MAX_RULES];       /* -1 = default rule; else index into regime stats */
    int32_t op[MAX_RULES];         /* 0 >=, 1 >, 2 <=, 3 < */
    double threshold[MAX_RULES];
    double w[MAX_RULES][N_FEAT];
} Policy;

static int32_t n_rot[N_PIECES];
static int32_t cells[N_PIECES][MAX_ROT][4][2];   /* (row, col) per cell */
static int32_t p_width[N_PIECES][MAX_ROT];        /* columns spanned */
static int32_t p_low[N_PIECES][MAX_ROT][4];       /* lowest row per spanned column */
static int32_t p_minr[N_PIECES][MAX_ROT], p_maxr[N_PIECES][MAX_ROT];   /* top/bottom cell row */

void set_pieces(const int32_t *rotations, const int32_t *data)
{
    for (int p = 0; p < N_PIECES; p++) {
        n_rot[p] = rotations[p];
        for (int r = 0; r < MAX_ROT; r++)
            for (int c = 0; c < 4; c++) {
                cells[p][r][c][0] = data[((p * MAX_ROT + r) * 4 + c) * 2];
                cells[p][r][c][1] = data[((p * MAX_ROT + r) * 4 + c) * 2 + 1];
            }
        for (int r = 0; r < n_rot[p]; r++) {
            int w = 0;
            for (int c = 0; c < 4; c++) p_low[p][r][c] = -1;
            for (int i = 0; i < 4; i++) {
                int rr = cells[p][r][i][0], cc = cells[p][r][i][1];
                if (cc + 1 > w) w = cc + 1;
                if (rr > p_low[p][r][cc]) p_low[p][r][cc] = rr;
            }
            p_width[p][r] = w;
            p_minr[p][r] = 4;
            p_maxr[p][r] = -1;
            for (int i = 0; i < 4; i++) {
                if (cells[p][r][i][0] < p_minr[p][r]) p_minr[p][r] = cells[p][r][i][0];
                if (cells[p][r][i][0] > p_maxr[p][r]) p_maxr[p][r] = cells[p][r][i][0];
            }
        }
    }
}

static int valid(const Game *g, int p, int rot, int col, int row)
{
    for (int i = 0; i < 4; i++) {
        int r = cells[p][rot][i][0] + row;
        int c = cells[p][rot][i][1] + col;
        if (r < 0 || r >= g->height || c < 0 || c >= g->width)
            return 0;
        if ((g->rows[r] >> c) & 1u)
            return 0;
    }
    return 1;
}

static int drop_row(const Game *g, int p, int rot, int col)
{
    for (int row = 0; row < g->height; row++)
        if (!valid(g, p, rot, col, row))
            return row - 1;
    return g->height - 1;
}

/* Row index of the topmost filled cell per column (height if empty). */
static void column_tops(const Game *g, int *tops)
{
    uint32_t seen = 0, all = (1u << g->width) - 1u;
    for (int c = 0; c < g->width; c++)
        tops[c] = g->height;
    for (int r = 0; r < g->height && seen != all; r++) {
        uint32_t fresh = g->rows[r] & ~seen;
        while (fresh) {
            int c = __builtin_ctz(fresh);
            tops[c] = r;
            fresh &= fresh - 1;
        }
        seen |= g->rows[r];
    }
}

/* Same result as drop_row, using column tops (with the same scan fallback as game.py). */
static int fast_drop_row(const Game *g, const int *tops, int p, int rot, int col)
{
    if (col < 0 || col + p_width[p][rot] > g->width)
        return -1;
    int drop = g->height;
    for (int dc = 0; dc < p_width[p][rot]; dc++) {
        int low = p_low[p][rot][dc];
        if (low < 0)
            continue;
        int top = tops[col + dc];
        if (top <= low)
            return drop_row(g, p, rot, col);
        if (top - low - 1 < drop)
            drop = top - low - 1;
    }
    return drop;
}

static const int64_t LINE_SCORES[5] = {0, 40, 100, 300, 1200};

static int place_at(Game *g, int p, int rot, int col, int row)
{
    if (row < 0) {
        g->game_over = 1;
        return 0;
    }
    for (int i = 0; i < 4; i++)
        g->rows[cells[p][rot][i][0] + row] |= 1u << (cells[p][rot][i][1] + col);
    g->pieces++;

    /* move features (same definitions as TetrisGame.place_piece) */
    uint32_t full = (1u << g->width) - 1u;
    int top_r = p_minr[p][rot], bottom_r = p_maxr[p][rot];
    g->last_landing2 = 2 * (g->height - 1 - (row + bottom_r)) + (bottom_r - top_r);
    int full_rows = 0, own = 0;
    for (int r = row + top_r; r <= row + bottom_r; r++)
        if (g->rows[r] == full)
            full_rows++;
    if (full_rows)
        for (int i = 0; i < 4; i++)
            if (g->rows[cells[p][rot][i][0] + row] == full)
                own++;
    g->last_eroded = full_rows * own;

    /* clear full rows: keep the others in order, add empty rows at the top */
    int dst = g->height - 1, cleared = 0;
    for (int src = g->height - 1; src >= 0; src--) {
        if (g->rows[src] == full)
            cleared++;
        else
            g->rows[dst--] = g->rows[src];
    }
    for (; dst >= 0; dst--)
        g->rows[dst] = 0;
    g->lines += cleared;
    g->score += cleared <= 4 ? LINE_SCORES[cleared] : (int64_t)cleared * 400;
    return 1;
}

static int place(Game *g, int p, int rot, int col)
{
    return place_at(g, p, rot, col, drop_row(g, p, rot, col));
}

typedef struct {
    int64_t agg_height, holes, bumpiness, wells, hole_depth, max_height, sz_fit;
} Stats;

static void board_stats(const Game *g, Stats *s)
{
    int h[32];
    int filled[32];
    int64_t holes = 0, hole_depth = 0;
    uint32_t seen = 0;
    for (int c = 0; c < g->width; c++) {
        h[c] = 0;
        filled[c] = 0;
    }
    for (int r = 0; r < g->height; r++) {
        uint32_t row = g->rows[r];
        uint32_t fresh = row & ~seen;
        while (fresh) {                      /* first filled cell of a column */
            int c = __builtin_ctz(fresh);
            h[c] = g->height - r;
            fresh &= fresh - 1;
        }
        seen |= row;
        uint32_t hole = seen & ~row;         /* empty cells under a filled one */
        holes += __builtin_popcount(hole);
        while (hole) {
            int c = __builtin_ctz(hole);
            hole_depth += filled[c];
            hole &= hole - 1;
        }
        uint32_t f = row;
        while (f) {
            filled[__builtin_ctz(f)]++;
            f &= f - 1;
        }
    }
    int64_t agg = 0, bump = 0, wells = 0, maxh = 0;
    for (int c = 0; c < g->width; c++) {
        agg += h[c];
        if (h[c] > maxh)
            maxh = h[c];
        if (c + 1 < g->width)
            bump += h[c] > h[c + 1] ? h[c] - h[c + 1] : h[c + 1] - h[c];
        int64_t left = c > 0 ? h[c - 1] : 1000000;
        int64_t right = c + 1 < g->width ? h[c + 1] : 1000000;
        int64_t d = (left < right ? left : right) - h[c];
        if (d > 0)
            wells += d * (d + 1) / 2;
    }
    s->agg_height = agg;
    s->holes = holes;
    s->bumpiness = bump;
    s->wells = wells;
    s->hole_depth = hole_depth;
    s->max_height = maxh;
    /* S/Z with a hole-free placement (same rule as features.sz_fit) */
    int sf = 0, zf = 0, n = g->width;
    for (int c = 0; c + 1 < n && !(sf && zf); c++) {
        int a = h[c], b = h[c + 1];
        if (!sf && (a == b + 1 || (c + 2 < n && a == b && h[c + 2] == a + 1)))
            sf = 1;
        if (!zf && (b == a + 1 || (c + 2 < n && b == h[c + 2] && a == b + 1)))
            zf = 1;
    }
    s->sz_fit = sf + zf;
}

/* Same summation order as tetris/features.evaluate */
static double evaluate(const Game *g, int64_t lines, const double *w)
{
    Stats s;
    board_stats(g, &s);
    double score = w[0] * (double)s.agg_height
                 + w[1] * (double)lines
                 + w[2] * (double)s.holes
                 + w[3] * (double)s.bumpiness
                 + w[5] * (double)s.hole_depth;
    if (w[4] != 0.0)
        score += w[4] * (double)s.wells;
    if (w[6] != 0.0)
        score += w[6] * ((double)g->last_landing2 * 0.5);
    if (w[7] != 0.0)
        score += w[7] * (double)g->last_eroded;
    if (w[8] != 0.0)
        score += w[8] * (double)s.sz_fit;
    return score;
}

/* stat ids match fastcore.py: max_height, agg_height, holes, bumpiness, wells, hole_depth */
static int select_regime(const Game *g, const Policy *pol)
{
    if (pol->n_rules == 1)
        return 0;
    Stats s;
    board_stats(g, &s);
    int64_t v[6] = {s.max_height, s.agg_height, s.holes, s.bumpiness, s.wells, s.hole_depth};
    for (int i = 0; i < pol->n_rules; i++) {
        if (pol->stat[i] < 0)
            return i;
        double a = (double)v[pol->stat[i]], t = pol->threshold[i];
        int ok = pol->op[i] == 0 ? a >= t : pol->op[i] == 1 ? a > t : pol->op[i] == 2 ? a <= t : a < t;
        if (ok)
            return i;
    }
    return pol->n_rules - 1;
}

static double lookahead_score(const Game *g, int next, int64_t base_lines, const double *w)
{
    double best = -INFINITY;
    int tops[32];
    column_tops(g, tops);
    for (int rot = 0; rot < n_rot[next]; rot++)
        for (int col = 0; col < g->width; col++) {
            int row = fast_drop_row(g, tops, next, rot, col);
            if (row < 0)
                continue;
            Game sim = *g;
            place_at(&sim, next, rot, col, row);
            double v = evaluate(&sim, sim.lines - base_lines, w);
            if (v > best)
                best = v;
        }
    return best;
}

/* Returns rotation * 64 + column of the best move, or -1 if there is none. */
int best_move(const Game *g, const Policy *pol, int piece, int next, int *regime_out)
{
    int regime = select_regime(g, pol);
    if (regime_out)
        *regime_out = regime;
    const double *w = pol->w[regime];
    double best_score = -INFINITY;
    int best = -1;
    int tops[32];
    column_tops(g, tops);
    for (int rot = 0; rot < n_rot[piece]; rot++)
        for (int col = 0; col < g->width; col++) {
            int row = fast_drop_row(g, tops, piece, rot, col);
            if (row < 0)
                continue;
            Game sim = *g;
            place_at(&sim, piece, rot, col, row);
            double score = next < 0 ? evaluate(&sim, sim.lines - g->lines, w)
                                    : lookahead_score(&sim, next, g->lines, w);
            if (score > best_score) {
                best_score = score;
                best = rot * 64 + col;
            }
        }
    return best;
}

/*
 * Play pieces seq[0..n-1] (seq[i+1] is always the known next piece, so at most
 * n-1 pieces are placed). Stops at game over or when g->pieces reaches
 * max_pieces (< 0 = no cap). Returns the number of pieces consumed.
 */
int64_t play(Game *g, const Policy *pol, const int8_t *seq, int64_t n, int lookahead,
             int64_t max_pieces, int64_t *regime_counts)
{
    int64_t i = 0;
    while (!g->game_over && i + 1 < n) {
        if (max_pieces >= 0 && g->pieces >= max_pieces)
            break;
        int regime;
        int m = best_move(g, pol, seq[i], lookahead ? seq[i + 1] : -1, &regime);
        regime_counts[regime]++;
        if (m < 0) {
            g->game_over = 1;
            break;
        }
        place(g, seq[i], m / 64, m % 64);
        i++;
    }
    return i;
}

/*
 * Episodes with stopping rules (crisis training / evaluation). Like play(), but
 * after every placement:
 *   - stop_holes > 0 and holes >= stop_holes            -> *outcome = 2 (entered a crisis)
 *   - recover_max_height >= 0, no holes, max height <=  -> *outcome = 1 (recovered)
 * Game over -> 3; piece cap or end of sequence -> 0.
 */
int64_t play_until(Game *g, const Policy *pol, const int8_t *seq, int64_t n, int lookahead,
                   int64_t max_pieces, int64_t *regime_counts, int stop_holes, int recover_max_height,
                   int *outcome)
{
    int64_t i = 0;
    Stats s;
    *outcome = 0;
    while (!g->game_over && i + 1 < n) {
        if (max_pieces >= 0 && g->pieces >= max_pieces)
            break;
        int regime;
        int m = best_move(g, pol, seq[i], lookahead ? seq[i + 1] : -1, &regime);
        regime_counts[regime]++;
        if (m < 0) {
            g->game_over = 1;
            break;
        }
        place(g, seq[i], m / 64, m % 64);
        i++;
        if (g->game_over)
            break;
        board_stats(g, &s);
        if (stop_holes > 0 && s.holes >= stop_holes) {
            *outcome = 2;
            break;
        }
        if (recover_max_height >= 0 && s.holes == 0 && s.max_height <= recover_max_height) {
            *outcome = 1;
            break;
        }
    }
    if (g->game_over)
        *outcome = 3;
    return i;
}
