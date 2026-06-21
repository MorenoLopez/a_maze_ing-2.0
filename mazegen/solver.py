#!/usr/bin/env python3
# ########################################################################### #
#   shebang: 1                                                                #
#                                                          :::      ::::::::  #
#   solver.py                                            :+:      :+:    :+:  #
#                                                      +:+ +:+         +:+    #
#   By: horarivo <horarivo@student.42antananarivo.   +#+  +:+       +#+       #
#                                                  +#+#+#+#+#+   +#+          #
#   Created: 2026/05/02 18:47:42 by orarivo             #+#    #+#            #
#   Updated: 2026/06/14 08:24:46 by horarivo           ###   ########.fr      #
#                                                                             #
# ########################################################################### #

"""BFS solver: shortest path + discovery order for path animations."""

from collections import deque
from typing import Optional

from .constants import DELTA, DIR_NAME
from .generator import MazeGenerator

# Direction delta used to reconstruct path_list from solve() output.
_DELTA_MAP: dict[str, tuple[int, int]] = {
    "N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0),
}


class MazeSolver:
    """Breadth-first search solver for a MazeGenerator grid.

    BFS guarantees the shortest path in an unweighted graph, which is
    exactly what a maze is: each passage between two cells costs 1 step.

    Results are cached after the first call to solve().

    Two extra sequences are stored during solve() to support animations:
        - ``bfs_order()``: cells in the order BFS discovered them.
          Used for the wave-propagation animation (replay the BFS visually).
        - ``path_list()``: the solution path as an ordered list from entry
          to exit.  Used for the flowing-gradient animation.

    Example usage::

        gen = MazeGenerator(20, 15, (0, 0), (19, 14), seed=42)
        gen.generate_all()"""

    def __init__(self, gen: MazeGenerator) -> None:
        """Attach the solver to a MazeGenerator"""
        
        self._gen = gen
        # Cached solution path (None = not yet computed)
        self._path: Optional[list[str]] = None
        # BFS cell discovery order (populated during solve())
        self._bfs_order: list[tuple[int, int]] = []

    # ## Core solve ###############################

    def solve(self) -> list[str]:
        """Find the shortest path from entry to exit using BFS"""

        if self._path is not None:
            return self._path

        gen = self._gen
        ex, ey = gen.exit_

        # Entry cell is the first discovered cell
        self._bfs_order = [gen.entry]

        queue: deque[tuple[tuple[int, int], list[str]]] = deque(
            [(gen.entry, [])]
        )
        seen: set[tuple[int, int]] = {gen.entry}

        while queue:
            (cx, cy), path = queue.popleft()
            if (cx, cy) == (ex, ey):
                self._path = path
                return path

            for direction, (dx, dy) in DELTA.items():
                nx, ny = cx + dx, cy + dy
                in_bounds = (
                    0 <= nx < gen.width
                    and 0 <= ny < gen.height
                )
                wall_open = not (gen.grid[cy][cx] & direction)
                if in_bounds and (nx, ny) not in seen and wall_open:
                    seen.add((nx, ny))
                    # Record discovery order for wave animation
                    self._bfs_order.append((nx, ny))
                    queue.append(
                        ((nx, ny), path + [DIR_NAME[direction]])
                    )

        self._path = []
        return self._path

    # ## Derived sequences #########################

    def path_cells(self) -> set[tuple[int, int]]:
        """Return every (x, y) cell on the solution path as a set"""

        cells: set[tuple[int, int]] = {self._gen.entry}
        x, y = self._gen.entry
        for d in self.solve():
            dx, dy = _DELTA_MAP[d]
            x, y = x + dx, y + dy
            cells.add((x, y))
        return cells

    def path_list(self) -> list[tuple[int, int]]:
        """Return the solution path as an ordered list (entry → exit)"""

        result: list[tuple[int, int]] = [self._gen.entry]
        x, y = self._gen.entry
        for d in self.solve():
            dx, dy = _DELTA_MAP[d]
            x, y = x + dx, y + dy
            result.append((x, y))
        return result

    def bfs_order(self) -> list[tuple[int, int]]:
        """Return cells in BFS discovery order (entry explored first)"""

        self.solve()  # ensure _bfs_order is populated
        return self._bfs_order
