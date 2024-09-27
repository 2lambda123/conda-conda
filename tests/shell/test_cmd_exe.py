# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from shutil import which

import pytest

from conda.common.compat import on_linux, on_mac

pytestmark = [
    pytest.mark.skipif(on_linux, reason="cmd.exe is not available on Linux"),
    pytest.mark.skipif(on_mac, reason="cmd.exe is not available on macOS"),
]


@pytest.fixture(scope="module")
def cmd_exe() -> str:
    if which("cmd.exe"):
        return "cmd.exe"

    raise FileNotFoundError("cmd.exe not found")


def test_cmd_exe_available(cmd_exe: str) -> None:
    assert cmd_exe
