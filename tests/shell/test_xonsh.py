# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from shutil import which

import pytest

from conda.common.compat import on_win

pytestmark = pytest.mark.skipif(on_win, reason="xonsh is harder to install on Windows")


@pytest.fixture(scope="module")
def xonsh() -> str:
    if which("xonsh"):
        return "xonsh"

    raise FileNotFoundError("xonsh not found")


def test_xonsh_available(xonsh: str) -> None:
    assert xonsh
