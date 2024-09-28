# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

from . import SKIPIF_ON_WIN

pytestmark = SKIPIF_ON_WIN
parametrize_xonsh = pytest.mark.parametrize("shell", ["xonsh"], indirect=True)


@parametrize_xonsh
def test_shell_available(shell: str) -> None:
    # the fixture does all the work
    pass
