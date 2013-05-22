import sys
import string
from collections import defaultdict
from os.path import join

import install
from naming import name_dist
from remote import fetch_file
from progressbar import Bar, ETA, FileTransferSpeed, Percentage, ProgressBar


PKGS_DIR = join(sys.prefix, 'pkgs')


def parse(plan):
    actions = defaultdict(list)
    prefix = None
    for a0, a1 in plan:
        print a0, a1
        if a0 == '#':
            continue
        elif a0 == 'PREFIX':
            prefix = a1
        elif a0 in ('FETCH', 'EXTRACT', 'REMOVE', 'UNLINK', 'LINK'):
            actions[a0].append(a1)
        else:
            raise
    return prefix, actions

def display(plan):
    from pprint import pprint
    pprint(parse(plan))

def fetch(index, dist, progress):
    fn = dist + '.tar.bz2'
    info = index[fn]
    fetch_file(info['channel'], fn, md5=info['md5'], size=info['size'],
               progress=progress)

def extract(dist, unused_prefix):
    "Extracting packages ..."
    install.extract(PKGS_DIR, dist)

def remove(dist, unused_prefix):
    "Removing packages ..."
    install.remove(PKGS_DIR, dist)

def link(dist, prefix):
    "Linking packages ..."
    install.link(PKGS_DIR, dist, prefix)

def unlink(dist, prefix):
    "Unlinking packages ..."
    install.unlink(dist, prefix)

def handle(prefix, dists, cb_func, progress):
    if not dists:
        return
    if progress:
        print cb_func.__doc__.strip()
        progress.maxval = len(dists)
        progress.start()
    for i, dist in enumerate(dists):
        if progress:
            progress.widgets[0] = '[%-20s]' % name_dist(dist)
            progress.update(i + 1)
        cb_func(dist, prefix)
    if progress:
        progress.widgets[0] = '[      COMPLETE      ]'
        progress.finish()

def execute(plan, index=None, progress_bar=True):
    if progress_bar:
        fetch_progress = ProgressBar(
            widgets=['', ' ', Percentage(), ' ', Bar(), ' ', ETA(), ' ',
                     FileTransferSpeed()])
        progress = ProgressBar(
            widgets=['', ' ', Bar(), ' ', Percentage()])
    else:
        fetch_progress = None
        progress = None

    prefix = None
    for line in plan:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        cmd, arg = string.split(line, maxsplit=1)
        if cmd == 'PREFIX':
            prefix = arg
        elif cmd == 'PRINT':
            print arg
        elif cmd == 'FETCH':
            fetch(index or {}, arg, fetch_progress)
        elif cmd == 'START' and progress_bar:
            progress.maxval = int(arg)
            progress.start()
        elif cmd == 'EXTRACT':
            install.extract(PKGS_DIR, arg)

#    handle(None, actions['EXTRACT'], extract, progress)
#    handle(prefix, actions['UNLINK'], unlink, progress)
#    handle(prefix, actions['LINK'], link, progress)
#    handle(None, actions['REMOVE'], remove, progress)


if __name__ == '__main__':
    import logging

    from api import get_index

    logging.basicConfig()

    plan = [
        '# install_plan',
        'PREFIX /home/ilan/a150/envs/test',
        'PRINT Fetching packages ...',
        'FETCH python-2.7.5-0',
        'START 3',
        'EXTRACT python-2.7.5-0',
        'EXTRACT scipy-0.11.0-np17py26_p3',
        'EXTRACT mkl-rt-11.0-p0',
    ]
    execute(plan, get_index())
