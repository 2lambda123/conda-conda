# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

from . import skipif_not_win

pytestmark = skipif_not_win
parametrize_fish = pytest.mark.parametrize("shell", ["fish"], indirect=True)


@parametrize_fish
def test_shell_available(shell: str) -> None:
    # the fixture does all the work
    pass
