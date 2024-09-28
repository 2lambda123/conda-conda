# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

from . import not_mac, not_win


@pytest.parameterize(
    "shell",
    [
        pytest.param("ash", mark=[not_mac, not_win]),
        "bash",
        pytest.param("dash", mark=not_win),
        pytest.param("zsh", mark=not_win),
    ],
    indirect=True,
)
def test_shell_available(shell: str) -> None:
    # the fixture does all the work
    pass
