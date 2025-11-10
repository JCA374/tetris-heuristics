#!/usr/bin/env python3
"""
Tetris AI with Pygame Graphics

Connects the AI to a real Tetris game with proper graphics, animations, and colors.
Requires: pip install pygame
"""

import pygame
import sys
import os
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tetris_game import TetrisGame
from tetris_ai import TetrisAI
from tetris_pieces import SevenBagGenerator, get_random_piece

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
WINDOW_HEIGHT = 720

# FPS
FPS = 60


class TetrisGameGUI:
    """Pygame GUI for Tetris AI."""

    def __init__(self, use_lookahead=False, speed=1.0):
        """
        Initialize the game GUI.

        Args:
            use_lookahead: Enable one-piece lookahead
            speed: Game speed multiplier (higher = faster)
        """
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Tetris AI - Pygame Demo")
        self.clock = pygame.time.Clock()
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)

        # Game state
        self.game = TetrisGame()
        self.ai = TetrisAI()
        self.use_lookahead = use_lookahead
        self.speed = speed
        self.move_delay = max(50, int(500 / speed))  # ms between moves

        # Piece generation
        if use_lookahead:
            self.piece_generator = SevenBagGenerator()
            self.current_piece = self.piece_generator.get_next_piece()
            self.next_piece = self.piece_generator.get_next_piece()
        else:
            self.current_piece = get_random_piece()
            self.next_piece = None

        # Timing
        self.last_move_time = pygame.time.get_ticks()

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

        # Piece name
        name_text = self.font_medium.render(piece.name, True, color)
        name_rect = name_text.get_rect(center=(x + box_size // 2, box_y + box_size + 20))
        self.screen.blit(name_text, name_rect)

    def draw_stats(self):
        """Draw game statistics."""
        y = STATS_Y

        # Current game stats
        self.draw_text("GAME STATS", STATS_X, y, self.font_small, WHITE)
        y += 35

        stats = [
            ("Lines", f"{self.game.lines_cleared}", (0, 255, 100)),
            ("Score", f"{self.game.score:,}", (255, 215, 0)),
            ("Pieces", f"{self.game.pieces_placed}", WHITE),
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
            ("Best", f"{self.best_lines}", (0, 255, 255)),
            ("Average", f"{avg_lines:.1f}", (255, 165, 0)),
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

        # Current piece preview
        self.draw_piece_preview(self.current_piece, PREVIEW_X, PREVIEW_Y, "CURRENT")

        # Next piece preview (if lookahead enabled)
        if self.next_piece:
            self.draw_piece_preview(self.next_piece, PREVIEW_X, PREVIEW_Y + 170, "NEXT")

        # Controls hint
        hint = "SPACE: Pause | Q: Quit"
        self.draw_text(hint, 20, WINDOW_HEIGHT - 30, self.font_small, GRAY)

        pygame.display.flip()

    def make_move(self):
        """Let AI make a move."""
        if self.game.game_over:
            return

        # Get best move from AI
        move = self.ai.get_best_move(self.game, self.current_piece, next_piece=self.next_piece)

        if move is None:
            self.game.game_over = True
            return

        rotation, col = move

        # Make the move
        self.game.place_piece(self.current_piece, rotation, col)

        # Advance to next piece
        if self.use_lookahead:
            self.current_piece = self.next_piece
            self.next_piece = self.piece_generator.get_next_piece()
        else:
            self.current_piece = get_random_piece()

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
        score_text = self.font_medium.render(f"Lines: {self.game.lines_cleared}", True, (0, 255, 100))
        score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 10))
        self.screen.blit(score_text, score_rect)

        # Restart hint
        restart_text = self.font_small.render("New game in 2 seconds...", True, WHITE)
        restart_rect = restart_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 60))
        self.screen.blit(restart_text, restart_rect)

        pygame.display.flip()
        pygame.time.wait(2000)

        # Reset game
        self.game = TetrisGame()
        if self.use_lookahead:
            self.piece_generator = SevenBagGenerator()
            self.current_piece = self.piece_generator.get_next_piece()
            self.next_piece = self.piece_generator.get_next_piece()
        else:
            self.current_piece = get_random_piece()
            self.next_piece = None

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

            # Update game
            if not paused and not self.game.game_over:
                current_time = pygame.time.get_ticks()
                if current_time - self.last_move_time > self.move_delay:
                    self.make_move()
                    self.last_move_time = current_time

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
    parser.add_argument('--lookahead', action='store_true',
                        help='Enable one-piece lookahead')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Game speed multiplier (default: 1.0, try 2.0 for faster)')

    args = parser.parse_args()

    try:
        game = TetrisGameGUI(use_lookahead=args.lookahead, speed=args.speed)
        game.run()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure pygame is installed:")
        print("  pip install pygame")
        sys.exit(1)


if __name__ == '__main__':
    main()
