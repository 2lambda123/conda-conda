# (c) 2012 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from argparse import RawDescriptionHelpFormatter

from conda.anaconda import Anaconda
from conda.planners import create_update_plan
from utils import add_parser_prefix, add_parser_yes, confirm, get_prefix, license_check_warn


def configure_parser(sub_parsers):
    p = sub_parsers.add_parser(
        'update',
        formatter_class = RawDescriptionHelpFormatter,
        description     = "Update Anaconda packages.",
        help            = "Update Anaconda packages.",
        epilog          = activate_example,
    )
    add_parser_yes(p)
    add_parser_prefix(p)
    p.add_argument(
        'pkg_names',
        metavar = 'package_name',
        action  = "store",
        nargs   = '*',
        help    = "names of packages to update (default: anaconda)",
    )
    p.set_defaults(func=execute)


def execute(args, parser):
    conda = Anaconda()

    license_check_warn()

    prefix = get_prefix(args)

    env = conda.lookup_environment(prefix)

    if len(args.pkg_names) == 0:
        args.pkg_names.append('anaconda')

    plan = create_update_plan(env, args.pkg_names)

    if plan.empty():
        print 'All packages already at latest compatible version'
        return

    print "Updating Anaconda environment at %s" % env.prefix

    print plan

    confirm(args)
    plan.execute(env)


activate_example = '''
examples:
    conda update -p ~/anaconda/envs/myenv scipy

'''
