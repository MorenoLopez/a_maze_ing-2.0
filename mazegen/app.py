#!/usr/bin/env python3
# ########################################################################### #
#   shebang: 1                                                                #
#                                                          :::      ::::::::  #
#   app.py                                               :+:      :+:    :+:  #
#                                                      +:+ +:+         +:+    #
#   By: horarivo <horarivo@student.42antananarivo.   +#+  +:+       +#+       #
#                                                  +#+#+#+#+#+   +#+          #
#   Created: 2026/05/25 18:52:47 by horarivo            #+#    #+#            #
#   Updated: 2026/06/14 08:24:46 by horarivo           ###   ########.fr      #
#                                                                             #
# ########################################################################### #


"""AppState: MLX window, render buffer and event management."""

import math
from typing import Any, Optional

from .config import Config, die
from .constants import (
    EAST,
    KEY_C,
    KEY_ESCAPE,
    KEY_P,
    KEY_Q,
    KEY_SPACE,
    NORTH,
    PALETTES,
    SOUTH,
    WEST,
)
from .generator import MazeGenerator
from .renderer import (
    draw_hline,
    draw_vline,
    fill_rect,
    to_bytes,
    to_int,
    write_output,
)
from .solver import MazeSolver

# Number of stack cells included in the light trail behind the DFS head.
# The most recent cell has intensity 1.0, the oldest has ~(1/TRAIL_LEN).
TRAIL_LEN: int = 80

# Warm tint colour applied at maximum stack depth (deep exploration).
# Blended toward this as the stack grows; fades back when backtracking.
_WARM: tuple[int, int, int] = (255, 0, 0)

# Path animation: number of path cells revealed per loop tick.
# Higher = the tracing line draws faster from entry to exit.
PATH_SPEED: int = 2


class AppState:
    """Manages the MLX window, pixel rendering and keyboard events.

    Rendering strategy:
        1. The entire scene is drawn into an MLX image buffer.
        2. ``mlx_put_image_to_window`` displays the buffer in one operation.
        3. ``mlx_string_put`` draws text on top (info bar).

    Generation animations (active while gen.done is False):
        - **Light trail**: the last TRAIL_LEN cells on the DFS stack glow
          and fade progressively — a "glowworm" digging through the maze.
        - **Pulse**: the head cell oscillates between its colour and white
          using a smooth sine wave, drawing the eye to the active point.
        - **Depth tint**: the trail shifts toward a warm orange when the
          stack is deep (exploring), and cools back when backtracking.

    Path animation (triggered by pressing P once generation is done):
        - **Tracing line**: a thin line is drawn through the centre of
          each solution-path cell, segment by segment, progressing from
          entry to exit at PATH_SPEED cells per loop tick — like a pen
          drawing the route on a map.
        - **Pen tip**: a bright glowing square marks the leading end of
          the line as it is drawn, and remains on the exit once the
          tracing is complete.
        - **Avatar follow**: the sprite icon follows the pen tip while
          the line is being traced, and rests on the exit afterwards.
        Pressing P again hides the line and resets the animation, so it
        retraces from the start the next time it is shown.

    Keyboard controls:
        - SPACE   : regenerate a new maze
        - P       : toggle shortest-path tracing animation
        - C       : cycle through colour palettes
        - Q / ESC : quit
    """

    INFO_H: int = 80  # info bar height in pixels
    MAX_CELL: int = 36  # maximum cell size in pixels
    MIN_CELL: int = 6  # minimum cell size in pixels

    def __init__(self, cfg: Config, mlx: Any) -> None:
        """Initialize MLX, create window and image buffer.

        Args:
            cfg: Validated maze configuration.
            mlx: Instance of the Mlx class.
        """
        self.cfg = cfg
        self.mlx: Any = mlx

        self.mlx_ptr: Any = mlx.mlx_init()
        if not self.mlx_ptr:
            die("Failed to initialize MLX.")

        # ## Compute pixel dimensions ##################################
        _, screen_w, screen_h = mlx.mlx_get_screen_size(self.mlx_ptr)

        self.cs: int = max(
            self.MIN_CELL,
            min(
                int(screen_w * 0.9) // cfg.width,
                (int(screen_h * 0.9) - self.INFO_H) // cfg.height,
            ),
        )
        self.maze_px_w: int = cfg.width * self.cs
        self.maze_px_h: int = cfg.height * self.cs
        self.win_w: int = self.maze_px_w
        self.win_h: int = self.maze_px_h + self.INFO_H
        self.wall_w: int = max(1, self.cs // 9)

        # ## Create window ############################################
        self.win_ptr: Any = mlx.mlx_new_window(
            self.mlx_ptr, self.win_w, self.win_h, "A-Maze-ing"
        )
        if not self.win_ptr:
            die("Unable to create MLX window.")

        # ## Create full-window image buffer ##########################
        self.img_ptr: Any = mlx.mlx_new_image(self.mlx_ptr,
                                              self.win_w,
                                              self.win_h
                                              )
        if not self.img_ptr:
            die("Unable to create MLX image.")
        self.data: Any
        self.sl: int
        self.data, _bpp, self.sl, _fmt = mlx.mlx_get_data_addr(self.img_ptr)

        # ## Application state ########################################
        self.pal_idx: int = 0
        self.show_path: bool = False
        self.solver: Optional[MazeSolver] = None
        self.needs_redraw: bool = True
        # Frame counter — incremented every loop tick, drives animations.
        self.frame: int = 0
        # Path tracing progress — number of path cells revealed so far.
        # Reset to 0 whenever the path animation is (re)started.
        self.path_frame: int = 0

        self.gen: MazeGenerator = self._make_gen(cfg.seed)
        self.spf: int = 6
        # self.spf: int = max(4, (cfg.width * cfg.height) // 80)

        # ## Icon ####################################################
        # ## DYNAMIC SPRITE SYSTEM ####################################─
        # 1. Load the XPM image
        orig_res = mlx.mlx_xpm_file_to_image(self.mlx_ptr, "flash.xpm")

        if orig_res and orig_res[0]:
            orig_ptr, orig_w, orig_h = orig_res
            orig_data, _, orig_sl, _ = mlx.mlx_get_data_addr(orig_ptr)

            # 2. Create an empty image at the size of one cell
            self.icon_ptr = mlx.mlx_new_image(self.mlx_ptr, self.cs, self.cs)
            icon_data, _, icon_sl, _ = mlx.mlx_get_data_addr(self.icon_ptr)

            # 3. Resampling algorithm (nearest-neighbour)
            for y in range(self.cs):
                for x in range(self.cs):
                    src_x = int(x * orig_w / self.cs)
                    src_y = int(y * orig_h / self.cs)

                    src_offset = src_y * orig_sl + src_x * 4
                    dest_offset = y * icon_sl + x * 4

                    # Copy the pixel (XPM also returns BGRA/RGBA
                    # data in the pixel buffer)
                    icon_data[dest_offset: dest_offset + 4] = orig_data[
                        src_offset: src_offset + 4
                        ]

            # 4. Free the source image memory
            mlx.mlx_destroy_image(self.mlx_ptr, orig_ptr)
        else:
            self.icon_ptr = None

    # ## Generator management ##############################################

    def _make_gen(self, seed: Optional[int] = None) -> MazeGenerator:
        """Create a new generator and reset all render state.

        Args:
            seed: Seed to use (None = pick randomly).

        Returns:
            A freshly initialised MazeGenerator.
        """
        self.show_path = False
        self.solver = None
        self.needs_redraw = True
        self.frame = 0
        self.path_frame = 0
        return MazeGenerator(
            self.cfg.width,
            self.cfg.height,
            self.cfg.entry,
            self.cfg.exit_,
            seed=seed,
            perfect=self.cfg.perfect,
        )

    def _get_solver(self) -> MazeSolver:
        """Return the cached MazeSolver, creating it if necessary.

        Returns:
            A MazeSolver attached to the current generator.
        """
        if self.solver is None:
            self.solver = MazeSolver(self.gen)
        return self.solver

    # ## Animation helpers ################################################

    @staticmethod
    def _blend_rgb(
        c1: tuple[int, int, int],
        c2: tuple[int, int, int],
        t: float,
    ) -> tuple[int, int, int]:
        """Linearly interpolate between two RGB colours.

        Args:
            c1: Start colour at t=0.
            c2: End colour at t=1.
            t:  Blend factor, clamped to [0.0, 1.0].

        Returns:
            Interpolated RGB tuple.
        """
        t = max(0.0, min(1.0, t))
        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )

    # ## Rendering ########################################################

    def _redraw(self) -> None:
        """Draw the entire scene into the buffer, then call put_image."""
        pal = PALETTES[self.pal_idx]
        gen = self.gen
        cs = self.cs
        ww = self.wall_w
        sl = self.sl
        data = self.data

        # Pre-compute static colour bytes (used for most cells)
        cb_bg = to_bytes(*pal["bg"])
        cb_wall = to_bytes(*pal["wall"])
        cb_visited = to_bytes(*pal["visited"])
        cb_entry = to_bytes(*pal["entry"])
        cb_exit = to_bytes(*pal["exit"])
        cb_pattern = to_bytes(*pal["pattern"])
        cb_info_bg = to_bytes(*pal["info_bg"])

        fill_rect(data, sl, 0, 0, self.win_w, self.win_h, cb_bg)
        fill_rect(
            data,
            sl,
            0,
            self.maze_px_h,
            self.win_w,
            self.INFO_H,
            cb_info_bg,
        )
        draw_hline(data, sl, 0, self.maze_px_h, self.win_w, 1, cb_wall)

        # ## Animation state (only computed during generation) ########─
        #
        # trail_map  : {pos: float}  intensity 0<t≤1 per trail cell
        #              (1.0 = most recent = brightest, near the head)
        # depth_t    : float 0..1   normalised stack depth
        #              (0 = shallow / backtracking, 1 = deepest explored)
        # pulse      : float 0.65..1.0  smooth oscillation for the head

        trail_map: dict[tuple[int, int], float] = {}
        depth_t: float = 0.0
        pulse: float = 1.0

        if not gen.done and gen._stack:
            # Build trail from the tail of the stack (most recent last)
            trail_slice = gen._stack[-TRAIL_LEN:]
            n = len(trail_slice)
            for i, cell in enumerate(trail_slice):
                trail_map[cell] = (i + 1) / n  # oldest ≈ 1/n, head = 1.0

            # Depth: compare to half the total cells as a comfortable max
            half = max(1, (gen.width * gen.height) // 2)
            depth_t = min(1.0, len(gen._stack) / half)

            # Pulse: sine wave in [0.65, 1.0], period ≈ 35 frames
            pulse = 0.65 + 0.35 * math.sin(self.frame * 0.18)

        # ## Path tracing animation state (only once generation is done) ─
        #
        # plist      : ordered list of (x, y) cells from entry to exit
        # n_shown    : number of cells reached so far by the tracing pen
        # path_head  : the "pen tip" — most recently revealed cell, drawn
        #              with an extra glow. Stays on the exit once the
        #              line has fully been traced.
        #
        # The line itself is drawn in a separate pass below (after the
        # cell grid), so it overlays cell fills and walls cleanly.

        plist: list[tuple[int, int]] = []
        n_shown: int = 0
        path_head: Optional[tuple[int, int]] = None

        if gen.done and self.show_path:
            plist = self._get_solver().path_list()
            n_shown = min(len(plist), self.path_frame)
            if n_shown > 0:
                path_head = plist[n_shown - 1]

        # ## Cell drawing loop ########################################─
        for row in range(gen.height):
            for col in range(gen.width):
                px = col * cs
                py = row * cs
                pos = (col, row)

                # ## Choose fill colour ################################
                if gen.is_42[row][col]:
                    # '42' pattern: always fully walled, dedicated colour
                    cb_fill = cb_pattern

                elif pos == gen.current:
                    # DFS head: pulse between its colour and white
                    # pulse=1.0 → fully white tint, pulse=0.65 → base
                    pulsed = self._blend_rgb(
                        pal["current"], (255, 255, 255), pulse * 0.75
                    )
                    cb_fill = to_bytes(*pulsed)

                elif pos in trail_map:
                    # Light trail: visited colour → current colour
                    # based on recency (t), then warm-tinted by depth
                    t = trail_map[pos]
                    trail_col = self._blend_rgb(
                        pal["visited"], pal["current"], t * 0.4
                    )
                    # Depth tint: shift toward warm orange when exploring deep
                    trail_col = self._blend_rgb(trail_col,
                                                _WARM,
                                                depth_t * t * 0.85
                                                )
                    cb_fill = to_bytes(*trail_col)

                elif pos == gen.entry:
                    cb_fill = cb_entry

                elif pos == gen.exit_:
                    cb_fill = cb_exit

                elif gen.visited[row][col]:
                    cb_fill = cb_visited

                else:
                    cb_fill = cb_bg

                fill_rect(data, sl, px, py, cs, cs, cb_fill)

                # ## Draw closed walls ################################─
                walls = gen.grid[row][col]
                if walls & NORTH:
                    draw_hline(data, sl, px, py, cs, ww, cb_wall)
                if walls & EAST:
                    draw_vline(data, sl, px + cs - ww, py, cs, ww, cb_wall)
                if walls & SOUTH:
                    draw_hline(data, sl, px, py + cs - ww, cs, ww, cb_wall)
                if walls & WEST:
                    draw_vline(data, sl, px, py, cs, ww, cb_wall)

        # ## Path tracing line (drawn on top of cells and walls) ########
        #
        # The line runs through the centre of each revealed path cell.
        # Consecutive cells differ by exactly one step (N/E/S/W), so each
        # segment is a straight horizontal or vertical stroke spanning
        # from one cell centre to the next — crossing the open wall gap
        # between them.
        if n_shown > 0:
            line_w = max(2, cs // 4)
            cb_line = to_bytes(*pal["path"])

            for i in range(n_shown - 1):
                (cx1, cy1) = plist[i]
                (cx2, cy2) = plist[i + 1]

                # Pixel coordinates of both cell centres
                px1 = cx1 * cs + cs // 2
                py1 = cy1 * cs + cs // 2
                px2 = cx2 * cs + cs // 2
                py2 = cy2 * cs + cs // 2

                if cy1 == cy2:
                    # Horizontal segment: centres are cs apart on X
                    x0 = min(px1, px2)
                    draw_hline(
                        data, sl, x0, py1 - line_w // 2, cs, line_w, cb_line
                    )
                else:
                    # Vertical segment: centres are cs apart on Y
                    y0 = min(py1, py2)
                    draw_vline(
                        data, sl, px1 - line_w // 2, y0, cs, line_w, cb_line
                    )

            # Glowing pen tip at the head cell's centre — bigger and
            # brighter than the line itself, marks the tracing front.
            if path_head is not None:
                hx, hy = path_head
                tip_w = max(line_w + 4, cs // 2)
                tip_x = hx * cs + cs // 2 - tip_w // 2
                tip_y = hy * cs + cs // 2 - tip_w // 2
                glow = self._blend_rgb(pal["path"], (255, 255, 255), 0.8)
                fill_rect(data,
                          sl,
                          tip_x,
                          tip_y,
                          tip_w,
                          tip_w,
                          to_bytes(*glow)
                          )

        self.mlx.mlx_put_image_to_window(self.mlx_ptr,
                                         self.win_ptr,
                                         self.img_ptr,
                                         0,
                                         0
                                         )

        if not gen.done and self.icon_ptr and gen.current:
            head_x = gen.current[0] * cs
            head_y = gen.current[1] * cs

            self.mlx.mlx_put_image_to_window(
                self.mlx_ptr, self.win_ptr, self.icon_ptr, head_x, head_y
            )

        # While the path is being traced, the avatar follows the pen tip;
        # otherwise it falls back to the DFS head (during generation) or
        # rests on the exit (idle, once generation is done).
        if gen.done and self.show_path and path_head is not None:
            avatar_pos = path_head
        else:
            avatar_pos = gen.current if gen.current else gen.exit_

        if self.icon_ptr and avatar_pos:
            head_x = avatar_pos[0] * cs
            head_y = avatar_pos[1] * cs

            self.mlx.mlx_put_image_to_window(
                self.mlx_ptr, self.win_ptr, self.icon_ptr, head_x, head_y
            )

        # ## Info bar text ############################################─
        wc = to_int(*pal["wall"])
        hc = to_int(*pal["hint"])
        ty = self.maze_px_h + 10

        if gen.done:
            path_len = len(self._get_solver().solve())
            if self.show_path:
                traced = min(self.path_frame, len(plist))
                status = (
                    f"Finished  seed={gen.seed}         "
                    f"path={path_len} steps  "
                    f"tracing {traced}/{len(plist)}"
                )
            else:
                status = (
                    f"Finished  seed={gen.seed}         "
                    f"path={path_len} steps"
                )
        else:
            done_cells = sum(
                gen.visited[r][c]
                for r in range(gen.height)
                for c in range(gen.width)
            )
            pct = done_cells * 100 // (gen.width * gen.height)
            status = f"Generating {pct}%     seed={gen.seed}"

        self.mlx.mlx_string_put(self.mlx_ptr, self.win_ptr, 8, ty, wc, status)
        self.mlx.mlx_string_put(
            self.mlx_ptr,
            self.win_ptr,
            8,
            ty + 22,
            hc,
            "SPACE=regen      P=path      C=color      Q=quit",
        )

    # ## MLX Callbacks ####################################################

    def on_key(self, keycode: int, _param: object) -> None:
        """Keyboard event handler.

        Args:
            keycode: X11 code of the pressed key.
            _param:  Parameter passed to the hook (ignored).
        """
        if keycode in (KEY_Q, KEY_ESCAPE):
            self.mlx.mlx_loop_exit(self.mlx_ptr)
        elif keycode == KEY_SPACE:
            self.gen = self._make_gen()
        elif keycode == KEY_P:
            if self.gen.done:
                self.show_path = not self.show_path
                # Restart the tracing animation from the entry every
                # time the path is (re)displayed.
                self.path_frame = 0
                self.needs_redraw = True
        elif keycode == KEY_C:
            self.pal_idx = (self.pal_idx + 1) % len(PALETTES)
            self.needs_redraw = True

    def on_loop(self, _param: object) -> None:
        """Called on every MLX loop iteration.

        While generating: advances the backtracker by self.spf steps and
        increments the animation frame counter (pulse and trail).

        Once generation is done and the path is shown: advances the path
        tracing animation by PATH_SPEED cells per tick until the line
        reaches the exit.

        Args:
            _param: Parameter passed to the hook (ignored).
        """
        if not self.gen.done:
            self.gen.step(self.spf)
            self.frame += 1  # drives pulse and trail animation
            self.needs_redraw = True
            if self.gen.done:
                solver = self._get_solver()
                write_output(
                    self.gen,
                    solver.solve(),
                    self.cfg.output_file,
                )
        elif self.show_path:
            # Advance the tracing line until it reaches the exit cell
            plist = self._get_solver().path_list()
            if self.path_frame < len(plist):
                self.path_frame += PATH_SPEED
                self.needs_redraw = True

        if self.needs_redraw:
            self._redraw()
            self.needs_redraw = False

    def on_expose(self, _param: object) -> None:
        """Redraw when the window is re-exposed (uncovered).

        Args:
            _param: Parameter passed to the hook (ignored).
        """
        self.needs_redraw = True

    def on_close(self, _param: object) -> None:
        """Handle the window close button (WM_DELETE_WINDOW).

        Args:
            _param: Parameter passed to the hook (ignored).
        """
        self.mlx.mlx_loop_exit(self.mlx_ptr)

    # ## Main loop ########################################################

    def run(self) -> None:
        """Register MLX hooks and enter the main event loop."""
        self.mlx.mlx_key_hook(self.win_ptr, self.on_key, None)
        self.mlx.mlx_loop_hook(self.mlx_ptr, self.on_loop, None)
        self.mlx.mlx_expose_hook(self.win_ptr, self.on_expose, None)
        self.mlx.mlx_hook(self.win_ptr, 33, 0, self.on_close, None)

        self.mlx.mlx_loop(self.mlx_ptr)

        self.mlx.mlx_destroy_image(self.mlx_ptr, self.img_ptr)
        self.mlx.mlx_destroy_window(self.mlx_ptr, self.win_ptr)
        self.mlx.mlx_release(self.mlx_ptr)
