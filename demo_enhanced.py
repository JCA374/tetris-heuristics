#!/usr/bin/env python3
"""
Enhanced Tetris AI Demo with Visual Effects

Features:
- Color-coded pieces
- Live statistics graph
- Smooth animations
- Next piece preview box
- Performance metrics
"""

import argparse
import time
import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tetris_game import TetrisGame
from tetris_ai import TetrisAI
from tetris_pieces import SevenBagGenerator, get_random_piece, ALL_PIECES


# ANSI color codes
class Colors:
    """Terminal colors for pretty output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # Piece colors
    CYAN = '\033[96m'      # I piece
    YELLOW = '\033[93m'    # O piece
    MAGENTA = '\033[95m'   # T piece
    GREEN = '\033[92m'     # S piece
    RED = '\033[91m'       # Z piece
    BLUE = '\033[94m'      # J piece
    ORANGE = '\033[38;5;214m'  # L piece

    # UI colors
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    BG_BLACK = '\033[40m'
    BG_GRAY = '\033[100m'


# Piece color mapping
PIECE_COLORS = {
    'I': Colors.CYAN,
    'O': Colors.YELLOW,
    'T': Colors.MAGENTA,
    'S': Colors.GREEN,
    'Z': Colors.RED,
    'J': Colors.BLUE,
    'L': Colors.ORANGE,
}


def clear_screen():
    """Clear the terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')


def draw_piece_preview(piece, label="CURRENT"):
    """Draw a colored preview of a piece."""
    color = PIECE_COLORS.get(piece.name, Colors.WHITE)

    # Get piece coordinates (first rotation)
    coords = piece.get_rotation(0)

    # Find bounding box
    min_row = min(r for r, c in coords)
    max_row = max(r for r, c in coords)
    min_col = min(c for r, c in coords)
    max_col = max(c for r, c in coords)

    # Create small grid
    height = max_row - min_row + 1
    width = max_col - min_col + 1
    grid = [[' ' for _ in range(width)] for _ in range(height)]

    # Fill grid
    for r, c in coords:
        grid[r - min_row][c - min_col] = '█'

    # Draw
    lines = []
    lines.append(f"{Colors.BOLD}{label}:{Colors.RESET}")
    lines.append(f"┌{'─' * (width * 2)}┐")
    for row in grid:
        line = '│' + color
        for cell in row:
            line += cell + cell  # Double width for square appearance
        line += Colors.RESET + '│'
        lines.append(line)
    lines.append(f"└{'─' * (width * 2)}┘")
    lines.append(f"  {color}{Colors.BOLD}{piece.name}{Colors.RESET}")

    return lines


def draw_colored_board(game):
    """Draw the game board with colors (simplified version without piece tracking)."""
    lines = []

    # Top border
    lines.append(f"{Colors.BOLD}┌{'─' * 20}┐{Colors.RESET}")

    # Board rows
    for row in game.board:
        line = f"{Colors.BOLD}│{Colors.RESET}"
        for cell in row:
            if cell == 0:
                line += f"{Colors.BG_BLACK} {Colors.RESET}"
            else:
                # Use gray for placed pieces (we don't track piece types)
                line += f"{Colors.WHITE}█{Colors.RESET}"
        line += f"{Colors.BOLD}│{Colors.RESET}"
        lines.append(line)

    # Bottom border
    lines.append(f"{Colors.BOLD}└{'─' * 20}┘{Colors.RESET}")

    return lines


def draw_stats_bar(lines_cleared, max_lines):
    """Draw a horizontal bar graph for lines cleared."""
    if max_lines == 0:
        max_lines = 100

    bar_width = 30
    filled = min(int((lines_cleared / max_lines) * bar_width), bar_width)
    empty = bar_width - filled

    bar = f"{Colors.GREEN}{'█' * filled}{Colors.GRAY}{'░' * empty}{Colors.RESET}"
    return bar


def print_enhanced_game_state(game, current_piece, next_piece, move_num, stats, ai_name, use_lookahead):
    """Print enhanced game state with visual effects."""
    clear_screen()

    # Header
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.WHITE}   🎮  TETRIS AI - {ai_name.upper()}{Colors.RESET}")
    if use_lookahead:
        print(f"{Colors.BOLD}{Colors.MAGENTA}   🔮  ONE-PIECE LOOKAHEAD ACTIVE{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}\n")

    # Get board and piece previews
    board_lines = draw_colored_board(game)
    current_preview = draw_piece_preview(current_piece, "CURRENT")

    if next_piece and use_lookahead:
        next_preview = draw_piece_preview(next_piece, "NEXT")
    else:
        next_preview = []

    # Calculate stats
    max_lines = max(stats['max_lines'], game.lines_cleared) if stats['max_lines'] > 0 else 100

    # Layout: Board on left, info on right
    for i in range(max(len(board_lines), 25)):
        line = ""

        # Board column
        if i < len(board_lines):
            line += board_lines[i]
        else:
            line += " " * 22

        line += "  "

        # Info column
        if i == 0:
            line += f"{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}"
        elif i == 1:
            line += f"{Colors.BOLD}{Colors.WHITE} GAME STATISTICS{Colors.RESET}"
        elif i == 2:
            line += f"{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}"
        elif i == 3:
            line += ""
        elif i == 4:
            line += f" {Colors.BOLD}Move:{Colors.RESET} {Colors.CYAN}#{move_num}{Colors.RESET}"
        elif i == 5:
            line += f" {Colors.BOLD}Lines:{Colors.RESET} {Colors.GREEN}{game.lines_cleared}{Colors.RESET}"
        elif i == 6:
            bar = draw_stats_bar(game.lines_cleared, max_lines)
            line += f" {bar}"
        elif i == 7:
            line += f" {Colors.BOLD}Score:{Colors.RESET} {Colors.YELLOW}{game.score:,}{Colors.RESET}"
        elif i == 8:
            line += f" {Colors.BOLD}Pieces:{Colors.RESET} {game.pieces_placed}"
        elif i == 9:
            line += ""
        elif i == 10:
            line += f"{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}"
        elif i == 11:
            line += f"{Colors.BOLD}{Colors.WHITE} SESSION STATS{Colors.RESET}"
        elif i == 12:
            line += f"{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}"
        elif i == 13:
            line += ""
        elif i == 14:
            line += f" {Colors.BOLD}Best:{Colors.RESET} {Colors.GREEN}{stats['max_lines']}{Colors.RESET} lines"
        elif i == 15:
            line += f" {Colors.BOLD}Avg:{Colors.RESET} {stats['avg_lines']:.1f} lines"
        elif i == 16:
            line += f" {Colors.BOLD}Games:{Colors.RESET} {stats['games_played']}"
        elif i == 17:
            line += ""
        elif i >= 18 and i < 18 + len(current_preview):
            preview_line = current_preview[i - 18]
            line += f" {preview_line}"
        elif next_preview and i >= 18 + len(current_preview) + 1 and i < 18 + len(current_preview) + 1 + len(next_preview):
            preview_line = next_preview[i - (18 + len(current_preview) + 1)]
            line += f" {preview_line}"

        print(line)

    # Footer
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}")
    print(f"{Colors.GRAY}  Press Ctrl+C to stop  |  Speed: {1000/stats['delay']:.0f} moves/sec{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}\n")


def enhanced_demo(ai_name="Defensive Strategy", weights=None, use_lookahead=False, delay=150, max_pieces=None):
    """
    Run enhanced demo with visual effects.

    Args:
        ai_name: Name to display
        weights: AI weights dict
        use_lookahead: Enable one-piece lookahead
        delay: Delay in ms between moves
        max_pieces: Max pieces to place (None = unlimited)
    """
    # Create AI
    ai = TetrisAI(weights=weights)

    # Show startup screen
    clear_screen()
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.WHITE}   🎮  TETRIS AI - ENHANCED DEMO{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}\n")
    print(f"  {Colors.BOLD}Strategy:{Colors.RESET} {ai_name}")
    print(f"  {Colors.BOLD}Lookahead:{Colors.RESET} {'ON 🔮' if use_lookahead else 'OFF'}")
    print(f"  {Colors.BOLD}Speed:{Colors.RESET} {delay}ms delay ({1000/delay:.0f} moves/sec)")
    print(f"\n  {Colors.BOLD}Weights:{Colors.RESET}")
    for key, val in ai.weights.items():
        color = Colors.GREEN if val > 0 else Colors.RED
        print(f"    {key:12s}: {color}{val:+.6f}{Colors.RESET}")
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}")
    print(f"\n{Colors.BOLD}  Starting in 3 seconds...{Colors.RESET}")
    time.sleep(3)

    # Session statistics
    stats = {
        'games_played': 0,
        'max_lines': 0,
        'total_lines': 0,
        'avg_lines': 0.0,
        'delay': delay
    }

    try:
        while True:
            # New game
            game = TetrisGame()
            stats['games_played'] += 1

            # Setup piece generation
            if use_lookahead:
                piece_generator = SevenBagGenerator()
                current_piece = piece_generator.get_next_piece()
                next_piece = piece_generator.get_next_piece()
            else:
                current_piece = get_random_piece()
                next_piece = None

            move_num = 0

            # Game loop
            while not game.game_over:
                if max_pieces and move_num >= max_pieces:
                    break

                # Display current state
                print_enhanced_game_state(game, current_piece, next_piece, move_num, stats, ai_name, use_lookahead)

                # Wait for animation
                time.sleep(delay / 1000.0)

                # Find best move
                move = ai.get_best_move(game, current_piece, next_piece=next_piece)

                if move is None:
                    game.game_over = True
                    break

                rotation, col = move

                # Make the move
                game.place_piece(current_piece, rotation, col)
                move_num += 1

                # Advance to next piece
                if use_lookahead:
                    current_piece = next_piece
                    next_piece = piece_generator.get_next_piece()
                else:
                    current_piece = get_random_piece()

            # Update session stats
            stats['total_lines'] += game.lines_cleared
            stats['max_lines'] = max(stats['max_lines'], game.lines_cleared)
            stats['avg_lines'] = stats['total_lines'] / stats['games_played']

            # Show final board one more time
            print_enhanced_game_state(game, current_piece, next_piece, move_num, stats, ai_name, use_lookahead)

            # Game over message
            print(f"\n{Colors.BOLD}{Colors.RED}   ⚠️  GAME OVER  ⚠️{Colors.RESET}")
            print(f"\n{Colors.BOLD}   Final Score: {Colors.YELLOW}{game.lines_cleared}{Colors.RESET} {Colors.BOLD}lines{Colors.RESET}")
            print(f"\n{Colors.GRAY}   Starting new game in 2 seconds...{Colors.RESET}\n")
            time.sleep(2)

    except KeyboardInterrupt:
        # Final statistics
        clear_screen()
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.WHITE}   📊  SESSION SUMMARY{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}\n")
        print(f"  {Colors.BOLD}Games Played:{Colors.RESET} {stats['games_played']}")
        print(f"  {Colors.BOLD}Total Lines:{Colors.RESET} {Colors.GREEN}{stats['total_lines']}{Colors.RESET}")
        print(f"  {Colors.BOLD}Average:{Colors.RESET} {Colors.YELLOW}{stats['avg_lines']:.1f}{Colors.RESET} lines/game")
        print(f"  {Colors.BOLD}Best Game:{Colors.RESET} {Colors.CYAN}{stats['max_lines']}{Colors.RESET} lines")
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}\n")
        print(f"{Colors.BOLD}  Thanks for watching! 🎮{Colors.RESET}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Enhanced Tetris AI Demo with Visual Effects',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run with default settings
  %(prog)s --lookahead              # Enable one-piece lookahead
  %(prog)s --delay 100              # Faster animation
  %(prog)s --max-pieces 100         # Stop each game after 100 pieces
  %(prog)s --speed fast             # Preset: fast mode
  %(prog)s --speed slow             # Preset: slow mode for presentations
        """
    )

    parser.add_argument(
        '--delay', '-d',
        type=int,
        default=None,
        help='Delay between moves in milliseconds (default: 150)'
    )

    parser.add_argument(
        '--lookahead',
        action='store_true',
        help='Enable one-piece lookahead'
    )

    parser.add_argument(
        '--max-pieces', '-p',
        type=int,
        default=None,
        help='Maximum pieces per game (default: unlimited)'
    )

    parser.add_argument(
        '--speed', '-s',
        choices=['slow', 'normal', 'fast', 'turbo'],
        default='normal',
        help='Animation speed preset'
    )

    args = parser.parse_args()

    # Speed presets
    speed_delays = {
        'slow': 300,
        'normal': 150,
        'fast': 75,
        'turbo': 25
    }

    delay = args.delay if args.delay else speed_delays[args.speed]

    # Use defensive weights (best performer)
    weights = {
        'height': -0.600000,
        'lines': 0.500000,
        'holes': -0.800000,
        'bumpiness': -0.300000
    }

    enhanced_demo(
        ai_name="Defensive Strategy",
        weights=weights,
        use_lookahead=args.lookahead,
        delay=delay,
        max_pieces=args.max_pieces
    )


if __name__ == '__main__':
    main()
