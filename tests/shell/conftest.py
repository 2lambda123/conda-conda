# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from shutil import which
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest import FixtureRequest


@pytest.fixture(scope="module")
def shell(request: FixtureRequest) -> str:
    shells: list[str] = (
        [request.param] if isinstance(request.param, str) else list(request.param)
    )
    for shell in shells:
        if which(shell):
            return shell
    raise FileNotFoundError(f"shell {tuple(shells)} not found")
