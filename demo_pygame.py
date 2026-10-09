#!/usr/bin/env python3
"""
Tetris AI with Pygame Graphics

Connects the AI to a real Tetris game with proper graphics, animations, and colors.
Requires: pip install pygame

Keys: UP/+ faster, DOWN/- slower, M max speed, A auto slow-down on/off, SPACE pause, Q quit.
Up to 100 moves/s the Python engine plays (cells keep their piece colours).
Faster than that the C core plays the same moves (bit-identical) far quicker,
but it does not track piece letters, so cells placed there are drawn gray.

Auto slow-down (A toggles): when the board reaches --slow-at holes (default 14;
about 1 in 6 such crises ends the game) the speed drops to --normal-speed so you
can watch the spiral, and returns to the previous speed once holes are below
--resume-below again (or a new game starts).
The window opens on the left half of the screen (--dock right|none to change)
and can be resized; the picture scales to fit.
"""

import ctypes
import pygame
import sys
import os
import time

from tetris import TetrisGame, Policy, fastcore
from tetris.features import board_stats
from tetris.pieces import make_generator
from demo import default_model

# Initialize Pygame
pygame.init()

# Colors (RGB)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (40, 40, 40)
LIGHT_GRAY = (200, 200, 200)

# Piece colors - vibrant and distinct
COLORS = {
    'I': (0, 240, 240),      # Cyan
    'O': (240, 240, 0),      # Yellow
    'T': (160, 0, 240),      # Purple/Magenta
    'S': (0, 240, 0),        # Green
    'Z': (240, 0, 0),        # Red
    'J': (0, 0, 240),        # Blue
    'L': (240, 160, 0),      # Orange
    'X': (105, 115, 135),    # placed by the C core (piece unknown)
    0: DARK_GRAY             # Empty cell
}

# Game settings
CELL_SIZE = 30
BOARD_WIDTH = 10
BOARD_HEIGHT = 20
BOARD_X = 50
BOARD_Y = 80

# UI Layout
PREVIEW_X = BOARD_X + BOARD_WIDTH * CELL_SIZE + 50
PREVIEW_Y = BOARD_Y
STATS_X = PREVIEW_X
STATS_Y = PREVIEW_Y + 370

# Window size
WINDOW_WIDTH = 750
WINDOW_HEIGHT = 840

# FPS
FPS = 60

# Moves per second; the last level ('max') plays as many moves as fit in each frame
SPEEDS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 'max']
PYTHON_MAX_SPEED = 100   # above this the C core plays (if it is available)
FRAME_BUDGET_MS = 14     # time per frame spent on AI moves at high speed


class PieceQueue:
    """Upcoming pieces; current = items[0], next = items[1]. Shared by the Python and C engines."""

    def __init__(self, randomizer='random'):
        self.generator = make_generator(randomizer, None)
        self.items = []
        self.ensure(2)

    def ensure(self, n):
        while len(self.items) < n:
            self.items.append(self.generator.get_next_piece())

    @property
    def current(self):
        return self.items[0]

    @property
    def next(self):
        return self.items[1]

    def advance(self, n=1):
        del self.items[:n]
        self.ensure(2)


def open_window(dock):
    """Open a resizable window, docked to the left/right half of the desktop if asked."""
    if dock != 'none':
        desk_w, desk_h = pygame.display.get_desktop_sizes()[0]
        width, height = desk_w // 2, desk_h - 80          # leave room for the top bar/title
        x = 0 if dock == 'left' else desk_w - width
        os.environ['SDL_VIDEO_WINDOW_POS'] = f'{x},40'
    else:
        width, height = WINDOW_WIDTH, WINDOW_HEIGHT
    return pygame.display.set_mode((width, height), pygame.RESIZABLE)


class TetrisGameGUI:
    """Pygame GUI for Tetris AI."""

    def __init__(self, policy, model_name, use_lookahead=False, speed=2, randomizer='random', dock='left',
                 slow_at=14, normal_speed=10, resume_below=6):
        """
        Initialize the game GUI.

        Args:
            policy: tetris.policy.Policy to play with
            model_name: shown in the stats panel
            use_lookahead: Enable one-piece lookahead
            speed: moves per second at start (snapped to the nearest level in SPEEDS)
            randomizer: 'random' or 'bag'
            dock: 'left', 'right' or 'none' (window placement)
            slow_at: holes that trigger the automatic slow-down (0 = off)
            normal_speed: moves per second while slowed down
            resume_below: back to the previous speed once holes are below this
        """
        self.window = open_window(dock)
        self.screen = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))   # drawn at fixed size, scaled to the window
        pygame.display.set_caption("Tetris AI - Pygame Demo")
        self.clock = pygame.time.Clock()
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)

        # Game state
        self.game = TetrisGame()
        self.ai = policy
        self.model_name = model_name
        self.randomizer = randomizer
        self.use_lookahead = use_lookahead
        numeric = [v for v in SPEEDS if v != 'max']
        self.speed_index = SPEEDS.index(min(numeric, key=lambda v: abs(v - speed)))
        self.move_credit = 0.0      # fractional moves owed at the current speed
        self.auto_slow = slow_at > 0
        self.slow_at = slow_at or 14
        self.normal_index = SPEEDS.index(min(numeric, key=lambda v: abs(v - normal_speed)))
        self.resume_below = resume_below
        self.slowed_from = None     # speed index to return to after an automatic slow-down
        self.message = None         # (text, colour, until_ms) banner

        # Piece generation
        self.stream = PieceQueue(randomizer)
        self.lib = fastcore._load()          # None without a C compiler: Python only
        self.cpolicy = fastcore.to_cpolicy(policy) if self.lib else None
        self.cgame = None                    # C copy of the game while the C core plays
        self.counts = (ctypes.c_int64 * fastcore.MAX_RULES)()

        # Timing
        self.last_tick = pygame.time.get_ticks()

        # Stats
        self.games_played = 0
        self.best_lines = 0
        self.total_lines = 0

        # Animation
        self.falling_animation = None  # (piece, rotation, col, start_time)

    def draw_cell(self, x, y, color, border=True):
        """Draw a single cell."""
        rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(self.screen, color, rect)

        if border and color != DARK_GRAY:
            # Add 3D effect with lighter and darker borders
            # Lighter top-left
            lighter = tuple(min(255, c + 40) for c in color)
            pygame.draw.line(self.screen, lighter, (x, y), (x + CELL_SIZE - 1, y), 2)
            pygame.draw.line(self.screen, lighter, (x, y), (x, y + CELL_SIZE - 1), 2)

            # Darker bottom-right
            darker = tuple(max(0, c - 40) for c in color)
            pygame.draw.line(self.screen, darker, (x + CELL_SIZE - 1, y), (x + CELL_SIZE - 1, y + CELL_SIZE - 1), 2)
            pygame.draw.line(self.screen, darker, (x, y + CELL_SIZE - 1), (x + CELL_SIZE - 1, y + CELL_SIZE - 1), 2)

    def draw_board(self):
        """Draw the Tetris board."""
        # Draw border
        border_rect = pygame.Rect(BOARD_X - 2, BOARD_Y - 2,
                                   BOARD_WIDTH * CELL_SIZE + 4,
                                   BOARD_HEIGHT * CELL_SIZE + 4)
        pygame.draw.rect(self.screen, WHITE, border_rect, 3)

        # Draw cells
        for row in range(BOARD_HEIGHT):
            for col in range(BOARD_WIDTH):
                x = BOARD_X + col * CELL_SIZE
                y = BOARD_Y + row * CELL_SIZE

                cell_value = self.game.board[row][col]
                if cell_value == 0:
                    color = DARK_GRAY
                else:
                    # Use the piece's original color!
                    # cell_value contains the piece name ('I', 'O', 'T', etc.)
                    color = COLORS.get(cell_value, GRAY)

                self.draw_cell(x, y, color, border=True)

    def draw_piece_preview(self, piece, x, y, label):
        """Draw a piece preview box."""
        # Label
        text = self.font_small.render(label, True, WHITE)
        self.screen.blit(text, (x, y))

        # Box
        box_y = y + 30
        box_size = 120
        pygame.draw.rect(self.screen, WHITE, (x, box_y, box_size, box_size), 2)

        # Get piece coordinates
        coords = piece.get_rotation(0)
        min_row = min(r for r, c in coords)
        max_row = max(r for r, c in coords)
        min_col = min(c for r, c in coords)
        max_col = max(c for r, c in coords)

        # Calculate centering
        piece_width = (max_col - min_col + 1) * CELL_SIZE
        piece_height = (max_row - min_row + 1) * CELL_SIZE
        offset_x = x + (box_size - piece_width) // 2
        offset_y = box_y + (box_size - piece_height) // 2

        # Draw piece
        color = COLORS[piece.name]
        for r, c in coords:
            cell_x = offset_x + (c - min_col) * CELL_SIZE
            cell_y = offset_y + (r - min_row) * CELL_SIZE
            self.draw_cell(cell_x, cell_y, color)


    def draw_stats(self):
        """Draw game statistics."""
        y = STATS_Y

        self.draw_text(self.model_name, STATS_X, y - 35, self.font_small, (0, 240, 240))

        # Current game stats
        self.draw_text("GAME STATS", STATS_X, y, self.font_small, WHITE)
        y += 35

        stats = [
            ("Lines", f"{self.game.lines_cleared:,}", (0, 255, 100)),
            ("Score", f"{self.game.score:,}", (255, 215, 0)),
            ("Pieces", f"{self.game.pieces_placed:,}", WHITE),
            ("Holes", f"{self.holes()}", (255, 80, 80) if self.holes() >= self.slow_at else WHITE),
            ("Speed", self.speed_label(), (255, 100, 255)),
            ("Auto slow", f"at {self.slow_at} holes" if self.auto_slow else "off", GRAY),
        ]

        for label, value, color in stats:
            text = f"{label}: {value}"
            self.draw_text(text, STATS_X, y, self.font_small, color)
            y += 30

        y += 20

        # Session stats
        self.draw_text("SESSION", STATS_X, y, self.font_small, WHITE)
        y += 35

        avg_lines = self.total_lines / self.games_played if self.games_played > 0 else 0
        session_stats = [
            ("Best", f"{self.best_lines:,}", (0, 255, 255)),
            ("Average", f"{avg_lines:,.0f}", (255, 165, 0)),
            ("Games", f"{self.games_played}", WHITE),
        ]

        for label, value, color in session_stats:
            text = f"{label}: {value}"
            self.draw_text(text, STATS_X, y, self.font_small, color)
            y += 30

    def draw_text(self, text, x, y, font, color):
        """Draw text on screen."""
        surface = font.render(text, True, color)
        self.screen.blit(surface, (x, y))

    def draw_header(self):
        """Draw header with title."""
        title = "TETRIS AI"
        title_text = self.font_large.render(title, True, (0, 240, 240))
        title_rect = title_text.get_rect(center=(WINDOW_WIDTH // 2, 25))
        self.screen.blit(title_text, title_rect)

        # Lookahead indicator
        if self.use_lookahead:
            lookahead_text = self.font_small.render("🔮 LOOKAHEAD ON", True, (255, 100, 255))
            self.screen.blit(lookahead_text, (WINDOW_WIDTH // 2 - 80, 55))

    def draw(self):
        """Draw everything."""
        self.screen.fill(BLACK)

        self.draw_header()
        self.draw_board()
        self.draw_stats()

        # Piece previews
        self.draw_piece_preview(self.stream.current, PREVIEW_X, PREVIEW_Y, "CURRENT")
        self.draw_piece_preview(self.stream.next, PREVIEW_X, PREVIEW_Y + 170,
                                "NEXT (lookahead)" if self.use_lookahead else "NEXT")

        # Controls hint
        if self.message and pygame.time.get_ticks() < self.message[2]:
            text = self.font_medium.render(self.message[0], True, self.message[1])
            self.screen.blit(text, text.get_rect(center=(WINDOW_WIDTH // 2, 62)))
        elif self.slowed_from is not None:
            text = self.font_small.render(f"Crisis - watching at normal speed (resumes below {self.resume_below} holes)",
                                          True, (255, 80, 80))
            self.screen.blit(text, text.get_rect(center=(WINDOW_WIDTH // 2, 62)))

        hint = "UP/DOWN: Speed | M: Max | A: Auto slow | SPACE: Pause | Q: Quit"
        self.draw_text(hint, 20, WINDOW_HEIGHT - 30, self.font_small, GRAY)

        self.present()

    def present(self):
        """Scale the fixed-size picture into the (resizable) window, keeping its aspect ratio."""
        win_w, win_h = self.window.get_size()
        scale = min(win_w / WINDOW_WIDTH, win_h / WINDOW_HEIGHT)
        size = (max(1, int(WINDOW_WIDTH * scale)), max(1, int(WINDOW_HEIGHT * scale)))
        self.window.fill(BLACK)
        self.window.blit(pygame.transform.smoothscale(self.screen, size),
                         ((win_w - size[0]) // 2, (win_h - size[1]) // 2))
        pygame.display.flip()

    def holes(self):
        return board_stats(self.game)[1]

    def notify(self, text, colour, seconds=4):
        self.message = (text, colour, pygame.time.get_ticks() + seconds * 1000)

    def check_crisis(self):
        """Automatic slow-down in a crisis and speed-up once the board has recovered."""
        if not self.auto_slow or self.game.game_over:
            return
        holes = self.holes()
        if self.slowed_from is None and holes >= self.slow_at and self.speed_index > self.normal_index:
            self.slowed_from = self.speed_index
            self.speed_index = self.normal_index
            self.move_credit = 0.0
            self.notify(f"CRISIS: {holes} holes - slowed down", (255, 80, 80), seconds=6)
        elif self.slowed_from is not None and holes < self.resume_below:
            self.resume(f"Recovered ({holes} hole{'s' if holes != 1 else ''}) - speeding up")

    def resume(self, text):
        self.speed_index, self.slowed_from = self.slowed_from, None
        self.move_credit = 0.0
        self.notify(text, (0, 255, 100))

    def speed_label(self):
        v = SPEEDS[self.speed_index]
        engine = 'C' if self.lib and (v == 'max' or v > PYTHON_MAX_SPEED) else 'Python'
        return f"{'max' if v == 'max' else f'{v:,}/s'} ({engine})"

    def change_speed(self, step):
        self.slowed_from = None               # the user takes over
        self.speed_index = max(0, min(len(SPEEDS) - 1, self.speed_index + step))
        self.move_credit = 0.0

    def play_frame(self, dt_ms):
        """Make the moves this frame owes at the current speed, within the frame's time budget."""
        v = SPEEDS[self.speed_index]
        if v == 'max':
            owed = float('inf')
        else:
            self.move_credit = min(self.move_credit + v * dt_ms / 1000, v)   # no catch-up bursts after a stall
            owed = int(self.move_credit)
        if self.lib and (v == 'max' or v > PYTHON_MAX_SPEED):
            made = self.play_fast(owed)
        else:
            self.cgame = None                 # the Python game is the truth again
            start = pygame.time.get_ticks()
            made = 0
            while made < owed and not self.game.game_over:
                self.make_move()
                made += 1
                before = self.speed_index
                self.check_crisis()
                if self.speed_index != before:
                    break
                if pygame.time.get_ticks() - start > FRAME_BUDGET_MS:
                    break
        if v != 'max':
            self.move_credit = max(0.0, self.move_credit - made)

    def play_fast(self, owed):
        """Play up to `owed` moves in the C core within the frame budget; returns moves made."""
        if self.cgame is None:               # hand the board over from the Python game
            g = self.cgame = fastcore.CGame(width=self.game.width, height=self.game.height)
            for r, row in enumerate(self.game.board):
                g.rows[r] = sum(1 << c for c, cell in enumerate(row) if cell)
            g.lines, g.pieces, g.score = self.game.lines_cleared, self.game.pieces_placed, self.game.score
        g = self.cgame
        # Stop the C core the moment holes reach slow_at (unless already past it: the user chose to go fast)
        stop = self.slow_at if self.auto_slow and self.slowed_from is None and self.holes() < self.slow_at else 0
        outcome = ctypes.c_int(0)
        deadline = time.perf_counter() + FRAME_BUDGET_MS / 1000
        made = 0
        while made < owed and not g.game_over and time.perf_counter() < deadline:
            n = int(min(owed - made, 500))
            self.stream.ensure(n + 1)          # play() places at most len-1 pieces (the last is the preview)
            seq = (ctypes.c_int8 * (n + 1))(*(fastcore.PIECE_INDEX[p.name] for p in self.stream.items[:n + 1]))
            before = g.pieces
            self.lib.play_until(ctypes.byref(g), ctypes.byref(self.cpolicy), seq, n + 1, int(self.use_lookahead),
                                before + n, self.counts, stop, -1, ctypes.byref(outcome))
            self.stream.advance(g.pieces - before)
            made += g.pieces - before
            if outcome.value == 2:             # crisis level reached
                break
        # Mirror the C game into the Python game for drawing (piece letters are unknown: 'X')
        game = self.game
        game.board = [[('X' if (bits >> c) & 1 else 0) for c in range(game.width)] for bits in g.rows[:game.height]]
        game.lines_cleared, game.pieces_placed, game.score = g.lines, g.pieces, g.score
        game.game_over = bool(g.game_over)
        if outcome.value == 2:
            self.cgame = None                  # continue in Python at normal speed
            self.check_crisis()
        return made

    def make_move(self):
        """Let AI make a move."""
        if self.game.game_over:
            return

        # Get best move from AI
        next_piece = self.stream.next if self.use_lookahead else None
        move = self.ai.get_best_move(self.game, self.stream.current, next_piece=next_piece)

        if move is None:
            self.game.game_over = True
            return

        rotation, col = move

        # Make the move
        self.game.place_piece(self.stream.current, rotation, col)
        self.stream.advance()

    def handle_game_over(self):
        """Handle game over."""
        # Update stats
        self.total_lines += self.game.lines_cleared
        self.best_lines = max(self.best_lines, self.game.lines_cleared)
        self.games_played += 1

        # Draw game over screen
        self.draw()

        # Game over overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        # Game over text
        game_over_text = self.font_large.render("GAME OVER", True, (255, 0, 0))
        game_over_rect = game_over_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 50))
        self.screen.blit(game_over_text, game_over_rect)

        # Final score
        score_text = self.font_medium.render(f"Lines: {self.game.lines_cleared:,}", True, (0, 255, 100))
        score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 10))
        self.screen.blit(score_text, score_rect)

        # Restart hint
        restart_text = self.font_small.render("New game in 2 seconds...", True, WHITE)
        restart_rect = restart_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 60))
        self.screen.blit(restart_text, restart_rect)

        self.present()
        pygame.time.wait(2000)

        # Reset game
        self.game = TetrisGame()
        self.stream = PieceQueue(self.randomizer)
        self.cgame = None
        if self.slowed_from is not None:
            self.resume("New game - back to previous speed")

    def run(self):
        """Main game loop."""
        running = True
        paused = False

        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key in (pygame.K_UP, pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
                        self.change_speed(+1)
                    elif event.key in (pygame.K_DOWN, pygame.K_MINUS, pygame.K_KP_MINUS):
                        self.change_speed(-1)
                    elif event.key == pygame.K_m:
                        self.slowed_from = None
                        self.speed_index = len(SPEEDS) - 1
                    elif event.key == pygame.K_a:
                        self.auto_slow = not self.auto_slow
                        self.notify(f"Auto slow-down {'on' if self.auto_slow else 'off'}", WHITE)
                        if not self.auto_slow and self.slowed_from is not None:
                            self.resume("Auto slow-down off - back to previous speed")

            # Update game
            now = pygame.time.get_ticks()
            if not paused and not self.game.game_over:
                self.play_frame(now - self.last_tick)
            self.last_tick = now

            # Handle game over
            if self.game.game_over:
                self.handle_game_over()

            # Draw
            self.draw()

            # Control frame rate
            self.clock.tick(FPS)

        pygame.quit()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Tetris AI with Pygame Graphics')
    parser.add_argument('--model', help='model JSON (default: best in models/)')
    parser.add_argument('--randomizer', choices=['random', 'bag'], default='random')
    parser.add_argument('--lookahead', action='store_true',
                        help='Enable one-piece lookahead')
    parser.add_argument('--speed', type=float, default=2,
                        help='moves per second at start (1 ... 5000; UP/DOWN change it while playing, M = max)')
    parser.add_argument('--slow-at', type=int, default=14,
                        help='holes that trigger the automatic slow-down (0 = off, default 14)')
    parser.add_argument('--normal-speed', type=float, default=10, help='moves per second while slowed down')
    parser.add_argument('--resume-below', type=int, default=6, help='speed back up once holes are below this')
    parser.add_argument('--dock', choices=['left', 'right', 'none'], default='left',
                        help='place the window on the left/right half of the screen (default: left)')

    args = parser.parse_args()

    try:
        path = args.model or default_model()
        policy = Policy.load(path)
        name = os.path.splitext(os.path.basename(path))[0]
        game = TetrisGameGUI(policy, name, use_lookahead=args.lookahead, speed=args.speed,
                             randomizer=args.randomizer, dock=args.dock,
                             slow_at=args.slow_at, normal_speed=args.normal_speed, resume_below=args.resume_below)
        game.run()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure pygame is installed:")
        print("  pip install pygame")
        sys.exit(1)


if __name__ == '__main__':
    main()
