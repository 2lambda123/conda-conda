# (c) 2012-2013 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function, division, absolute_import

import os
import bz2
import sys
import json
import hashlib
from logging import getLogger
from os.path import isdir, join

from conda import config
from conda.utils import memoized
from conda.connection import connectionhandled_urlopen
from conda.compat import PY3, itervalues
from conda.lock import Locked

if PY3:
    import urllib.request as urllib2
else:
    import urllib2


log = getLogger(__name__)

retries = 3


def fetch_repodata(url, cache={}):
    log.debug("fetching repodata: %s ..." % url)

    request = urllib2.Request(url + 'repodata.json.bz2')
    if url in cache:
        d = cache[url]
        if '_etag' in d:
            request.add_header('If-None-Match', d['_etag'])
        if '_mod' in d:
            request.add_header('If-Modified-Since', d['_mod'])

    try:
        u = connectionhandled_urlopen(request)
        data = u.read()
        u.close()
        d = json.loads(bz2.decompress(data).decode('utf-8'))
        etag = u.info().getheader('Etag')
        if etag:
            d['_etag'] = etag
        timestamp = u.info().getheader('Last-Modified')
        if timestamp:
            d['_mod'] = timestamp
        cache[url] = d

    except urllib2.HTTPError as e:
        msg = "HTTPError: %d  %s\n" % (e.code, e.msg)
        log.debug(msg)
        if e.code != 304:
            raise RuntimeError(msg)

    except urllib2.URLError:
        sys.stderr.write("Error: unknown host: %s\n" % url)

    return cache[url]


@memoized
def fetch_index(channel_urls):
    cache_dir = join(config.pkgs_dir, 'cache')
    if not isdir(cache_dir):
        os.makedirs(cache_dir)
    cache_path = join(cache_dir, 'index.json')
    try:
        cache = json.load(open(cache_path))
    except IOError:
        cache = {}

    index = {}
    for url in reversed(channel_urls):
        repodata = fetch_repodata(url, cache)
        new_index = repodata['packages']
        for info in itervalues(new_index):
            info['channel'] = url
        index.update(new_index)

    try:
        with open(cache_path, 'w') as fo:
            json.dump(cache, fo, indent=2, sort_keys=True)
    except IOError:
        pass

    return index


def fetch_pkg(info, dst_dir=config.pkgs_dir):
    '''
    fetch a package `fn` from `url` and store it into `dst_dir`
    '''
    fn = '%(name)s-%(version)s-%(build)s.tar.bz2' % info
    url = info['channel'] + fn
    path = join(dst_dir, fn)
    pp = path + '.part'

    with Locked(dst_dir):
        for x in range(retries):
            try:
                fi = connectionhandled_urlopen(url)#urllib2.urlopen(url)
            except IOError:
                log.debug("Attempt %d failed at urlopen" % x)
                continue
            if fi is None:
                log.debug("Could not fetch (urlopen returned None)")
                continue
            log.debug("Fetching: %s" % url)
            n = 0
            h = hashlib.new('md5')
            getLogger('fetch.start').info((fn, info['size']))
            need_retry = False
            try:
                fo = open(pp, 'wb')
            except IOError:
                raise RuntimeError("Could not open %r for writing.  "
                             "Permissions problem or missing directory?" % pp)
            while True:
                try:
                    chunk = fi.read(16384)
                except IOError:
                    need_retry = True
                    break
                if not chunk:
                    break
                try:
                    fo.write(chunk)
                except IOError:
                    raise RuntimeError("Failed to write to %r." % pp)
                h.update(chunk)
                n += len(chunk)
                getLogger('fetch.update').info(n)

            fo.close()
            if need_retry:
                continue

            fi.close()
            getLogger('fetch.stop').info(None)
            if h.hexdigest() != info['md5']:
                raise RuntimeError("MD5 sums mismatch for download: %s" % fn)
            try:
                os.rename(pp, path)
            except OSError:
                raise RuntimeError("Could not rename %r to %r." % (pp, path))
            return

    raise RuntimeError("Could not locate '%s'" % url)
