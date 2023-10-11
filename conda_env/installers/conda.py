# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""DEPRECATED: Use `conda.env.installers.conda` instead.

Conda-flavored installer.
"""
from conda.deprecations import deprecated
from conda.env.installers.conda import dry_run, install  # noqa

deprecated.module("24.3", "24.9", addendum="Use `conda.env.installers.conda` instead.")
