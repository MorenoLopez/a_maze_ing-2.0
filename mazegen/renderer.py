#!/usr/bin/env python3
# ########################################################################### #
#   shebang: 1                                                                #
#                                                          :::      ::::::::  #
#   renderer.py                                          :+:      :+:    :+:  #
#                                                      +:+ +:+         +:+    #
#   By: horarivo <horarivo@student.42antananarivo.   +#+  +:+       +#+       #
#                                                  +#+#+#+#+#+   +#+          #
#   Created: 2026/05/26 18:47:13 by horarivo            #+#    #+#            #
#   Updated: 2026/06/14 08:24:26 by horarivo           ###   ########.fr      #
#                                                                             #
# ########################################################################### #

"""Low-level pixel helpers for MLX buffer and file writing."""

from .config import die
from .generator import MazeGenerator


# ## Helpers ########################


def to_bytes(r: int, g: int, b: int) -> bytes:
    """Convert RGB to 4 little-endian ARGB bytes (MLX buffer format)"""
    return (0xFF000000 | (r << 16) | (g << 8) | b).to_bytes(
        4, "little"
    )


def to_int(r: int, g: int, b: int) -> int:
    """Convert RGB to 0xAARRGGBB integer for mlx_string_put"""
    return 0xFF000000 | (r << 16) | (g << 8) | b


# ## Drawing primitives #########################


def fill_rect(
    data: memoryview,
    sl: int,
    x: int,
    y: int,
    w: int,
    h: int,
    cb: bytes,
) -> None:
    """Fill a rectangle of pixels in the image buffer"""
    row_bytes = cb * w
    for dy in range(h):
        start = (y + dy) * sl + x * 4
        data[start:start + w * 4] = row_bytes


def draw_hline(
    data: memoryview,
    sl: int,
    x: int,
    y: int,
    length: int,
    thick: int,
    cb: bytes,
) -> None:
    """Draw a thick horizontal line in the buffer."""
    fill_rect(data, sl, x, y, length, thick, cb)


def draw_vline(
    data: memoryview,
    sl: int,
    x: int,
    y: int,
    length: int,
    thick: int,
    cb: bytes,
) -> None:
    """Draw a thick horizontal line in the buffer"""
    fill_rect(data, sl, x, y, thick, length, cb)


# ## Fichier de sortie ####################################################─


def write_output(
    gen: MazeGenerator,
    solution: list[str],
    filepath: str,
) -> None:
    """Write the maze to a text file in hexadecimal format."""
    try:
        with open(filepath, "w") as f:
            for row in gen.grid:
                f.write(
                    "".join(format(cell, "X") for cell in row) + "\n"
                )
            f.write("\n")
            ex, ey = gen.entry
            xx, xy = gen.exit_
            f.write(f"{ex},{ey}\n")
            f.write(f"{xx},{xy}\n")
            f.write("".join(solution) + "\n")
        print(f"[OK] File written: {filepath!r}")
    except OSError as exc:
        die(f"Unable to write {filepath!r}: {exc}")
