# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

parametrize_powershell = pytest.mark.parametrize(
    "shell", [("powershell", "pwsh", "pwsh-preview")], indirect=True
)


@parametrize_powershell
def test_shell_available(shell: str) -> None:
    # the fixture does all the work
    pass
