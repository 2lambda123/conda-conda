# -*- coding: utf-8 -*-
# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import absolute_import, division, print_function, unicode_literals

from errno import EACCES
from logging import getLogger
from os import environ, listdir
from os.path import dirname, isdir, isfile, join, normpath

from .prefix_data import PrefixData
from ..base.context import context
from ..common.compat import ensure_text_type, on_win, open
from ..common.path import expand
from ..gateways.disk.read import yield_lines
from ..gateways.disk.test import is_conda_environment

log = getLogger(__name__)

# If you want to have a better time while testing `conda`, you should set CONDA_TEST_USER_ENVIRONMENTS_TXT_FILE
# to `/dev/null`.
USER_ENVIRONMENTS_TXT_FILE = environ.get('CONDA_TEST_USER_ENVIRONMENTS_TXT_FILE',
                                         expand(join('~', '.conda', 'environments.txt')))


def register_env(location):
    location = normpath(location)

    if "placehold_pl" in location or "skeleton_" in location:
        # Don't record envs created by conda-build.
        return

    if location in yield_lines(USER_ENVIRONMENTS_TXT_FILE):
        # Nothing to do. Location is already recorded in a known environments.txt file.
        return

    try:
        with open(USER_ENVIRONMENTS_TXT_FILE, 'a') as fh:
            fh.write(ensure_text_type(location))
            fh.write('\n')
    except EnvironmentError as e:
        if e.errno == EACCES:
            log.warn("Unable to register environment. Path not writable.\n"
                     "  environment location: %s\n"
                     "  registry file: %s", location, USER_ENVIRONMENTS_TXT_FILE)
        else:
            raise


def unregister_env(location):
    if isdir(location):
        meta_dir = join(location, 'conda-meta')
        if isdir(meta_dir):
            meta_dir_contents = listdir(meta_dir)
            if len(meta_dir_contents) > 1:
                # if there are any files left other than 'conda-meta/history'
                #   then don't unregister
                return

    _clean_environments_txt(USER_ENVIRONMENTS_TXT_FILE, location)


def list_all_known_prefixes():
    all_env_paths = set()
    if on_win:
        home_dir_dir = dirname(expand('~'))
        for home_dir in listdir(home_dir_dir):
            environments_txt_file = join(home_dir_dir, home_dir, '.conda', 'environments.txt')
            if isfile(environments_txt_file):
                all_env_paths.update(_clean_environments_txt(environments_txt_file))
    else:
        from os import geteuid
        from pwd import getpwall
        if geteuid() == 0:
            search_dirs = tuple(pwentry.pw_dir for pwentry in getpwall()) or (expand('~'),)
        else:
            search_dirs = (expand('~'),)
        for home_dir in search_dirs:
            environments_txt_file = join(home_dir, '.conda', 'environments.txt')
            if isfile(environments_txt_file):
                all_env_paths.update(_clean_environments_txt(environments_txt_file))

    # in case environments.txt files aren't complete, also add all known conda environments in
    # all envs_dirs
    envs_dirs = (envs_dir for envs_dir in context.envs_dirs if isdir(envs_dir))
    all_env_paths.update(path for path in (
        join(envs_dir, name) for envs_dir in envs_dirs for name in listdir(envs_dir)
    ) if path not in all_env_paths and is_conda_environment(path))

    all_env_paths.add(context.root_prefix)
    return sorted(all_env_paths)


def query_all_prefixes(spec):
    for prefix in list_all_known_prefixes():
        prefix_recs = tuple(PrefixData(prefix).query(spec))
        if prefix_recs:
            yield prefix, prefix_recs


def _clean_environments_txt(environments_txt_file, remove_location=None):
    if not isfile(environments_txt_file):
        return ()

    if remove_location:
        remove_location = normpath(remove_location)
    environments_txt_lines = tuple(yield_lines(environments_txt_file))
    environments_txt_lines_cleaned = tuple(
        prefix for prefix in environments_txt_lines
        if prefix != remove_location and is_conda_environment(prefix)
    )
    if environments_txt_lines_cleaned != environments_txt_lines:
        _rewrite_environments_txt(environments_txt_file, environments_txt_lines_cleaned)
    return environments_txt_lines_cleaned


def _rewrite_environments_txt(environments_txt_file, prefixes):
    try:
        with open(environments_txt_file, 'w') as fh:
            fh.write('\n'.join(prefixes))
            fh.write('\n')
    except EnvironmentError as e:
        log.info("File not cleaned: %s", environments_txt_file)
        log.debug('%r', e, exc_info=True)
