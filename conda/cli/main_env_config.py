# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda-env config`.

Allows for programmatically interacting with conda-env's configuration files (e.g., `~/.condarc`).
"""
from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)

from .main_env_vars import configure_parser as configure_vars_parser


def configure_parser(sub_parsers: _SubParsersAction) -> ArgumentParser:
    from ..auxlib.ish import dals

    summary = "Configure a conda environment."
    description = summary
    epilog = dals(
        """
        Examples::

            conda env config vars list
            conda env config --append channels conda-forge

        """
    )

    p = sub_parsers.add_parser(
        "config",
        help=summary,
        description=description,
        epilog=epilog,
    )
    p.set_defaults(func="conda.cli.main_env_config.execute")
    config_subparser = p.add_subparsers()
    configure_vars_parser(config_subparser)

    return p


def execute(args: Namespace, parser: ArgumentParser) -> int:
    parser.parse_args(["config", "--help"])

    return 0
