# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

from . import skipif_not_win

pytestmark = skipif_not_win
parametrize_csh = pytest.mark.parametrize("shell", ["csh", "tcsh"], indirect=True)


@parametrize_csh
def test_shell_available(shell: str) -> None:
    # the fixture does all the work
    pass
