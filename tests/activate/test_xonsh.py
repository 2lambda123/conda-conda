# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from shutil import which


def test_xonsh_available():
    assert which("xonsh")
