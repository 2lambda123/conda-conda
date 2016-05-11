# -*- coding: utf-8 -*-
from __future__ import print_function, division, absolute_import

from collections import namedtuple
from logging import getLogger
from os import remove
from os.path import isdir, isfile, join
from re import match
from shlex import split
from subprocess import CalledProcessError, Popen, PIPE
import sys
try:
    from setuptools.command.build_py import build_py
    from setuptools.command.sdist import sdist
    from setuptools.command.test import test as TestCommand
except ImportError:
    from distutils.command.build_py import build_py
    from distutils.command.sdist import sdist
    TestCommand = object


from .path import absdirname, PackageFile

log = getLogger(__name__)

Response = namedtuple('Response', ['stdout', 'stderr', 'rc'])


def call(path, command, raise_on_error=True):
    p = Popen(split(command), cwd=path, stdout=PIPE, stderr=PIPE)
    stdout, stderr = p.communicate()
    rc = p.returncode
    log.debug("{0} $  {1}\n"
              "  stdout: {2}\n"
              "  stderr: {3}\n"
              "  rc: {4}"
              .format(path, command, stdout, stderr, rc))
    if raise_on_error and rc != 0:
        raise CalledProcessError(rc, command, "stdout: {1}\nstderr: {2}".format(stdout, stderr))
    return Response(stdout, stderr, rc)


def _get_version_from_pkg_info(package_name):
    with PackageFile('.version', package_name) as fh:
        return fh.read()


def _is_git_dirty(path):
    try:
        call(path, "git diff --quiet")
        call(path, "git diff --cached --quiet")
        return False
    except CalledProcessError:
        return True


def _get_most_recent_git_tag(path):
    try:
        return call(path, "git describe --tags").stdout.strip()
    except CalledProcessError as e:
        if e.returncode == 128:
            return None
        elif e.returncode == 127:
            log.error('git not found on path')
            raise
        else:
            raise  # pragma: no cover


def _get_git_hash(path):
    try:
        return call(path, "git rev-parse HEAD").stdout.strip()[:7]
    except CalledProcessError:
        return 0


def _get_version_from_git_tag(path):
    """Return a PEP440-compliant version derived from the git status.
    If that fails for any reason, return the first 7 chars of the changeset hash.
    """
    tag = _get_most_recent_git_tag(path)
    if tag is None:
        return tag
    m = match(b"(?P<xyz>\d+\.\d+\.\d+)(?:-(?P<dev>\d+)-(?P<hash>.+))?", tag)
    version = m.group('xyz').decode('utf-8')
    if m.group('dev') or _is_git_dirty(path):
        dev = (m.group('dev') or b'0').decode('utf-8')
        hash_ = (m.group('hash') or _get_git_hash(path)).decode('utf-8')
        version += ".dev{dev}+{hash_}".format(dev=dev, hash_=hash_)
    return version


def is_git_repo(path):
    return call(path, "git rev-parse", raise_on_error=False).rc == 0


def get_git_version_or_none(file):
    here = absdirname(file)
    return _get_version_from_git_tag(here) if is_git_repo(here) else None


def get_version(file, package):
    """Returns a version string for the current package, derived
    either from git or from a .version file.

    This function is expected to run in two contexts. In a development
    context, where .git/ exists, the version is pulled from git tags.
    Using the BuildPyCommand and SDistCommand classes for cmdclass in
    setup.py will write a .version file into any dist.

    In an installed context, the .version file written at dist build
    time is the source of version information.

    """
    # check for .version file
    try:
        version_from_pkg = _get_version_from_pkg_info(package)
        return version_from_pkg.decode('UTF-8') if hasattr(version_from_pkg, 'decode') else version_from_pkg  # NOQA
    except IOError:
        # no .version file found; fall back to git repo
        here = absdirname(file)
        version = _get_version_from_git_tag(here)
        if version is not None:
            return version
    raise RuntimeError("Could not get package version (no .git or .version file)")


def write_version_into_init(target_dir, version):
    target_init_file = join(target_dir, "__init__.py")
    assert isfile(target_init_file), "File not found: {0}".format(target_init_file)
    with open(target_init_file, 'r') as f:
        init_lines = f.readlines()
    for q in range(len(init_lines)):
        if init_lines[q].startswith('__version__'):
            init_lines[q] = '__version__ = "{0}"\n'.format(version)
        elif init_lines[q].startswith(('from auxlib', 'import auxlib')):
            init_lines[q] = None
    print("UPDATING {0}".format(target_init_file))
    remove(target_init_file)
    with open(target_init_file, 'w') as f:
        f.write(''.join(l for l in init_lines if l is not None))


def write_version_file(target_dir, version):
    assert isdir(target_dir), "Directory not found: {0}".format(target_dir)
    target_file = join(target_dir, ".version")
    with open(target_file, 'w') as f:
        f.write(version)


class BuildPyCommand(build_py):
    def run(self):
        build_py.run(self)
        target_dir = join(self.build_lib, self.distribution.metadata.name)
        write_version_into_init(target_dir, self.distribution.metadata.version)
        write_version_file(target_dir, self.distribution.metadata.version)


class SDistCommand(sdist):
    def make_release_tree(self, base_dir, files):
        sdist.make_release_tree(self, base_dir, files)
        target_dir = join(base_dir, self.distribution.metadata.name)
        write_version_into_init(target_dir, self.distribution.metadata.version)
        write_version_file(target_dir, self.distribution.metadata.version)


class Tox(TestCommand):
    user_options = [('tox-args=', 'a', "Arguments to pass to tox")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.tox_args = None

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import tox
        import shlex
        args = self.tox_args
        if args:
            args = shlex.split(self.tox_args)
        else:
            args = ''
        errno = tox.cmdline(args=args)
        sys.exit(errno)
