# SPDX-FileCopyrightText: © 2012 Continuum Analytics, Inc. <http://continuum.io>
# SPDX-FileCopyrightText: © 2017 Anaconda, Inc. <https://www.anaconda.com>
# SPDX-License-Identifier: BSD-3-Clause
import subprocess
from pathlib import Path

import pytest

from . import http_test_server

pytest_plugins = (
    # Add testing fixtures and internal pytest plugins here
    "conda.testing.gateways.fixtures",
    "conda.testing.notices.fixtures",
    "conda.testing.fixtures",
)


def _conda_build_recipe(recipe):
    subprocess.run(
        ["conda-build", str(Path(__file__).resolve().parent / "test-recipes" / recipe)],
        check=True,
    )
    return recipe


@pytest.fixture(scope="session")
def activate_deactivate_package():
    return _conda_build_recipe("activate_deactivate_package")


@pytest.fixture(scope="session")
def pre_link_messages_package():
    return _conda_build_recipe("pre_link_messages_package")


@pytest.fixture
def clear_cache():
    from conda.core.subdir_data import SubdirData

    SubdirData._cache_.clear()


@pytest.fixture(scope="session")
def support_file_server():
    """
    Open a local web server to test remote support files.
    """
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
