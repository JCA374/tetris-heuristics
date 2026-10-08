import os
import sys

# Make the repo root importable (tetris/, training/) when running pytest from anywhere
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
