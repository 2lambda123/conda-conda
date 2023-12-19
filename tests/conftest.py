# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from conda.base.context import context, reset_context
from conda.testing import conda_cli, path_factory, tmp_env  # noqa: F401

from . import http_test_server
from .fixtures_jlap import (  # noqa: F401
    package_repository_base,
    package_server,
    package_server_ssl,
)

pytest_plugins = (
    # Add testing fixtures and internal pytest plugins here
    "conda.testing.gateways.fixtures",
    "conda.testing.notices.fixtures",
    "conda.testing.fixtures",
)


@pytest.fixture
def test_recipes_channel(monkeypatch: MonkeyPatch) -> Path:
    local = Path(__file__).parent / "test-recipes"
    monkeypatch.setenv("CONDA_BLD_PATH", str(local))
    monkeypatch.setenv("CONDA_USE_LOCAL", "true")
    reset_context()
    assert local.samefile(context.bld_path)
    assert context.use_local

    return local


@pytest.fixture
def legacy_repodata_channel(monkeypatch: MonkeyPatch) -> Path:
    local = Path(__file__).parent / "data" / "legacy_repodata"
    monkeypatch.setenv("CONDA_BLD_PATH", str(local))
    monkeypatch.setenv("CONDA_USE_LOCAL", "true")
    reset_context()
    assert local.samefile(context.bld_path)
    assert context.use_local

    return local


@pytest.fixture
def clear_cache():
    from conda.core.subdir_data import SubdirData

    SubdirData.clear_cached_local_channel_data(exclude_file=False)


@pytest.fixture(scope="session")
def support_file_server():
    """Open a local web server to test remote support files."""
    base = Path(__file__).parents[0] / "conda_env" / "support"
    http = http_test_server.run_test_server(str(base))
    yield http
    # shutdown is checked at a polling interval, or the daemon thread will shut
    # down when the test suite exits.
    http.shutdown()


@pytest.fixture
def support_file_server_port(support_file_server):
    return support_file_server.socket.getsockname()[1]


@pytest.fixture
def clear_cuda_version():
    from conda.plugins.virtual_packages import cuda

    cuda.cached_cuda_version.cache_clear()


@pytest.fixture(autouse=True)
def do_not_register_envs(monkeypatch):
    """Do not register environments created during tests"""
    monkeypatch.setenv("CONDA_REGISTER_ENVS", "false")


@pytest.fixture(autouse=True)
def do_not_notify_outdated_conda(monkeypatch):
    """Do not notify about outdated conda during tests"""
    monkeypatch.setenv("CONDA_NOTIFY_OUTDATED_CONDA", "false")
