# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

from . import skipif_not_linux, skipif_not_mac

pytestmark = [skipif_not_linux, skipif_not_mac]
parametrize_cmd_exe = pytest.mark.parametrize("shell", ["cmd.exe"], indirect=True)


@parametrize_cmd_exe
def test_shell_available(shell: str) -> None:
    # the fixture does all the work
    pass
