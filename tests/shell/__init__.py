# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

from conda.common.compat import on_linux, on_mac, on_win

SKIPIF_ON_LINUX = pytest.mark.skipif(on_linux, reason="not available on Linux")
SKIPIF_ON_MAC = pytest.mark.skipif(on_mac, reason="not available on macOS")
SKIPIF_ON_WIN = pytest.mark.skipif(on_win, reason="not available on Windows")

# Here, by removing --dev you can try weird situations that you may want to test, upgrade paths
# and the like? What will happen is that the conda being run and the shell scripts it's being run
# against will be essentially random and will vary over the course of activating and deactivating
# environments. You will have absolutely no idea what's going on as you change code or scripts and
# encounter some different code that ends up being run (some of the time). You will go slowly mad.
# No, you are best off keeping --dev on the end of these. For sure, if conda bundled its own tests
# module then we could remove --dev if we detect we are being run in that way.
DEV_ARG = "--dev"
ACTIVATE_ARGS = f" activate {DEV_ARG} "
DEACTIVATE_ARGS = f" deactivate {DEV_ARG} "
INSTALL_ARGS = f" install {DEV_ARG} "

# hdf5 version to use in tests
HDF5_VERSION = "1.12.1"
