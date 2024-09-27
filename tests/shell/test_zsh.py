# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from shutil import which

import pytest

from conda.common.compat import on_win

pytestmark = pytest.mark.skipif(on_win, reason="zsh is not available on Windows")


@pytest.fixture(scope="module")
def zsh() -> str:
    if which("zsh"):
        return "zsh"

    raise FileNotFoundError("zsh not found")


def test_zsh_available(zsh: str) -> None:
    assert zsh
