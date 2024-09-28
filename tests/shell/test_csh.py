# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import pytest

from conda import __version__ as CONDA_VERSION

from . import SKIPIF_ON_WIN, InteractiveShell

pytestmark = SKIPIF_ON_WIN
PARAMETRIZE_CSH = pytest.mark.parametrize("shell", ["csh", "tcsh"], indirect=True)


@PARAMETRIZE_CSH
def test_shell_available(shell: str) -> None:
    # the fixture does all the work
    pass


@PARAMETRIZE_CSH
def test_basic_integration(
    shell_wrapper_integration: tuple[str, str, str], shell: str
) -> None:
    prefix, prefix2, prefix3 = shell_wrapper_integration

    with InteractiveShell(shell) as interactive:
        interactive.sendline("conda --version")
        interactive.expect_exact(f"conda {CONDA_VERSION}")
        interactive.assert_env_var("CONDA_SHLVL", "0")
        interactive.sendline("conda activate base")
        interactive.assert_env_var("prompt", "(base).*")
        interactive.assert_env_var("CONDA_SHLVL", "1")
        interactive.sendline(f'conda activate "{prefix}"')
        interactive.assert_env_var("CONDA_SHLVL", "2")
        interactive.assert_env_var("CONDA_PREFIX", prefix, True)
        interactive.sendline("conda deactivate")
        interactive.assert_env_var("CONDA_SHLVL", "1")
        interactive.sendline("conda deactivate")
        interactive.assert_env_var("CONDA_SHLVL", "0")

        assert "CONDA_PROMPT_MODIFIER" not in str(interactive.p.after)

        interactive.sendline("conda deactivate")
        interactive.assert_env_var("CONDA_SHLVL", "0")
