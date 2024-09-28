# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

from . import not_linux, not_mac

pytestmark = [not_linux, not_mac]


@pytest.parameterize("shell", ["cmd.exe"], indirect=True)
def test_shell_available(shell: str) -> None:
    # the fixture does all the work
    pass
