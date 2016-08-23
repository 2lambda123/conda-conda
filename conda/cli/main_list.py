# (c) Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import absolute_import, division, print_function

import logging
import re
from argparse import RawDescriptionHelpFormatter
from os.path import isdir, isfile

from conda import Message
from .common import (add_parser_help, add_parser_prefix, add_parser_json,
                     add_parser_show_channel_urls, disp_features, stdout_json)
from ..base.context import context, subdir
from ..egg_info import get_egg_info
from ..exceptions import (CondaEnvironmentNotFoundError, CondaFileNotFoundError,
                          CondaEnvironmentError)
from ..install import dist2quad, is_linked, linked, linked_data, name_dist

stdout = logging.getLogger('stdout')

descr = "List linked packages in a conda environment."

# Note, the formatting of this is designed to work well with help2man
examples = """
Examples:

List all packages in the current environment:

    conda list

List all packages installed into the environment 'myenv':

    conda list -n myenv

Save packages for future use:

    conda list --export > package-list.txt

Reinstall packages from an export file:

    conda create -n myenv --file package-list.txt

"""
log = logging.getLogger(__name__)

def configure_parser(sub_parsers):
    p = sub_parsers.add_parser(
        'list',
        description=descr,
        help=descr,
        formatter_class=RawDescriptionHelpFormatter,
        epilog=examples,
        add_help=False,
    )
    add_parser_help(p)
    add_parser_prefix(p)
    add_parser_json(p)
    add_parser_show_channel_urls(p)
    p.add_argument(
        '-c', "--canonical",
        action="store_true",
        help="Output canonical names of packages only. Implies --no-pip. ",
    )
    p.add_argument(
        '-f', "--full-name",
        action="store_true",
        help="Only search for full names, i.e., ^<regex>$.",
    )
    p.add_argument(
        "--explicit",
        action="store_true",
        help="List explicitly all installed conda packaged with URL "
             "(output may be used by conda create --file).",
    )
    p.add_argument(
        "--md5",
        action="store_true",
        help="Add MD5 hashsum when using --explicit",
    )
    p.add_argument(
        '-e', "--export",
        action="store_true",
        help="Output requirement string only (output may be used by "
             " conda create --file).",
    )
    p.add_argument(
        '-r', "--revisions",
        action="store_true",
        help="List the revision history and exit.",
    )
    p.add_argument(
        "--no-pip",
        action="store_false",
        default=True,
        dest="pip",
        help="Do not include pip-only installed packages.")
    p.add_argument(
        'regex',
        action="store",
        nargs="?",
        help="List only packages matching this regular expression.",
    )
    p.set_defaults(func=execute)


def get_export_header_pieces():
    return ('# This file may be used to create an environment using:',
            '# $ conda create --name <env> --file <this file>',
            '# platform: %s' % subdir
            )


def print_export_header():
    stdout.info(Message('export_header_printout', '\n'.join(get_export_header_pieces())))


def get_packages(installed, regex):
    pat = re.compile(regex, re.I) if regex else None
    for dist in sorted(installed, key=lambda x: name_dist(x).lower()):
        name = name_dist(dist)
        if pat and pat.search(name) is None:
            continue

        yield dist


def list_packages(prefix, installed, regex=None, format='human',
                  show_channel_urls=context.show_channel_urls):
    res = 0
    result = []
    for dist in get_packages(installed, regex):
        if format == 'canonical':
            result.append(dist)
            continue
        if format == 'export':
            result.append('='.join(dist2quad(dist)[:3]))
            continue

        try:
            # Returns None if no meta-file found (e.g. pip install)
            info = is_linked(prefix, dist)
            features = set(info.get('features', '').split())
            disp = '%(name)-25s %(version)-15s %(build)15s' % info
            disp += '  %s' % disp_features(features)
            schannel = info.get('schannel')
            if show_channel_urls or show_channel_urls is None and schannel != 'defaults':
                disp += '  %s' % schannel
            result.append(disp)
        except (AttributeError, IOError, KeyError, ValueError) as e:
            log.debug("exception for dist %s:\n%r", dist, e)
            result.append('%-25s %-15s %15s' % dist2quad(dist)[:3])

    return res, result


class PrintPackages(Message):

    def __init__(self, prefix, regex=None, format='human', piplist=False):
        if not isdir(prefix):
            raise CondaEnvironmentError("""\
Error: environment does not exist: %s
#
# Use 'conda create' to create an environment before listing its packages.""" %
                                        prefix)

        installed_packages = linked(prefix)
        if piplist and context.use_pip and format == 'human':
            installed_packages.update(get_egg_info(prefix))
        message_pieces = []
        if not context.json:
            if format == 'human':
                message_pieces.append('# packages in environment at %s:' % prefix)
                message_pieces.append('#')
            if format == 'export':
                message_pieces.extend(get_export_header_pieces())

        _, output = list_packages(prefix, installed_packages, regex, format=format,
                                  show_channel_urls=context.show_channel_urls)
        message_pieces.extend(output)

        super(PrintPackages, self).__init__(self.__class__.__name__,
                                            message_str='\n'.join(message_pieces),
                                            subdir=context.subdir,
                                            installed_packages=dict.fromkeys(installed_packages),
                                            prefix=prefix)


def print_packages(prefix, regex=None, format='human', piplist=False,
                   json=False, show_channel_urls=context.show_channel_urls):
    if not isdir(prefix):
        raise CondaEnvironmentNotFoundError(prefix)

    if not json:
        if format == 'human':
            stdout.info(Message('package_list_header',
                        '# packages in environment at %s:' % prefix, prefix=prefix))
            stdout.info(Message('package_list_header', '#'))
        if format == 'export':
            print_export_header()

    installed = linked(prefix)
    log.debug("installed conda packages:\n%s", installed)
    if piplist and context.use_pip and format == 'human':
        other_python = get_egg_info(prefix)
        log.debug("other installed python packages:\n%s", other_python)
        installed.update(other_python)

    exitcode, output = list_packages(prefix, installed, regex, format=format,
                                     show_channel_urls=show_channel_urls)
    if not json:
        stdout.info(Message('package_list_output', '\n'.join(output)))
    else:
        stdout_json(output)
    return exitcode


def print_explicit(prefix, add_md5=False):
    if not isdir(prefix):
        raise CondaEnvironmentNotFoundError(prefix)
    print_export_header()
    stdout.info(Message('explicit_notify', "@EXPLICIT"))
    for meta in sorted(linked_data(prefix).values(), key=lambda x: x['name']):
        url = meta.get('url')
        if not url or url.startswith('<unknown>'):
            stdout.info(Message('no_info_for_url_notify_message',
                                '# no URL for: %s' % meta['fn'],
                                filename=meta['fn']))
            continue
        md5 = meta.get('md5')
        stdout.info(Message('md5_printout', url + ('#%s' % md5 if add_md5 and md5 else ''),
                            url=url, md5=md5, filename=meta['fn']))


def execute(args, parser):
    prefix = context.prefix_w_legacy_search

    regex = args.regex
    if args.full_name:
        regex = r'^%s$' % regex

    if args.revisions:
        from conda.history import History

        h = History(prefix)
        if isfile(h.path):
            if not args.json:
                h.print_log()
            else:
                stdout_json(h.object_log())
        else:
            raise CondaFileNotFoundError(h.path, "No revision log found: %s\n" % h.path)
        return

    if args.explicit:
        print_explicit(prefix, args.md5)
        return

    if args.canonical:
        format = 'canonical'
    elif args.export:
        print_explicit(prefix, args.md5)
        return
    else:
        format = 'human'

    if args.json:
        format = 'canonical'

    exitcode = print_packages(prefix, regex, format, piplist=args.pip,
                              json=args.json,
                              show_channel_urls=args.show_channel_urls)
    return exitcode
