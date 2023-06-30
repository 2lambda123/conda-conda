# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from os.path import exists, join

import pytest

from conda.auxlib.compat import Utf8NamedTemporaryFile
from conda.gateways.disk.delete import rm_rf
from conda.testing import TmpEnvFixture
from conda.testing.integration import (
    PYTHON_BINARY,
    Commands,
    make_temp_prefix,
    package_is_installed,
    run_command,
)


@pytest.mark.integration
def test_basic(tmp_env: TmpEnvFixture):
    with tmp_env("python=3.5") as prefix:
        assert exists(join(prefix, PYTHON_BINARY))
        assert package_is_installed(prefix, "python=3")

        output, error, _ = run_command(Commands.LIST, str(prefix), "-e")

        with Utf8NamedTemporaryFile(mode="w", suffix="txt", delete=False) as env_txt:
            env_txt.write(output)
            env_txt.flush()
            env_txt.close()
            prefix2 = make_temp_prefix()
            run_command(Commands.CREATE, prefix2, "--file", env_txt.name)

            assert package_is_installed(prefix2, "python")

        output2, error, _ = run_command(Commands.LIST, prefix2, "-e")
        assert output == output2


@pytest.mark.integration
@pytest.mark.skipif(True, reason="Bring back `conda list --export` #3445")
def test_multi_channel_export(tmp_env: TmpEnvFixture):
    """
    When try to import from txt
    every package should come from same channel
    """
    with tmp_env("python=3.5") as prefix:
        assert exists(join(prefix, PYTHON_BINARY))
        assert package_is_installed(prefix, "python=3")

        run_command(Commands.INSTALL, str(prefix), "six", "-c", "conda-forge")
        assert package_is_installed(prefix, "six")

        output, error, _ = run_command(Commands.LIST, str(prefix), "-e")
        assert "conda-forge" in output

        try:
            with Utf8NamedTemporaryFile(
                mode="w", suffix="txt", delete=False
            ) as env_txt:
                env_txt.write(output)
                env_txt.close()
                prefix2 = make_temp_prefix()
                run_command(Commands.CREATE, prefix2, "--file", env_txt.name)

                assert package_is_installed(prefix2, "python")
            output2, error, _ = run_command(Commands.LIST, prefix2, "-e")
            assert output == output2
        finally:
            rm_rf(env_txt.name)


@pytest.mark.integration
def test_multi_channel_explicit(tmp_env: TmpEnvFixture):
    """
    When try to import from txt
    every package should come from same channel
    """
    with tmp_env("python=3.5") as prefix:
        assert exists(join(prefix, PYTHON_BINARY))
        assert package_is_installed(prefix, "python=3")

        run_command(Commands.INSTALL, str(prefix), "six", "-c", "conda-forge")
        assert package_is_installed(prefix, "conda-forge::six")

        output, error, _ = run_command(Commands.LIST, str(prefix), "--explicit")
        assert not error
        assert "conda-forge" in output

        urls1 = {url for url in output.split() if url.startswith("http")}

        try:
            with Utf8NamedTemporaryFile(
                mode="w", suffix="txt", delete=False
            ) as env_txt:
                env_txt.write(output)
                env_txt.close()
                prefix2 = make_temp_prefix()
                run_command(Commands.CREATE, prefix2, "--file", env_txt.name)

                assert package_is_installed(prefix2, "python")
                assert package_is_installed(prefix2, "six")
            output2, error2, _ = run_command(Commands.LIST, prefix2, "--explicit")
            assert not error2
            urls2 = {url for url in output2.split() if url.startswith("http")}
            assert urls1 == urls2
        finally:
            rm_rf(env_txt.name)
