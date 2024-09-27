# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from shutil import which

import pytest


@pytest.fixture(scope="module")
def bash() -> str:
    if which("bash"):
        return "bash"

    raise FileNotFoundError("bash not found")


def test_bash_available(bash: str) -> None:
    assert bash
