# SPDX-FileCopyrightText: © 2012 Continuum Analytics, Inc. <http://continuum.io>
# SPDX-FileCopyrightText: © 2017 Anaconda, Inc. <https://www.anaconda.com>
# SPDX-License-Identifier: BSD-3-Clause
import sys

from .install import install
from ..base.context import context
from ..notices import notices


@notices
def execute(args, parser):
    if context.force:
        print("\n\n"
              "WARNING: The --force flag will be removed in a future conda release.\n"
              "         See 'conda update --help' for details about the --force-reinstall\n"
              "         and --clobber flags.\n"
              "\n", file=sys.stderr)

    install(args, parser, 'update')
