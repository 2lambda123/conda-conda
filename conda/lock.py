# (c) 2012-2013 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

"""
Tools for working with locks

A lock is just an empty directory. We use directories because this lets us use
the race condition-proof os.makedirs.

For now, there is one global lock for all of conda, because some things happen
globally (such as downloading packages).

We don't raise an error if the lock is named with the current PID
"""
from __future__ import absolute_import, division, print_function

import logging
import os
import time
from glob import glob
from os.path import abspath, isdir, dirname
from .compat import range
from .exceptions import LockError

LOCKFN = 'conda_lock'

# Keep the string "LOCKERROR" in this string so that external
# programs can look for it.
LOCKSTR = """\
LOCKERROR: It looks like conda is already doing something.
The lock %s was found. Wait for it to finish before continuing.
If you are sure that conda is not running, remove it and try again.
You can also use: $ conda clean --lock
"""

stdoutlog = logging.getLogger('stdoutlog')
log = logging.getLogger(__name__)


def touch(file_name, times=None):
    """ Touch function like touch in Unix shell
    :param file_name: the name of file
    :param times: the access and modified time
    Examples:
        touch("hello_world.py")
    """
    with open(file_name, 'a'):
        os.utime(file_name, times)


class FileLock(object):
    """
    Context manager to handle locks.
    """
    def __init__(self, file_path, retries=10):
        """
        :param filepath: The file or directory to be locked
        :param retries: max number of retries
        :return:
        """
        self.file_path = abspath(file_path)
        self.retries = retries

    def __enter__(self):

        sleep_time = 1
        self.lock_path = "{0}.pid{1}.{2}".format(self.file_path, os.getpid(), LOCKFN)
        lock_glob_str = "{0}.pid*.{1}".format(self.file_path, LOCKFN)
        last_glob_match = None

        for _ in range(self.retries):
            # search, whether there is process already locked on this file
            glob_result = glob(lock_glob_str)
            if glob_result:
                stdoutlog.info(LOCKSTR % glob_result[0])
                stdoutlog.info("Sleeping for %s seconds\n" % sleep_time)

                time.sleep(sleep_time/10)
                sleep_time *= 2
                last_glob_match = glob_result
            else:
                # Just for unittest, should never happen in real-world application
                if not isdir(dirname(self.lock_path)):
                    os.makedirs(dirname(self.file_path))
                # create a lock
                touch(self.lock_path)
                return self

        stdoutlog.error("Exceeded max retries, giving up")
        raise LockError(LOCKSTR % last_glob_match[0])

    def __exit__(self, exc_type, exc_value, traceback):
        from .install import rm_rf
        rm_rf(self.lock_path)
