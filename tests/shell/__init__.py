# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

from conda.common.compat import on_linux, on_mac, on_win

not_linux = pytest.mark.skipif(on_linux, reason="not available on Linux")
not_mac = pytest.mark.skipif(on_mac, reason="not available on macOS")
not_win = pytest.mark.skipif(on_win, reason="not available on Windows")
