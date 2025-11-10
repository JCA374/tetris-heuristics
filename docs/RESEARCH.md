# Tetris AI Heuristics Research

## Executive Summary

This document summarizes research on implementing a simple, computationally efficient Tetris AI using heuristics. The most practical approach for a simple implementation is a **one-piece lookahead with 4-6 heuristics** optimized either manually or via genetic algorithms.

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Two Main Approaches](#two-main-approaches)
3. [Heuristic Functions](#heuristic-functions)
4. [Computational Considerations](#computational-considerations)
5. [Implementation Examples](#implementation-examples)
6. [Recommended Approach](#recommended-approach)

---

## Core Concepts

### How Tetris AI Works

The basic algorithm:
1. For each falling piece, enumerate ALL possible placements (positions and rotations)
2. Calculate a score for each potential board state using heuristic functions
3. Select the move with the best score
4. Execute the move

### Scoring Formula

Most implementations use a linear combination of heuristics:

```
Score = w1 × height + w2 × lines_cleared + w3 × holes + w4 × bumpiness
```

Where w1, w2, w3, w4 are weights that determine the importance of each factor.

---

## Two Main Approaches

### Approach 1: Four-Feature Heuristic (Simplest)

**Best for:** Quick implementation, low computational cost

**Features:**
1. **Aggregate Height** - Sum of all column heights (minimize)
2. **Complete Lines** - Number of lines that can be cleared (maximize)
3. **Holes** - Empty cells with filled cells above them (minimize)
4. **Bumpiness** - Sum of absolute height differences between adjacent columns (minimize)

**Example Weights (from genetic algorithm):**
```
Height:    -0.7988
Lines:     +0.5223
Holes:     -0.2492
Bumpiness: -0.1646
```

**Performance:** Can clear 2000+ lines in a single game

**Repositories:**
- [takado8/Tetris](https://github.com/takado8/Tetris) (C#)
- [isaaclino/tetris-ai](https://github.com/isaaclino/tetris-ai) (JavaScript)

### Approach 2: Pierre Dellacherie Algorithm (Advanced)

**Best for:** Higher performance, still computationally efficient

**Features (6 total):**
1. **Landing Height** - Height where current piece lands
2. **Eroded Piece Cells** - Cells from dropped piece cleared immediately
3. **Row Transitions** - Empty cells adjacent to filled cells horizontally
4. **Column Transitions** - Empty cells adjacent to filled cells vertically
5. **Holes** - Empty cells with filled cells above
6. **Wells** - Succession of empty cells with filled cells on both sides

**Performance:** Can clear 660,000+ lines on average

**Why it's better:**
- More sophisticated features capture game dynamics better
- "Eroded Piece Cells" rewards immediate line clearing
- Transition metrics identify problematic patterns early

**Repositories:**
- [tetris-bot-protocol/dellacherie](https://github.com/tetris-bot-protocol/dellacherie)
- [yanyongyu/python-tetris](https://github.com/yanyongyu/python-tetris) (Python with El-Tetris)

---

## Heuristic Functions

### Detailed Explanations

#### 1. Aggregate Height
```
Sum of (height of highest block in each column)
```
- Lower is better (more room to play)
- Simple to calculate: O(columns)

#### 2. Complete Lines
```
Count of rows that are completely filled
```
- Higher is better (primary game objective)
- Immediate reward signal

#### 3. Holes
```
Count of empty cells with at least one filled cell above in the same column
```
- Lower is better (holes are hard to clear)
- Critical metric - holes cause game over

**Calculation:**
```python
holes = 0
for col in range(width):
    found_block = False
    for row in range(height):
        if board[row][col] is filled:
            found_block = True
        elif found_block and board[row][col] is empty:
            holes += 1
```

#### 4. Bumpiness
```
Sum of |height[i] - height[i+1]| for all adjacent columns
```
- Lower is better (flat surface is ideal)
- Helps avoid creating wells

**Calculation:**
```python
bumpiness = 0
for i in range(width - 1):
    bumpiness += abs(column_heights[i] - column_heights[i+1])
```

#### 5. Landing Height (Dellacherie)
```
Row where the center of the piece lands
```
- Lower is better (keeps board height down)

#### 6. Eroded Piece Cells (Dellacherie)
```
Number of cells from placed piece that are cleared immediately
```
- Higher is better (rewards immediate line clearing)
- Formula: `lines_cleared × piece_cells_in_cleared_lines`

---

## Computational Considerations

### Lookahead Depth

**No Lookahead:**
- Evaluate only current piece
- Baseline speed

**One-Piece Lookahead:**
- Evaluate current piece and next piece
- **~160× slower** than no lookahead
- Still practical for real-time play

**Two-Piece Lookahead:**
- Evaluate current + next 2 pieces
- **~26,000× slower** than no lookahead
- NOT practical for most use cases

### Recommendation: Stick to one-piece or no lookahead

The computational cost grows exponentially:
- O piece: 9 possible positions
- Z, S, I pieces: 17 possible positions each
- T, L, J pieces: 34 possible positions each
- Average: ~162 total moves per piece

With lookahead, you evaluate: `current_moves × next_moves` = 162 × 162 = 26,244 evaluations!

---

## Implementation Examples

### Python Implementations (Recommended)

#### Simple & Clean (< 600 lines)
**[arton0306/TetrisAi](https://github.com/arton0306/TetrisAi)**
- Only 2 files: `TetrisAi.py` and `TetrisObject.py`
- Includes genetic algorithm for weight optimization
- Best starting point for learning

#### With Pygame Visualization
**[yanyongyu/python-tetris](https://github.com/yanyongyu/python-tetris)**
- Uses Pierre Dellacherie algorithm
- Can be installed via pip
- Good for testing and visualization

#### Comprehensive Tutorial
**[AndrejaNajev/tetris-AI-bot-Python](https://github.com/AndrejaNajev/tetris-AI-bot-Python)**
- Well-documented
- Uses standard 4-feature heuristic
- Good code structure

### JavaScript Implementations

**[isaaclino/tetris-ai](https://github.com/isaaclino/tetris-ai)**
- 74% JavaScript, runs in browser
- Clear separation of game logic and AI
- Visual interface for testing

### C# Implementation

**[takado8/Tetris](https://github.com/takado8/Tetris)**
- Includes genetic algorithm implementation
- Optimized weights documented in README
- Achieved 2000+ lines cleared

---

## Recommended Approach

### For a Simple, Working Implementation:

**Option 1: Hand-Tuned Weights (Fastest to implement)**

1. Implement basic Tetris game engine
2. Add 4 heuristics: height, lines, holes, bumpiness
3. Start with these weights:
   ```
   height:    -0.51
   lines:     +0.76
   holes:     -0.36
   bumpiness: -0.18
   ```
4. Test and manually adjust weights

**Estimated Lines of Code:** 300-500 lines in Python

---

**Option 2: Genetic Algorithm (Better performance)**

1. Implement basic Tetris game engine
2. Add 4 heuristics
3. Implement simple genetic algorithm:
   - Population: 20 individuals
   - Generations: 50-100
   - Fitness: Number of lines cleared
   - Mutation rate: 5%
4. Let it run overnight to find optimal weights

**Estimated Lines of Code:** 500-800 lines in Python

---

**Option 3: Pierre Dellacherie Algorithm (Best performance)**

1. Implement basic Tetris game engine
2. Add 6 Dellacherie heuristics
3. Use documented weights from research papers
4. Fine-tune if needed

**Estimated Lines of Code:** 600-1000 lines in Python

**Expected Performance:** 600,000+ lines cleared

---

## Sample Code Structure

### Minimal Implementation Outline

```python
# tetris_game.py
class TetrisGame:
    def __init__(self, width=10, height=20):
        self.board = [[0] * width for _ in range(height)]
        self.width = width
        self.height = height

    def get_possible_moves(self, piece):
        """Returns all possible (rotation, column) pairs"""
        pass

    def place_piece(self, piece, rotation, column):
        """Places piece and returns resulting board state"""
        pass

    def clear_lines(self):
        """Clears completed lines and returns count"""
        pass

# tetris_ai.py
class TetrisAI:
    def __init__(self, weights):
        self.weights = weights

    def calculate_aggregate_height(self, board):
        """Sum of column heights"""
        heights = []
        for col in range(len(board[0])):
            for row in range(len(board)):
                if board[row][col] != 0:
                    heights.append(len(board) - row)
                    break
        return sum(heights)

    def calculate_holes(self, board):
        """Count holes (empty cells below filled cells)"""
        holes = 0
        for col in range(len(board[0])):
            found_block = False
            for row in range(len(board)):
                if board[row][col] != 0:
                    found_block = True
                elif found_block:
                    holes += 1
        return holes

    def calculate_bumpiness(self, board):
        """Sum of height differences between adjacent columns"""
        heights = self.get_column_heights(board)
        bumpiness = 0
        for i in range(len(heights) - 1):
            bumpiness += abs(heights[i] - heights[i+1])
        return bumpiness

    def calculate_complete_lines(self, board):
        """Count number of complete lines"""
        complete = 0
        for row in board:
            if all(cell != 0 for cell in row):
                complete += 1
        return complete

    def evaluate_board(self, board):
        """Calculate score using weighted heuristics"""
        score = (
            self.weights['height'] * self.calculate_aggregate_height(board) +
            self.weights['lines'] * self.calculate_complete_lines(board) +
            self.weights['holes'] * self.calculate_holes(board) +
            self.weights['bumpiness'] * self.calculate_bumpiness(board)
        )
        return score

    def get_best_move(self, game, piece):
        """Find best move by trying all possibilities"""
        best_score = float('-inf')
        best_move = None

        for rotation, column in game.get_possible_moves(piece):
            # Simulate placing piece
            simulated_board = game.simulate_move(piece, rotation, column)
            score = self.evaluate_board(simulated_board)

            if score > best_score:
                best_score = score
                best_move = (rotation, column)

        return best_move

# genetic_algorithm.py
class GeneticAlgorithm:
    def __init__(self, population_size=20, mutation_rate=0.05):
        self.population_size = population_size
        self.mutation_rate = mutation_rate

    def create_individual(self):
        """Create random weights"""
        return {
            'height': random.uniform(-1, 1),
            'lines': random.uniform(-1, 1),
            'holes': random.uniform(-1, 1),
            'bumpiness': random.uniform(-1, 1)
        }

    def evaluate_fitness(self, weights):
        """Play game with weights and return lines cleared"""
        game = TetrisGame()
        ai = TetrisAI(weights)
        lines_cleared = 0

        while not game.is_game_over():
            piece = game.get_next_piece()
            move = ai.get_best_move(game, piece)
            game.make_move(move)
            lines_cleared += game.clear_lines()

        return lines_cleared

    def evolve(self, generations=50):
        """Run genetic algorithm"""
        population = [self.create_individual() for _ in range(self.population_size)]

        for gen in range(generations):
            # Evaluate fitness
            fitness_scores = [(ind, self.evaluate_fitness(ind)) for ind in population]
            fitness_scores.sort(key=lambda x: x[1], reverse=True)

            # Select top 50%
            survivors = [ind for ind, _ in fitness_scores[:self.population_size // 2]]

            # Create next generation
            population = survivors.copy()
            while len(population) < self.population_size:
                parent1, parent2 = random.sample(survivors, 2)
                child = self.crossover(parent1, parent2)
                child = self.mutate(child)
                population.append(child)

        return fitness_scores[0][0]  # Return best weights
```

---

## Key Takeaways

1. **Start simple**: Use 4 basic heuristics (height, lines, holes, bumpiness)
2. **Avoid deep lookahead**: Stick to one-piece or no lookahead for speed
3. **Use existing weights**: Start with published weights before optimizing
4. **Python is ideal**: Great balance of simplicity and performance
5. **Genetic algorithms work**: Can find good weights overnight
6. **Pierre Dellacherie is best**: If you want top performance with heuristics

---

## Resources

### Academic Papers
- [Tetris AI PDF](https://chihsienyen.github.io/pdf/Tetris_AI.pdf) - Wei-Tze Tsai's analysis
- [Tetris: A Heuristic Study](http://www.diva-portal.org/smash/get/diva2:815662/FULLTEXT01.pdf)

### Popular Blog Posts
- [Code My Road - Tetris AI](https://codemyroad.wordpress.com/2013/04/14/tetris-ai-the-near-perfect-player/)
- [Lucky's Notes - Genetic Algorithm](https://luckytoilet.wordpress.com/2011/05/27/coding-a-tetris-ai-using-a-genetic-algorithm/)
- [El-Tetris Algorithm](https://imake.ninja/el-tetris-an-improvement-on-pierre-dellacheries-algorithm/)

### GitHub Repositories

**Python (Recommended):**
- [arton0306/TetrisAi](https://github.com/arton0306/TetrisAi) - Simple, < 600 lines
- [yanyongyu/python-tetris](https://github.com/yanyongyu/python-tetris) - With visualization
- [AndrejaNajev/tetris-AI-bot-Python](https://github.com/AndrejaNajev/tetris-AI-bot-Python) - Well documented

**Other Languages:**
- [takado8/Tetris](https://github.com/takado8/Tetris) - C# with genetic algorithm
- [isaaclino/tetris-ai](https://github.com/isaaclino/tetris-ai) - JavaScript
- [tetris-bot-protocol/dellacherie](https://github.com/tetris-bot-protocol/dellacherie) - Dellacherie algorithm

---

## Next Steps

1. Choose an approach (recommend starting with Option 1)
2. Implement or fork a basic Tetris game engine
3. Add heuristic evaluation functions
4. Test with documented weights
5. (Optional) Implement genetic algorithm for optimization
6. Iterate and improve

**Estimated Time:**
- Basic implementation: 4-8 hours
- With genetic algorithm: 8-16 hours
- Dellacherie algorithm: 12-20 hours
