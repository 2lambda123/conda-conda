# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from shutil import which

import pytest

from conda.common.compat import on_win

pytestmark = pytest.mark.skipif(on_win, reason="dash is not available on Windows")


@pytest.fixture(scope="module")
def dash() -> str:
    if which("dash"):
        return "dash"

    raise FileNotFoundError("dash not found")


def test_dash_available(dash: str) -> None:
    assert dash
