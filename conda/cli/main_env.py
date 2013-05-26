# (c) 2012-2013 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from argparse import RawDescriptionHelpFormatter
from os.path import isdir, join
from shutil import rmtree

from conda.anaconda import Anaconda
from conda.planners import create_activate_plan, create_deactivate_plan
from utils import add_parser_prefix, add_parser_yes, confirm, get_prefix


descr = ("Link or unlink available packages in the specified conda "
         "environment.")
example = '''
examples:
  conda env -ln myenv numba-0.3.1-np17py27_0
  conda env -un myenv numba-0.3.1-np17py27_0
  conda env -rn myenv

'''

def configure_parser(sub_parsers):
    p = sub_parsers.add_parser(
        'env',
        formatter_class = RawDescriptionHelpFormatter,
        description = descr,
        help = descr + " (ADVANCED)",
        epilog = example,
    )
    add_parser_yes(p)
    add_parser_prefix(p)
    adr_group = p.add_mutually_exclusive_group()
    adr_group.add_argument(
        '-l', "--link",
        action  = "store_true",
        help    = "link available packages in the specified conda environment.",
    )
    adr_group.add_argument(
        '-u', "--unlink",
        action  = "store_true",
        help    = "unlink packages in an conda environment.",
    )
    adr_group.add_argument(
        '-r', "--remove",
        action  = "store_true",
        help    = "delete a conda environment.",
    )
    p.add_argument(
        'canonical_names',
        action  = "store",
        metavar = 'canonical_name',
        nargs   = '*',
        help    = "canonical name of package to unlink in the specified conda environment",
    )
    p.set_defaults(func=execute)


def execute(args, parser):
    conda = Anaconda()

    prefix = get_prefix(args)
    env = conda.lookup_environment(prefix)

    if args.link:
        if not args.canonical_names:
            raise RuntimeError("must supply one or more canonical package names for -l/--link")

        plan = create_activate_plan(env, args.canonical_names)

        if plan.empty():
            if len(args.canonical_names) == 1:
                print "Could not find package with canonical name '%s' to link (already linked or unknown)." % args.canonical_names[0]
            else:
                print "Could not find packages with canonical names %s to link." % args.canonical_names
            return

        print plan

        confirm(args)

        try:
            plan.execute(env)
        except IOError:
            raise RuntimeError('One of more of the packages is not locally available, see conda download -h')

    elif args.unlink:
        if not args.canonical_names:
            raise RuntimeError("must supply one or more canonical package names for -u/--unlink")

        plan = create_deactivate_plan(env, args.canonical_names)

        if plan.empty():
            print 'All packages already unlinked, nothing to do'
            if len(args.canonical_names) == 1:
                print "Could not find package with canonical name '%s' to unlink (already unlinked or unknown)." % args.canonical_names[0]
            else:
                print "Could not find packages with canonical names %s to unlink." % args.canonical_names
            return

        print plan

        confirm(args)

        plan.execute(env)

    elif args.remove:

        if args.canonical_names:
            raise RuntimeError("-r/--remove does not accept any canonical package names (use -p/--prefix or -n/--name to specify the environment to remove)")

        if env == conda.root_environment:
            raise RuntimeError("Cannot delete conda root environment")

        if not isdir(join(env.prefix, 'conda-meta')):
            raise RuntimeError("%s does not appear to be an conda environment" % env.prefix)

        print
        print "**** The following conda environment directory will be removed: %s ****" % env.prefix
        print

        confirm(args)

        rmtree(env.prefix)

    else:
        raise RuntimeError("One of -l/--link, -u/--unlink or -r/--remove is required.")
