# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Tools for managing conda environments."""
from __future__ import annotations

import os
from errno import EACCES, ENOENT, EROFS
from logging import getLogger
from os.path import dirname, isdir, isfile, join, normpath
from pathlib import Path

from ..base.constants import PYVENV_CONFIG
from ..base.context import context
from ..common._os import is_admin
from ..common.compat import ensure_text_type, on_win, open
from ..common.path import expand
from ..gateways.disk.read import yield_lines
from ..gateways.disk.test import is_conda_environment
from .prefix_data import PrefixData

log = getLogger(__name__)


# The idea is to mock this to return '/dev/null' (or some temp file) instead.
def get_user_environments_txt_file(userhome="~"):
    return expand(join(userhome, ".conda", "environments.txt"))


def register_env(location):
    if not context.register_envs:
        return

    user_environments_txt_file = get_user_environments_txt_file()
    location = normpath(location)
    folder = dirname(location)
    try:
        os.makedirs(folder)
    except:
        pass

    if (
        "placehold_pl" in location
        or "skeleton_" in location
        or user_environments_txt_file == os.devnull
    ):
        # Don't record envs created by conda-build.
        return

    if location in yield_lines(user_environments_txt_file):
        # Nothing to do. Location is already recorded in a known environments.txt file.
        return

    user_environments_txt_directory = os.path.dirname(user_environments_txt_file)
    try:
        os.makedirs(user_environments_txt_directory, exist_ok=True)
    except OSError as exc:
        log.warn(
            "Unable to register environment. "
            f"Could not create {user_environments_txt_directory}. "
            f"Reason: {exc}"
        )
        return

    try:
        with open(user_environments_txt_file, "a") as fh:
            fh.write(ensure_text_type(location))
            fh.write("\n")
    except OSError as e:
        if e.errno in (EACCES, EROFS, ENOENT):
            log.warn(
                "Unable to register environment. Path not writable or missing.\n"
                "  environment location: %s\n"
                "  registry file: %s",
                location,
                user_environments_txt_file,
            )
        else:
            raise


def unregister_env(location):
    if isdir(location):
        meta_dir = join(location, "conda-meta")
        if isdir(meta_dir):
            meta_dir_contents = tuple(entry.name for entry in os.scandir(meta_dir))
            if len(meta_dir_contents) > 1:
                # if there are any files left other than 'conda-meta/history'
                #   then don't unregister
                return

    _clean_environments_txt(get_user_environments_txt_file(), location)


def list_all_known_prefixes():
    all_env_paths = set()
    # If the user is an admin, load environments from all user home directories
    if is_admin():
        if on_win:
            home_dir_dir = dirname(expand("~"))
            search_dirs = tuple(entry.path for entry in os.scandir(home_dir_dir))
        else:
            from pwd import getpwall

            search_dirs = tuple(pwentry.pw_dir for pwentry in getpwall()) or (
                expand("~"),
            )
    else:
        search_dirs = (expand("~"),)
    for home_dir in filter(None, search_dirs):
        environments_txt_file = get_user_environments_txt_file(home_dir)
        if isfile(environments_txt_file):
            try:
                # When the user is an admin, some environments.txt files might
                # not be readable (if on network file system for example)
                all_env_paths.update(_clean_environments_txt(environments_txt_file))
            except PermissionError:
                log.warning(f"Unable to access {environments_txt_file}")

    # in case environments.txt files aren't complete, also add all known conda environments in
    # all envs_dirs
    envs_dirs = (envs_dir for envs_dir in context.envs_dirs if isdir(envs_dir))
    all_env_paths.update(
        path
        for path in (
            entry.path for envs_dir in envs_dirs for entry in os.scandir(envs_dir)
        )
        if path not in all_env_paths and is_conda_environment(path)
    )

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
        prefix
        for prefix in environments_txt_lines
        if prefix != remove_location and is_conda_environment(prefix)
    )
    if environments_txt_lines_cleaned != environments_txt_lines:
        _rewrite_environments_txt(environments_txt_file, environments_txt_lines_cleaned)
    return environments_txt_lines_cleaned


def _rewrite_environments_txt(environments_txt_file, prefixes):
    try:
        with open(environments_txt_file, "w") as fh:
            fh.write("\n".join(prefixes))
            fh.write("\n")
    except OSError as e:
        log.info("File not cleaned: %s", environments_txt_file)
        log.debug("%r", e, exc_info=True)


def set_environment_no_site_packages(prefix: str, remove: bool = False) -> None:
    """
    Marks an environment as not using Python's user site packages by inserting a ``pyvenv.cfg``
    file with ``include-system-site-packages`` set to ``false``
    """
    try:
        path = Path(prefix, PYVENV_CONFIG)

        # If it already exists, we simply delete what is there, so we can replace it
        if path.exists():
            path.unlink()

        if not remove:
            with path.open("w") as fp:
                fp.write("include-system-site-packages = false\n")

    except OSError as exc:
        log.error(
            f"Unable to edit \"{PYVENV_CONFIG}\" to set \"include-system-site-packages\""
            f" to \"false\". Reason: {exc}"
        )


def is_environment_no_python_user_packages(prefix: str) -> bool | None:
    """
    Determines whether the environment is configured to use Python's user site packages
    """
    try:
        path = Path(prefix, PYVENV_CONFIG)

        if path.exists():
            lines = tuple(
                filter(None, path.read_text().replace(" ", "").split("\n"))
            )

            return "include-system-site-packages=false" in lines

        return False

    except OSError as exc:
        log.error(
            f"Unable to read \"{PYVENV_CONFIG}\" for environment. Reason: {exc}"
        )
