# (c) 2012 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
''' The remote module provides functions for interfacing with remote Anaconda
repositories.

'''
import os
import bz2
import json
import hashlib
import urllib2
import logging
from os.path import join

from config import PACKAGES_DIR


log = logging.getLogger(__name__)
retries = 3


def fetch_repodata(url):
    for x in range(retries):
        for fn in 'repodata.json.bz2', 'repodata.json':
            try:
                fi = urllib2.urlopen(url + fn)
                log.debug("fetched: %s [%s] ..." % (fn, url))
                data = fi.read()
                fi.close()
                if fn.endswith('.bz2'):
                    data = bz2.decompress(data)
                return json.loads(data)

            except IOError:
                log.debug('download failed try: %d' % x)

    raise RuntimeError("failed to fetch repodata from %r" % url)


def fetch_index(channel_urls):
    index = {}
    for url in reversed(channel_urls):
        repodata = fetch_repodata(url)
        new_index = repodata['packages']
        for info in new_index.itervalues():
            info['channel'] = url
        index.update(new_index)
    return index


def fetch_file(url, fn, md5=None, size=None, progress=None,
               dst_dir=PACKAGES_DIR):
    '''
    fetch a file `fn` from `url` and store it into `dst_dir`
    '''
    path = join(dst_dir, fn)
    pp = path + '.part'

    for x in range(retries):
        try:
            fi = urllib2.urlopen(url + fn)
            log.debug("fetching: %s [%s]" % (fn, url))
            n = 0
            h = hashlib.new('md5')
            if size is None:
                length = int(fi.headers["Content-Length"])
            else:
                length = size

            if progress:
                progress.widgets[0] = fn
                progress.maxval = length
                progress.start()

            with open(pp, 'wb') as fo:
                while True:
                    chunk = fi.read(16384)
                    if not chunk:
                        break
                    fo.write(chunk)
                    if md5:
                        h.update(chunk)
                    n += len(chunk)
                    if progress:
                        progress.update(n)

            fi.close()
            if progress: progress.finish()
            if md5 and h.hexdigest() != md5:
                raise RuntimeError("MD5 sums mismatch for download: %s" %
                                   fn)
            os.rename(pp, path)
            return url
        except IOError:
            log.debug('download failed try: %d' % x)

    raise RuntimeError("Could not locate file '%s' on any repository" % fn)
