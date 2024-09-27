# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from shutil import which

import pytest

from conda.common.compat import on_win


@pytest.fixture(scope="module")
def powershell() -> str:
    if on_win and which("powershell"):
        return "powershell"

    if which("pwsh"):
        return "pwsh"

    if which("pwsh-preview"):
        return "pwsh-preview"

    raise FileNotFoundError("powershell not found")


def test_powershell_available(powershell: str) -> None:
    assert powershell
