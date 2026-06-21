# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    Makefile                                           :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: horarivo <horarivo@student.42antananari    +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2026/05/26 18:15:51 by horarivo          #+#    #+#              #
#    Updated: 2026/06/12 11:56:19 by horarivo         ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

# ## Variables #############################################
PYTHON  = python3
MAIN    = a_maze_ing.py
CONFIG  = config.txt

# mypy flags (non-strict lint
MYPY_FLAGS = \
	--warn-return-any \
	--warn-unused-ignores \
	--ignore-missing-imports \
	--disallow-untyped-defs \
	--check-untyped-defs

# ## Phony targets (not files) ###############################
.PHONY: install run debug clean lint lint-strict

# ## install #################################################
install:
	$(PYTHON) -m pip install -r requirements.txt

# ## run #####################################################
run:
	$(PYTHON) $(MAIN) $(CONFIG)

# ## debug ###################################################
debug:
	$(PYTHON) -m pdb $(MAIN) $(CONFIG)

# ## clean ###################################################
clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} \;
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} \;
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	@echo "Cleanup complete."

# ## lint ####################################################
lint:
	flake8 . && mypy . $(MYPY_FLAGS)

# ## lint-strict #############################################
lint-strict:
	flake8 . && mypy . --strict
