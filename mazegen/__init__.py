#!/usr/bin/env python3
# ########################################################################### #
#   shebang: 1                                                                #
#                                                          :::      ::::::::  #
#   __init__.py                                          :+:      :+:    :+:  #
#                                                      +:+ +:+         +:+    #
#   By: codespace <codespace@student.42.fr>          +#+  +:+       +#+       #
#                                                  +#+#+#+#+#+   +#+          #
#   Created: 2026/05/28 00:00:00 by horarivo            #+#    #+#            #
#   Updated: 2026/07/11 07:15:32 by codespace          ###   ########.fr      #
#                                                                             #
# ########################################################################### #


"""maze - public API of the maze generation package.

This file marks the ``maze/`` directory as a Python package and defines
the public API: the names listed in ``__all__`` are the only ones that
outside code should import. Internal modules (renderer, app, constants)
are implementation details and are not re-exported here.
"""

from .config import Config, die
from .generator import MazeGenerator
from .solver import MazeSolver

__all__ = [
    "Config",
    "die",
    "MazeGenerator",
    "MazeSolver",
]
