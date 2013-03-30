# (c) 2012 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
'''conda is a tool for managing Anaconda environments and packages.

conda provides the following commands:

    Information
    ===========

    info       : display information about the current Anaconda install
    list       : list packages activated in a specified Anaconda environment
    depends    : find package dependencies
    search     : print information about a specified package
    help       : display a list of available conda commands and their help strings

    Basic Package Management
    ========================

    create     : create a new Anaconda environment from a list of specified packages. To use this environment, invoke the binaries in that environment's bin directory or adjust your PATH to look in this directory first.
    install    : install new packages into an existing Anaconda environment
    update     : update packages in a specified Anaconda environment

    Advanced Package Management
    ===========================

    env        : activate or deactivate available packages in the specified Anaconda environment
    local      : add and remove Anaconda packages from local availability

    Packaging
    =========

    package    : create a conda package in an environment
    pip        : call pip and create a conda package in an environment
    index      : updates repodata.json in channel directories

Additional help for each command can be accessed by using:

    conda <command> -h
'''
import sys
import argparse

import conda_argparse
import main_build
import main_clone
import main_launch
import main_create
import main_depends
import main_env
import main_help
import main_index
import main_info
import main_install
import main_list
import main_local
import main_remove
import main_package
import main_pip
import main_search
import main_share
import main_update


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('..activate', '..deactivate'):
        import activate
        activate.main()
        return

    import logging
    from .. import __version__

    p = conda_argparse.ArgumentParser(
        description='conda is a tool for managing Anaconda environments and packages.'
    )
    p.add_argument(
        '-v', '--version',
        action='version',
        version='conda %s' % __version__,
    )
    p.add_argument(
        '-l', "--log-level",
        action  = "store",
        default = "warning",
        choices = ['debug', 'info', 'warning', 'error', 'critical'],
        help    = argparse.SUPPRESS,
    )
    sub_parsers = p.add_subparsers(
        metavar = 'command',
        dest    = 'cmd',
    )

    main_info.configure_parser(sub_parsers)
    main_help.configure_parser(sub_parsers)
    main_list.configure_parser(sub_parsers)
    main_depends.configure_parser(sub_parsers)
    main_search.configure_parser(sub_parsers)
    main_create.configure_parser(sub_parsers)
    main_install.configure_parser(sub_parsers)
    main_update.configure_parser(sub_parsers)
    main_env.configure_parser(sub_parsers)
    main_local.configure_parser(sub_parsers)
    main_remove.configure_parser(sub_parsers)
    main_package.configure_parser(sub_parsers)
    main_pip.configure_parser(sub_parsers)
    main_share.configure_parser(sub_parsers)
    main_clone.configure_parser(sub_parsers)
    main_launch.configure_parser(sub_parsers)
    main_build.configure_parser(sub_parsers)
    main_index.configure_parser(sub_parsers)

    args = p.parse_args()

    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(level=log_level)

    try:
        args.func(args, p)
    except RuntimeError as e:
        print "conda: error:", e
        exit(2)
    except Exception as e:
        print "An unexpected exceptional error has occurred, please consider sending the following traceback to the conda GitHub issue tracker at https://github.com/ContinuumIO/conda/issues"
        print
        exc_info = sys.exc_info()
        raise exc_info[1], None, exc_info[2]


if __name__ == '__main__':
    main()
