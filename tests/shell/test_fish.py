# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from shutil import which

import pytest

from conda.common.compat import on_win

pytestmark = pytest.mark.skipif(on_win, reason="fish is not available on Windows")


@pytest.fixture(scope="module")
def fish() -> str:
    if which("fish"):
        return "fish"

    raise FileNotFoundError("fish not found")


def test_fish_available(fish: str) -> None:
    assert fish
