# (c) 2012-2013 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
from __future__ import print_function, division, absolute_import

from argparse import RawDescriptionHelpFormatter
import os
import sys

from os.path import join, getsize

from conda.cli import common
import conda.config as config
from conda.utils import human_bytes

try:
    from builtins import PermissionError
except ImportError:  #py2
    from __builtin__ import OSError as PermissionError


descr = """
Remove unused packages and caches
"""

example = """
examples:
    conda clean --tarballs
"""

def configure_parser(sub_parsers):
    p = sub_parsers.add_parser(
        'clean',
        formatter_class = RawDescriptionHelpFormatter,
        description = descr,
        help = descr,
        epilog = example,
    )

    common.add_parser_yes(p)
    common.add_parser_json(p)
    p.add_argument(
        "-i", "--index-cache",
        action = "store_true",
        help = "remove index cache",
    )
    p.add_argument(
        "-l", "--lock",
        action = "store_true",
        help = "remove all conda lock files",
    )
    p.add_argument(
        "-t", "--tarballs",
        action = "store_true",
        help = "remove cached package tarballs",
    )
    p.add_argument(
        '-p', '--packages',
        action='store_true',
        help="""remove unused cached packages. Warning: this does not check
    for symlinked packages.""",
    )
    p.set_defaults(func=execute)


def find_lock():
    from os.path import join

    from conda.lock import LOCKFN

    lock_dirs = config.pkgs_dirs
    lock_dirs += [config.root_dir]
    for envs_dir in config.envs_dirs:
        for fn in os.listdir(envs_dir):
            if os.path.isdir(join(envs_dir, fn)):
                lock_dirs.append(join(envs_dir, fn))

    try:
        from conda_build.config import croot
        lock_dirs.append(croot)
    except ImportError:
        pass

    for dir in lock_dirs:
        if not os.path.exists(dir):
            continue
        for dn in os.listdir(dir):
            if os.path.isdir(join(dir, dn)) and dn.startswith(LOCKFN):
                path = join(dir, dn)
                yield path


def rm_lock(locks, verbose=True):
    for path in locks:
        if verbose:
            print('removing: %s' % path)
        os.rmdir(path)


def find_tarballs():
    pkgs_dir = config.pkgs_dirs[0]

    rmlist = []
    for fn in os.listdir(pkgs_dir):
        if fn.endswith('.tar.bz2') or fn.endswith('.tar.bz2.part'):
            rmlist.append(fn)

    if not rmlist:
        return pkgs_dir, rmlist, 0

    totalsize = 0
    for fn in rmlist:
        size = getsize(join(pkgs_dir, fn))
        totalsize += size

    return pkgs_dir, rmlist, totalsize


def rm_tarballs(args, pkgs_dir, rmlist, totalsize, verbose=True):
    if verbose:
        print('Cache location: %s' % pkgs_dir)

    if not rmlist:
        if verbose:
            print("There are no tarballs to remove")
        return

    if verbose:
        print("Will remove the following tarballs:")
        print()

        maxlen = len(max(rmlist, key=lambda x: len(str(x))))
        fmt = "%-40s %10s"
        for fn in rmlist:
            size = getsize(join(pkgs_dir, fn))
            print(fmt % (fn, human_bytes(size)))
        print('-' * (maxlen + 2 + 10))
        print(fmt % ('Total:', human_bytes(totalsize)))
        print()

    if not args.json:
        common.confirm_yn(args)
    if args.json and args.dry_run:
        return

    for fn in rmlist:
        if verbose:
            print("removing %s" % fn)
        try:
            os.unlink(join(pkgs_dir, fn))
        except PermissionError:
            print("Permission denied to remove {}".format(join(pkgs_dir, fn)))


def find_pkgs():
    # TODO: This doesn't handle packages that have hard links to files within
    # themselves, like bin/python3.3 and bin/python3.3m in the Python package
    from os.path import join, isdir
    from os import lstat, walk, listdir

    pkgs_dir = config.pkgs_dirs[0]
    warnings = []

    rmlist = []
    pkgs = [i for i in listdir(pkgs_dir) if isdir(join(pkgs_dir, i)) and
        # Only include actual packages
        isdir(join(pkgs_dir, i, 'info'))]
    for pkg in pkgs:
        breakit = False
        for root, dir, files in walk(join(pkgs_dir, pkg)):
            if breakit:
                break
            for fn in files:
                try:
                    stat = lstat(join(root, fn))
                except OSError as e:
                    warnings.append((fn, e))
                    continue
                if stat.st_nlink > 1:
                    # print('%s is installed: %s' % (pkg, join(root, fn)))
                    breakit = True
                    break
        else:
            rmlist.append(pkg)

    if not rmlist:
        return pkgs_dir, rmlist, warnings, 0, []

    totalsize = 0
    pkgsizes = []
    for pkg in rmlist:
        pkgsize = 0
        for root, dir, files in walk(join(pkgs_dir, pkg)):
            for fn in files:
                # We don't have to worry about counting things twice:  by
                # definition these files all have a link count of 1!
                size = lstat(join(root, fn)).st_size
                totalsize += size
                pkgsize += size
        pkgsizes.append(pkgsize)

    return pkgs_dir, rmlist, warnings, totalsize, pkgsizes


def rm_pkgs(args, pkgs_dir, rmlist, warnings, totalsize, pkgsizes,
            verbose=True):
    from conda.install import rm_rf

    if verbose:
        print('Cache location: %s' % pkgs_dir)
        for fn, exception in warnings:
            print(exception)

    if not rmlist:
        if verbose:
            print("There are no unused packages to remove")
        return

    if verbose:
        print("Will remove the following packages:")
        print()
        maxlen = len(max(rmlist, key=lambda x: len(str(x))))
        fmt = "%-40s %10s"
        for pkg, pkgsize in zip(rmlist, pkgsizes):
            print(fmt % (pkg, human_bytes(pkgsize)))
        print('-' * (maxlen + 2 + 10))
        print(fmt % ('Total:', human_bytes(totalsize)))
        print()

    if not args.json:
        common.confirm_yn(args)
    if args.json and args.dry_run:
        return

    for pkg in rmlist:
        if verbose:
            print("removing %s" % pkg)
        try:
            rm_rf(join(pkgs_dir, pkg))
        except PermissionError:
            print('Permission denied to remove {}'.format(join(pkgs_dir, pkg)))


def rm_index_cache():
    from conda.install import rm_rf
    for pkg_dir in config.pkgs_dirs:
        cache_dir = join(pkg_dir, 'cache')
        try:
            rm_rf(cache_dir)
            print('Removed {}'.format(cache_dir))
        except PermissionError:
            print('Permission denied to remove {}'.format(cache_dir))


def execute(args, parser):
    json_result = {
        'success': True
    }

    if args.lock:
        locks = list(find_lock())
        json_result['lock'] = {
            'files': locks
        }
        rm_lock(locks, verbose=not args.json)
    if args.tarballs:
        pkgs_dir, rmlist, totalsize = find_tarballs()
        json_result['tarballs'] = {
            'pkgs_dir': pkgs_dir,
            'files': rmlist,
            'total_size': totalsize
        }
        rm_tarballs(args, pkgs_dir, rmlist, totalsize, verbose=not args.json)
    if args.index_cache:
        json_result['index_cache'] = {
            'files': [join(config.pkgs_dirs[0], 'cache')]
        }
        rm_index_cache()
    if args.packages:
        pkgs_dir, rmlist, warnings, totalsize, pkgsizes = find_pkgs()
        json_result['packages'] = {
            'pkgs_dir': pkgs_dir,
            'files': rmlist,
            'total_size': totalsize,
            'warnings': warnings,
            'pkg_sizes': dict(zip(rmlist, pkgsizes))
        }
        rm_pkgs(args, pkgs_dir, rmlist, warnings, totalsize, pkgsizes,
                verbose=not args.json)
    if not (args.lock or args.tarballs or args.index_cache or args.packages):
        common.error_and_exit(
            "One of {--lock, --tarballs, --index-cache, --packages} required",
            error_type="ValueError")

    if args.json:
        common.stdout_json(json_result)
