# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

from conda.common.compat import on_linux, on_mac, on_win

skipif_not_linux = pytest.mark.skipif(on_linux, reason="not available on Linux")
skipif_not_mac = pytest.mark.skipif(on_mac, reason="not available on macOS")
skipif_not_win = pytest.mark.skipif(on_win, reason="not available on Windows")
