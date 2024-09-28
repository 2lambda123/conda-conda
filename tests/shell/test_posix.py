# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

from . import SKIPIF_ON_MAC, SKIPIF_ON_WIN

parametrize_posix = pytest.mark.parametrize(
    "shell",
    [
        pytest.param("ash", marks=[SKIPIF_ON_MAC, SKIPIF_ON_WIN]),
        "bash",
        pytest.param("dash", marks=SKIPIF_ON_WIN),
        pytest.param("zsh", marks=SKIPIF_ON_WIN),
    ],
    indirect=True,
)


@parametrize_posix
def test_shell_available(shell: str) -> None:
    # the fixture does all the work
    pass
