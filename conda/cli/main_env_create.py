# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda-env create`.

Creates new conda environments with the specified packages.
"""
import json
import os
import sys
import textwrap
from argparse import (
    ArgumentParser,
    Namespace,
    RawDescriptionHelpFormatter,
    _StoreTrueAction,
    _SubParsersAction,
)

from conda.base.context import context, determine_target_prefix
from conda.core.prefix_data import PrefixData
from conda.deprecations import deprecated
from conda.env import (
    specs,
)
from conda.env.installers.base import InvalidInstaller, get_installer
from conda.gateways.disk.delete import rm_rf
from conda.misc import touch_nonadmin
from conda.notices import notices

from . import install as cli_install
from .common import get_filename, print_result


def configure_parser(sub_parsers: _SubParsersAction) -> ArgumentParser:
    from ..auxlib.ish import dals
    from .helpers import (
        add_output_and_prompt_options,
        add_parser_default_packages,
        add_parser_networking,
        add_parser_prefix,
        add_parser_solver,
    )

    summary = "Create an environment based on an environment definition file."
    description = dals(
        f"""
        {summary}

        If using an environment.yml file (the default), you can name the
        environment in the first line of the file with 'name: envname' or
        you can specify the environment name in the CLI command using the
        -n/--name argument. The name specified in the CLI will override
        the name specified in the environment.yml file.

        Unless you are in the directory containing the environment definition
        file, use -f to specify the file path of the environment definition
        file you want to use.

        """
    )
    epilog = dals(
        """
        Examples::

            conda env create
            conda env create -n envname
            conda env create folder/envname
            conda env create -f /path/to/environment.yml
            conda env create -f /path/to/requirements.txt -n envname
            conda env create -f /path/to/requirements.txt -p /home/user/envname

        """
    )

    p = sub_parsers.add_parser(
        "create",
        formatter_class=RawDescriptionHelpFormatter,
        help=summary,
        description=description,
        epilog=epilog,
    )
    p.add_argument(
        "-f",
        "--file",
        action="store",
        help="Environment definition file (default: environment.yml)",
        default="environment.yml",
    )

    # Add name and prefix args
    add_parser_prefix(p)

    # Add networking args
    add_parser_networking(p)

    p.add_argument(
        "remote_definition",
        help="Remote environment definition / IPython notebook",
        action="store",
        default=None,
        nargs="?",
    )
    p.add_argument(
        "--force",
        dest="yes",
        action=deprecated.action(
            "23.9",
            "24.3",
            _StoreTrueAction,
            addendum="Use `--yes` instead.",
        ),
        default=False,
    )
    add_parser_default_packages(p)
    add_output_and_prompt_options(p)
    add_parser_solver(p)

    p.set_defaults(func="conda.cli.main_env_create.execute")

    return p


@notices
def execute(args: Namespace, parser: ArgumentParser) -> int:
    spec = specs.detect(
        name=args.name,
        filename=get_filename(args.file),
        directory=os.getcwd(),
        remote_definition=args.remote_definition,
    )
    env = spec.environment

    # FIXME conda code currently requires args to have a name or prefix
    # don't overwrite name if it's given. gh-254
    if args.prefix is None and args.name is None:
        args.name = env.name

    prefix = determine_target_prefix(context, args)

    if args.yes and prefix != context.root_prefix and os.path.exists(prefix):
        rm_rf(prefix)
    cli_install.check_prefix(prefix, json=args.json)

    # TODO, add capability
    # common.ensure_override_channels_requires_channel(args)
    # channel_urls = args.channel or ()

    result = {"conda": None, "pip": None}

    args_packages = (
        context.create_default_packages if not args.no_default_packages else []
    )

    if args.dry_run:
        installer_type = "conda"
        installer = get_installer(installer_type)

        pkg_specs = env.dependencies.get(installer_type, [])
        pkg_specs.extend(args_packages)

        solved_env = installer.dry_run(pkg_specs, args, env)
        if args.json:
            print(json.dumps(solved_env.to_dict(), indent=2))
        else:
            print(solved_env.to_yaml(), end="")

    else:
        if args_packages:
            installer_type = "conda"
            installer = get_installer(installer_type)
            result[installer_type] = installer.install(prefix, args_packages, args, env)

        if len(env.dependencies.items()) == 0:
            installer_type = "conda"
            pkg_specs = []
            installer = get_installer(installer_type)
            result[installer_type] = installer.install(prefix, pkg_specs, args, env)
        else:
            for installer_type, pkg_specs in env.dependencies.items():
                try:
                    installer = get_installer(installer_type)
                    result[installer_type] = installer.install(
                        prefix, pkg_specs, args, env
                    )
                except InvalidInstaller:
                    sys.stderr.write(
                        textwrap.dedent(
                            """
                        Unable to install package for {0}.

                        Please double check and ensure your dependencies file has
                        the correct spelling.  You might also try installing the
                        conda-env-{0} package to see if provides the required
                        installer.
                        """
                        )
                        .lstrip()
                        .format(installer_type)
                    )
                    return -1

        if env.variables:
            pd = PrefixData(prefix)
            pd.set_environment_env_vars(env.variables)

        touch_nonadmin(prefix)
        print_result(args, prefix, result)

    return 0
