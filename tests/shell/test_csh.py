# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from shutil import which

import pytest

from conda.common.compat import on_win

pytestmark = pytest.mark.skipif(on_win, reason="csh is not available on Windows")


@pytest.fixture(scope="module")
def csh() -> str:
    if which("csh"):
        return "csh"

    raise FileNotFoundError("csh not found")


def test_csh_available(csh: str) -> None:
    assert csh
