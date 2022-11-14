# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from .hookspec import hookimpl
from .types import CondaSolver, CondaSubcommand, CondaVirtualPackage  # noqa: F401

#: Conda plugin hook implementation marker, please use ``conda.plugins.hookimpl``
hookimpl = hookimpl
