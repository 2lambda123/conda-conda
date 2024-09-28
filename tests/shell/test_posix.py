# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

from . import skipif_not_mac, skipif_not_win

parametrize_posix = pytest.mark.parametrize(
    "shell",
    [
        pytest.param("ash", marks=[skipif_not_mac, skipif_not_win]),
        "bash",
        pytest.param("dash", marks=skipif_not_win),
        pytest.param("zsh", marks=skipif_not_win),
    ],
    indirect=True,
)


@parametrize_posix
def test_shell_available(shell: str) -> None:
    # the fixture does all the work
    pass
