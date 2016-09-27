# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from conda.base.context import context
from conda.common.url import path_to_url
from conda.models.channel import Channel, UrlChannel, split_platform
from conda.utils import on_win
from logging import getLogger
from unittest import TestCase

try:
    from unittest import mock
except ImportError:
    import mock
patch = mock.patch

log = getLogger(__name__)


platform = context.subdir
DEFAULT_URLS = ['https://repo.continuum.io/pkgs/free/%s/' % platform,
                 'https://repo.continuum.io/pkgs/free/noarch/',
                 'https://repo.continuum.io/pkgs/pro/%s/' % platform,
                 'https://repo.continuum.io/pkgs/pro/noarch/']
if on_win:
    DEFAULT_URLS.extend(['https://repo.continuum.io/pkgs/msys2/%s/' % platform,
                          'https://repo.continuum.io/pkgs/msys2/noarch/'])


class ChannelTests(TestCase):

    def test_channel_cache(self):
        Channel._reset_state()
        assert len(Channel._cache_) == 0
        dc = Channel('defaults')
        assert len(Channel._cache_) == 1
        dc1 = Channel('defaults')
        assert len(Channel._cache_) == 1
        dc2 = Channel('defaults')
        assert len(Channel._cache_) == 1

        assert dc1 is dc
        assert dc2 is dc

        dc3 = Channel(dc)
        assert len(Channel._cache_) == 1
        assert dc3 is dc

        ccc = Channel('conda-canary')
        assert len(Channel._cache_) == 2

        ccc1 = Channel('conda-canary')
        assert len(Channel._cache_) == 2
        assert ccc1 is ccc

    def test_default_channel(self):
        dc = Channel('defaults')
        # assert isinstance(dc, DefaultChannel)

        assert dc.base_url == 'https://conda.anaconda.org/defaults'
        assert dc.canonical_name == 'defaults'
        assert dc.urls == DEFAULT_URLS

        assert dc._scheme == "https"
        assert dc._netloc == "conda.anaconda.org"
        assert dc._path == "/defaults"
        assert dc._platform is None

    def test_url_channel_w_platform(self):
        channel = Channel('https://repo.continuum.io/pkgs/free/osx-64/')
        assert isinstance(channel, UrlChannel)

        assert channel._scheme == "https"
        assert channel._netloc == "repo.continuum.io"
        assert channel._path == "/pkgs/free"
        assert channel._platform == 'osx-64'

        assert channel.base_url == 'https://repo.continuum.io/pkgs/free'
        assert channel.canonical_name == 'defaults'
        assert channel.urls == DEFAULT_URLS

    def test_url_channel_wo_platform(self):
        channel = Channel('https://repo.continuum.io/pkgs/free/')
        assert isinstance(channel, UrlChannel)

        assert channel._scheme == "https"
        assert channel._netloc == "repo.continuum.io"
        assert channel._path == "/pkgs/free"
        assert channel._platform is None

        platform = context.subdir
        assert channel.base_url == 'https://repo.continuum.io/pkgs/free'
        assert channel.canonical_name == 'defaults'
        assert channel.urls == DEFAULT_URLS

    def test_split_platform(self):
        assert split_platform('/pkgs/free/') == ('/pkgs/free', None)
        assert split_platform('/pkgs/free') == ('/pkgs/free', None)
        assert split_platform('/pkgs/free/osx-64/') == ('/pkgs/free', 'osx-64')
        assert split_platform('/pkgs/free/osx-64') == ('/pkgs/free', 'osx-64')

        assert split_platform('/') == ('/', None)
        assert split_platform('') == ('/', None)
        assert split_platform(None) == ('/', None)

    def test_local_channel(self):
        local = Channel('local')
        assert local.canonical_name == "local"
        build_path = path_to_url(context.local_build_root)
        local_urls = ['%s/%s/' % (build_path, context.subdir),
                      '%s/noarch/' % build_path]
        assert local.urls == local_urls

        lc = Channel(build_path)
        assert lc.canonical_name == "local"
        assert lc.urls == local_urls

        lc_noarch = Channel(local_urls[1])
        assert lc_noarch.canonical_name == "local"
        assert lc_noarch.urls == local_urls

    def test_canonical_name(self):
        assert Channel('https://repo.continuum.io/pkgs/free').canonical_name == "defaults"
        assert Channel('http://repo.continuum.io/pkgs/free/linux-64').canonical_name == "defaults"
        assert Channel('https://conda.anaconda.org/bioconda').canonical_name == "bioconda"
        assert Channel('http://conda.anaconda.org/bioconda/win-64').canonical_name == "bioconda"
        assert Channel('http://conda.anaconda.org/bioconda/label/main/osx-64').canonical_name == "bioconda/label/main"
        assert Channel('http://conda.anaconda.org/t/tk-abc-123-456/bioconda/win-64').canonical_name == "bioconda"

    def test_urls_from_name(self):
        platform = context.subdir
        assert Channel("bioconda").urls == ["https://conda.anaconda.org/bioconda/%s/" % platform,
                                            "https://conda.anaconda.org/bioconda/noarch/"]
        assert Channel("bioconda/label/dev").urls == [
            "https://conda.anaconda.org/bioconda/label/dev/%s/" % platform,
            "https://conda.anaconda.org/bioconda/label/dev/noarch/"]

    def test_regular_url_channels(self):
        platform = context.subdir
        c = Channel('https://some.other.com/pkgs/free/')
        assert c.canonical_name == "https://some.other.com/pkgs/free"
        assert c.urls == ["https://some.other.com/pkgs/free/%s/" % platform,
                          "https://some.other.com/pkgs/free/noarch/"]

        c = Channel('https://some.other.com/pkgs/free/noarch')
        assert c.canonical_name == "https://some.other.com/pkgs/free"
        assert c.urls == ["https://some.other.com/pkgs/free/%s/" % platform,
                          "https://some.other.com/pkgs/free/noarch/"]

    def test_auth(self):
        assert Channel('http://user:pass@conda.anaconda.org/t/tk-abc-123-456/bioconda/win-64').canonical_name == "bioconda"
        assert Channel('http://conda.anaconda.org/bioconda/label/main/osx-64')._auth == None
        assert Channel('http://user:pass@conda.anaconda.org/bioconda/label/main/osx-64')._auth == 'user:pass'
        assert Channel('http://user:pass@path/to/repo')._auth == 'user:pass'
        assert Channel('http://user:pass@path/to/repo').canonical_name == 'http://path/to/repo'
