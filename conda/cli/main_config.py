# (c) 2012-2013 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
from __future__ import print_function, division, absolute_import

import re
import os
import sys
from argparse import RawDescriptionHelpFormatter
from copy import deepcopy

import conda.config as config
from conda.config_file import (write_config, ConfigKeyError, ConfigTypeError, ConfigValueError)
from conda.cli import common

descr = """
Modify configuration values in .condarc.  This is modeled after the git
config command.  Writes to the user .condarc file (%s) by default.

See http://conda.pydata.org/docs/config.html for details on all the options
that can go in .condarc.

List keys, like

  $ cat .condarc
  $ key:
  $   - a
  $   - b

are modified with the --add and --remove options. For example

    conda config --add key c

on the above configuration would prepend the key 'c', giving

    key:
      - c
      - a
      - b

Note that the key 'channels' implicitly contains the key 'defaults' if it is
not configured.

Boolean keys, like

    key: true

are modified with --set and removed with --remove-key. For example

    conda config --set key false

gives

    key: false

Note that in YAML, yes, YES, on, true, True, and TRUE are all valid ways to
spell "true", and no, NO, off, false, False, and FALSE, are all valid ways to
spell "false".

The .condarc file is YAML, and any valid YAML syntax is allowed.  However,
this command uses a specialized YAML parser that tries to maintain structure
and comments, which may not recognize all kinds of syntax. The --force flag
can be used to write using the YAML parser, which will remove any structure
and comments from the file.  Currently, the --force flag is required to use
--remove or --remove-key.

""" % config.user_rc_path

# Note, the formatting of this is designed to work well with help2man
example = """
Examples:

Get the channels defined in the system .condarc:

    conda config --get channels --system

Add the 'foo' Binstar channel:

    conda config --add channels foo

Enable the 'show_channel_urls' option:

    conda config --set show_channel_urls yes
"""

class CouldntParse(NotImplementedError):
    def __init__(self, reason):
        self.args = ["""Could not parse the yaml file. Use -f to use the
yaml parser (this will remove any structure or comments from the existing
.condarc file). Reason: %s""" % reason]

class BoolKey(common.Completer):
    def __contains__(self, other):
        # Other is either one of the keys or the boolean
        try:
            import yaml
        except ImportError:
            yaml = False

        ret = other in config.rc_bool_keys
        if yaml:
            ret = ret or isinstance(yaml.load(other), bool)

        return ret

    def _get_items(self):
        return config.rc_bool_keys + ['yes', 'no', 'on', 'off', 'true', 'false']

class ListKey(common.Completer):
    def _get_items(self):
        return config.rc_list_keys

class BoolOrListKey(common.Completer):
    def __contains__(self, other):
        return other in self.get_items()

    def _get_items(self):
        return config.rc_list_keys + config.rc_bool_keys

def configure_parser(sub_parsers):
    p = sub_parsers.add_parser(
        'config',
        formatter_class = RawDescriptionHelpFormatter,
        description = descr,
        help = descr,
        epilog = example,
        )
    common.add_parser_json(p)

    # TODO: use argparse.FileType
    location = p.add_mutually_exclusive_group()
    location.add_argument(
        "--system",
        action="store_true",
        help="""\
write to the system .condarc file ({system}). Otherwise writes to the user
        config file ({user}).""".format(system=config.sys_rc_path,
                                        user=config.user_rc_path),
        )
    location.add_argument(
        "--file",
        action="store",
        help="""\
write to the given file. Otherwise writes to the user config file ({user}) or
the file path given by the 'CONDARC' environment variable, if it is set.
        (%(default)s)""".format(user=config.user_rc_path),
        default=os.environ.get('CONDARC', config.user_rc_path)
        )

    # XXX: Does this really have to be mutually exclusive. I think the below
    # code will work even if it is a regular group (although combination of
    # --add and --remove with the same keys will not be well-defined).
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--get",
        nargs = '*',
        action = "store",
        help = "get the configuration value",
        default = None,
        metavar = ('KEY'),
        choices=BoolOrListKey()
        )
    action.add_argument(
        "--add",
        nargs = 2,
        action = "append",
        help = """add one configuration value to a list key. The default
        behavior is to prepend.""",
        default = [],
        choices=ListKey(),
        metavar = ('KEY', 'VALUE'),
        )
    action.add_argument(
        "--set",
        nargs = 2,
        action = "append",
        help = "set a boolean key. BOOL_VALUE should be 'yes' or 'no'",
        default = [],
        choices=BoolKey(),
        metavar = ('KEY', 'BOOL_VALUE'),
        )
    action.add_argument(
        "--remove",
        nargs = 2,
        action = "append",
        help = """remove a configuration value from a list key. This removes
    all instances of the value""",
        default = [],
        metavar = ('KEY', 'VALUE'),
        )
    action.add_argument(
        "--remove-key",
        nargs = 1,
        action = "append",
        help = """remove a configuration key (and all its values)""",
        default = [],
        metavar = "KEY",
        )

    p.add_argument(
        "-f", "--force",
        action = "store_true",
        help = """Write to the config file using the yaml parser.  This will
        remove any comments or structure from the file."""
        )

    p.set_defaults(func=execute)


def execute(args, parser):
    try:
        import yaml
        yaml
    except ImportError:
        common.error_and_exit("pyyaml is required to modify configuration",
                              json=args.json, error_type="ImportError")

    if args.system:
        rc_path = config.sys_rc_path
    elif args.file:
        rc_path = args.file
    else:
        rc_path = config.user_rc_path

    try:
        json_result = write_config(rc_path, add=args.add, get=args.get,
            set_=args.set, remove=args.remove, remove_key=args.remove_key, force=args.force)
    except (NotImplementedError, ConfigValueError, ConfigTypeError, ConfigKeyError) as e:
        if args.json:
            common.exception_and_exit(e, json=True)
        else:
            sys.exit("Error: %s" % e.args[0])

    if args.json:
        common.stdout_json_success(
            rc_path=rc_path,
            **json_result
        )
    else:
        for warning in json_result['warnings']:
            print(warning, file=sys.stderr)
        for result in json_result['result']:
            print(result)
