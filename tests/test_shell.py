# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import os
import platform
import sys
from functools import lru_cache
from logging import getLogger
from os.path import join
from pathlib import Path
from re import escape
from shutil import which
from subprocess import CalledProcessError, check_output
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from conda import CONDA_PACKAGE_ROOT
from conda import __version__ as conda_version
from conda.base.context import context
from conda.common.compat import on_win
from conda.testing.integration import SPACER_CHARACTER

from .shell import (
    ACTIVATE_ARGS,
    DEACTIVATE_ARGS,
    DEV_ARG,
    HDF5_VERSION,
    INSTALL_ARGS,
    InteractiveShell,
)

if TYPE_CHECKING:
    from typing import Any, Callable, Iterator

    from pytest import TempPathFactory

    from conda.testing.fixtures import (
        CondaCLIFixture,
        PathFactoryFixture,
        TmpEnvFixture,
    )


pytestmark = pytest.mark.integration


log = getLogger(__name__)


@lru_cache(maxsize=None)
def bash_unsupported() -> str | None:
    if not (bash := which("bash")):
        return "bash: was not found on PATH"
    elif on_win:
        try:
            output = check_output(f'{bash} -c "uname -v"')
        except CalledProcessError as exc:
            return f"bash: something went wrong while running bash, output:\n{exc.output}\n"
        else:
            if b"Microsoft" in output:
                return "bash: WSL is not yet supported. Pull requests welcome."
            else:
                output = check_output(f"{bash} --version")
                if b"msys" not in output and b"cygwin" not in output:
                    return f"bash: Only MSYS2 and Cygwin bash are supported on Windows, found:\n{output!r}\n"
    return None


skip_unsupported_bash = pytest.mark.skipif(
    bool(bash_unsupported()),
    reason=bash_unsupported() or "bash: supported!",
)


def which_powershell():
    r"""
    Since we don't know whether PowerShell is installed as powershell, pwsh, or pwsh-preview,
    it's helpful to have a utility function that returns the name of the best PowerShell
    executable available, or `None` if there's no PowerShell installed.

    If PowerShell is found, this function returns both the kind of PowerShell install
    found and a path to its main executable.
    E.g.: ('pwsh', r'C:\Program Files\PowerShell\6.0.2\pwsh.exe)
    """
    if on_win:
        posh = which("powershell.exe")
        if posh:
            return "powershell", posh

    posh = which("pwsh")
    if posh:
        return "pwsh", posh

    posh = which("pwsh-preview")
    if posh:
        return "pwsh-preview", posh


@pytest.fixture
def shell_wrapper_integration(
    path_factory: PathFactoryFixture,
) -> Iterator[tuple[str, str, str]]:
    prefix = path_factory(
        prefix=uuid4().hex[:4], name=SPACER_CHARACTER, suffix=uuid4().hex[:4]
    )
    history = prefix / "conda-meta" / "history"
    history.parent.mkdir(parents=True, exist_ok=True)
    history.touch()

    prefix2 = prefix / "envs" / "charizard"
    history2 = prefix2 / "conda-meta" / "history"
    history2.parent.mkdir(parents=True, exist_ok=True)
    history2.touch()

    prefix3 = prefix / "envs" / "venusaur"
    history3 = prefix3 / "conda-meta" / "history"
    history3.parent.mkdir(parents=True, exist_ok=True)
    history3.touch()

    yield str(prefix), str(prefix2), str(prefix3)


def basic_posix(shell, prefix, prefix2, prefix3):
    if shell.shell_name in ("zsh", "dash"):
        conda_is_a_function = "conda is a shell function"
    else:
        conda_is_a_function = "conda is a function"

    case = str.lower if on_win else str

    num_paths_added = len(tuple(shell.activator._get_path_dirs(prefix)))
    prefix_p = shell.path_conversion(prefix)
    prefix2_p = shell.path_conversion(prefix2)
    shell.path_conversion(prefix3)

    PATH0 = shell.get_env_var("PATH", "")
    assert any(path.endswith("condabin") for path in PATH0.split(":"))

    shell.assert_env_var("CONDA_SHLVL", "0")
    # Remove sys.prefix from PATH. It interferes with path entry count tests.
    # We can no longer check this since we'll replace e.g. between 1 and N path
    # entries with N of them in _replace_prefix_in_path() now. It is debatable
    # whether it should be here at all too.
    if PATH0.startswith(shell.path_conversion(sys.prefix) + ":"):
        PATH0 = PATH0[len(shell.path_conversion(sys.prefix)) + 1 :]
        shell.sendline(f'export PATH="{PATH0}"')
        PATH0 = shell.get_env_var("PATH", "")
    shell.sendline("type conda")
    shell.expect(conda_is_a_function)

    _CE_M = shell.get_env_var("_CE_M")
    _CE_CONDA = shell.get_env_var("_CE_CONDA")

    shell.sendline("conda --version")
    shell.expect_exact("conda " + conda_version)

    shell.sendline(f"conda {ACTIVATE_ARGS} base")

    shell.sendline("type conda")
    shell.expect(conda_is_a_function)

    CONDA_EXE2 = case(shell.get_env_var("CONDA_EXE"))
    _CE_M2 = shell.get_env_var("_CE_M")

    shell.assert_env_var("PS1", "(base).*")
    shell.assert_env_var("CONDA_SHLVL", "1")
    PATH1 = shell.get_env_var("PATH", "")
    assert len(PATH0.split(":")) + num_paths_added == len(PATH1.split(":"))

    CONDA_EXE = case(shell.get_env_var("CONDA_EXE"))
    _CE_M = shell.get_env_var("_CE_M")
    _CE_CONDA = shell.get_env_var("_CE_CONDA")

    log.debug("activating ..")
    shell.sendline(f'conda {ACTIVATE_ARGS} "{prefix_p}"')

    shell.sendline("type conda")
    shell.expect(conda_is_a_function)

    CONDA_EXE2 = case(shell.get_env_var("CONDA_EXE"))
    _CE_M2 = shell.get_env_var("_CE_M")
    _CE_CONDA2 = shell.get_env_var("_CE_CONDA")
    assert CONDA_EXE == CONDA_EXE2
    assert _CE_M == _CE_M2
    assert _CE_CONDA == _CE_CONDA2

    shell.sendline("env | sort")
    # When CONDA_SHLVL==2 fails it usually means that conda activate failed. We that fails it is
    # usually because you forgot to pass `--dev` to the *previous* activate so CONDA_EXE changed
    # from python to conda, which is then found on PATH instead of using the dev sources. When it
    # goes to use this old conda to generate the activation script for the newly activated env.
    # it is running the old code (or at best, a mix of new code and old scripts).
    shell.assert_env_var("CONDA_SHLVL", "2")
    CONDA_PREFIX = shell.get_env_var("CONDA_PREFIX", "")
    # We get C: vs c: differences on Windows.
    # Also, self.prefix instead of prefix_p is deliberate (maybe unfortunate?)
    assert CONDA_PREFIX.lower() == prefix.lower()
    PATH2 = shell.get_env_var("PATH", "")
    assert len(PATH0.split(":")) + num_paths_added == len(PATH2.split(":"))

    shell.sendline("env | sort | grep CONDA")
    shell.expect("CONDA_")
    shell.sendline('echo "PATH=$PATH"')
    shell.expect("PATH=")
    shell.sendline(f'conda {ACTIVATE_ARGS} "{prefix2_p}"')
    shell.sendline("env | sort | grep CONDA")
    shell.expect("CONDA_")
    shell.sendline('echo "PATH=$PATH"')
    shell.expect("PATH=")
    shell.assert_env_var("PS1", "(charizard).*")
    shell.assert_env_var("CONDA_SHLVL", "3")
    PATH3 = shell.get_env_var("PATH")
    assert len(PATH0.split(":")) + num_paths_added == len(PATH3.split(":"))

    CONDA_EXE2 = case(shell.get_env_var("CONDA_EXE"))
    _CE_M2 = shell.get_env_var("_CE_M")
    _CE_CONDA2 = shell.get_env_var("_CE_CONDA")
    assert CONDA_EXE == CONDA_EXE2
    assert _CE_M == _CE_M2
    assert _CE_CONDA == _CE_CONDA2

    shell.sendline(f"conda {INSTALL_ARGS} -yq hdf5={HDF5_VERSION}")
    shell.expect(r"Executing transaction: ...working... done.*\n", timeout=180)
    shell.assert_env_var("?", "0", use_exact=True)

    shell.sendline("h5stat --version")
    shell.expect(rf".*h5stat: Version {HDF5_VERSION}.*")

    # TODO: assert that reactivate worked correctly

    shell.sendline("type conda")
    shell.expect(conda_is_a_function)

    shell.sendline(f"conda run {DEV_ARG} h5stat --version")
    shell.expect(rf".*h5stat: Version {HDF5_VERSION}.*")

    # regression test for #6840
    shell.sendline(f"conda {INSTALL_ARGS} --blah")
    shell.assert_env_var("?", "2", use_exact=True)
    shell.sendline("conda list --blah")
    shell.assert_env_var("?", "2", use_exact=True)

    shell.sendline(f"conda {DEACTIVATE_ARGS}")
    shell.assert_env_var("CONDA_SHLVL", "2")
    PATH = shell.get_env_var("PATH")
    assert len(PATH0.split(":")) + num_paths_added == len(PATH.split(":"))

    shell.sendline(f"conda {DEACTIVATE_ARGS}")
    shell.assert_env_var("CONDA_SHLVL", "1")
    PATH = shell.get_env_var("PATH")
    assert len(PATH0.split(":")) + num_paths_added == len(PATH.split(":"))

    shell.sendline(f"conda {DEACTIVATE_ARGS}")
    shell.assert_env_var("CONDA_SHLVL", "0")
    PATH = shell.get_env_var("PATH")
    assert len(PATH0.split(":")) == len(PATH.split(":"))
    # assert PATH0 == PATH  # cygpath may "resolve" paths

    shell.sendline(shell.print_env_var % "PS1")
    shell.clear()
    assert "CONDA_PROMPT_MODIFIER" not in str(shell.p.after)

    shell.sendline(f"conda {DEACTIVATE_ARGS}")
    shell.assert_env_var("CONDA_SHLVL", "0")

    # When fully deactivated, CONDA_EXE, _CE_M and _CE_CONDA must be retained
    # because the conda shell scripts use them and if they are unset activation
    # is not possible.
    CONDA_EXED = case(shell.get_env_var("CONDA_EXE"))
    assert CONDA_EXED, (
        "A fully deactivated conda shell must retain CONDA_EXE (and _CE_M and _CE_CONDA in dev)\n"
        "  as the shell scripts refer to them."
    )

    PATH0 = shell.get_env_var("PATH")

    shell.sendline(f'conda {ACTIVATE_ARGS} "{prefix2_p}"')
    shell.assert_env_var("CONDA_SHLVL", "1")
    PATH1 = shell.get_env_var("PATH")
    assert len(PATH0.split(":")) + num_paths_added == len(PATH1.split(":"))

    shell.sendline(f'conda {ACTIVATE_ARGS} "{prefix3}" --stack')
    shell.assert_env_var("CONDA_SHLVL", "2")
    PATH2 = shell.get_env_var("PATH")
    assert "charizard" in PATH2
    assert "venusaur" in PATH2
    assert len(PATH0.split(":")) + num_paths_added * 2 == len(PATH2.split(":"))

    shell.sendline(f'conda {ACTIVATE_ARGS} "{prefix_p}"')
    shell.assert_env_var("CONDA_SHLVL", "3")
    PATH3 = shell.get_env_var("PATH")
    assert "charizard" in PATH3
    assert "venusaur" not in PATH3
    assert len(PATH0.split(":")) + num_paths_added * 2 == len(PATH3.split(":"))

    shell.sendline(f"conda {DEACTIVATE_ARGS}")
    shell.assert_env_var("CONDA_SHLVL", "2")
    PATH4 = shell.get_env_var("PATH")
    assert "charizard" in PATH4
    assert "venusaur" in PATH4
    assert len(PATH4.split(":")) == len(PATH2.split(":"))
    # assert PATH4 == PATH2  # cygpath may "resolve" paths

    shell.sendline(f"conda {DEACTIVATE_ARGS}")
    shell.assert_env_var("CONDA_SHLVL", "1")
    PATH5 = shell.get_env_var("PATH")
    assert len(PATH1.split(":")) == len(PATH5.split(":"))
    # assert PATH1 == PATH5  # cygpath may "resolve" paths

    # Test auto_stack
    shell.sendline(shell.activator.export_var_tmpl % ("CONDA_AUTO_STACK", "1"))

    shell.sendline(f'conda {ACTIVATE_ARGS} "{prefix3}"')
    shell.assert_env_var("CONDA_SHLVL", "2")
    PATH2 = shell.get_env_var("PATH")
    assert "charizard" in PATH2
    assert "venusaur" in PATH2
    assert len(PATH0.split(":")) + num_paths_added * 2 == len(PATH2.split(":"))

    shell.sendline(f'conda {ACTIVATE_ARGS} "{prefix_p}"')
    shell.assert_env_var("CONDA_SHLVL", "3")
    PATH3 = shell.get_env_var("PATH")
    assert "charizard" in PATH3
    assert "venusaur" not in PATH3
    assert len(PATH0.split(":")) + num_paths_added * 2 == len(PATH3.split(":"))


def basic_csh(shell, prefix, prefix2, prefix3):
    shell.sendline("conda --version")
    shell.expect_exact("conda " + conda_version)
    shell.assert_env_var("CONDA_SHLVL", "0")
    shell.sendline("conda activate base")
    shell.assert_env_var("prompt", "(base).*")
    shell.assert_env_var("CONDA_SHLVL", "1")
    shell.sendline(f'conda activate "{prefix}"')
    shell.assert_env_var("CONDA_SHLVL", "2")
    shell.assert_env_var("CONDA_PREFIX", prefix, True)
    shell.sendline("conda deactivate")
    shell.assert_env_var("CONDA_SHLVL", "1")
    shell.sendline("conda deactivate")
    shell.assert_env_var("CONDA_SHLVL", "0")

    assert "CONDA_PROMPT_MODIFIER" not in str(shell.p.after)

    shell.sendline("conda deactivate")
    shell.assert_env_var("CONDA_SHLVL", "0")


@pytest.mark.parametrize(
    "shell_name,script",
    [
        pytest.param(
            "bash",
            basic_posix,
            marks=[
                skip_unsupported_bash,
                pytest.mark.skipif(
                    on_win, reason="Temporary skip, larger refactor necessary"
                ),
            ],
        ),
        pytest.param(
            "dash",
            basic_posix,
            marks=[
                pytest.mark.skipif(
                    not which("dash") or on_win, reason="dash not installed"
                )
            ],
        ),
        pytest.param(
            "zsh",
            basic_posix,
            marks=[pytest.mark.skipif(not which("zsh"), reason="zsh not installed")],
        ),
        pytest.param(
            "csh",
            basic_csh,
            marks=[
                pytest.mark.skipif(not which("csh"), reason="csh not installed"),
                pytest.mark.xfail(
                    reason="pure csh doesn't support argument passing to sourced scripts"
                ),
            ],
        ),
        pytest.param(
            "tcsh",
            basic_csh,
            marks=[
                pytest.mark.skipif(not which("tcsh"), reason="tcsh not installed"),
                pytest.mark.xfail(
                    reason="punting until we officially enable support for tcsh"
                ),
            ],
        ),
    ],
)
def test_basic_integration(
    shell_wrapper_integration: tuple[str, str, str],
    shell_name: str,
    script: Callable[[InteractiveShell, str, str, str], None],
):
    with InteractiveShell(shell_name) as shell:
        script(shell, *shell_wrapper_integration)


@pytest.mark.skipif(not which("fish"), reason="fish not installed")
@pytest.mark.xfail(reason="fish and pexpect don't seem to work together?")
def test_fish_basic_integration(shell_wrapper_integration: tuple[str, str, str]):
    prefix, _, _ = shell_wrapper_integration

    with InteractiveShell("fish") as shell:
        shell.sendline("env | sort")
        # We should be seeing environment variable output to terminal with this line, but
        # we aren't.  Haven't experienced this problem yet with any other shell...

        shell.assert_env_var("CONDA_SHLVL", "0")
        shell.sendline("conda activate base")
        shell.assert_env_var("CONDA_SHLVL", "1")
        shell.sendline(f'conda activate "{prefix}"')
        shell.assert_env_var("CONDA_SHLVL", "2")
        shell.assert_env_var("CONDA_PREFIX", prefix, True)
        shell.sendline("conda deactivate")
        shell.assert_env_var("CONDA_SHLVL", "1")
        shell.sendline("conda deactivate")
        shell.assert_env_var("CONDA_SHLVL", "0")

        shell.sendline(shell.print_env_var % "PS1")
        shell.clear()
        assert "CONDA_PROMPT_MODIFIER" not in str(shell.p.after)

        shell.sendline("conda deactivate")
        shell.assert_env_var("CONDA_SHLVL", "0")


@pytest.mark.skipif(
    not which_powershell() or platform.machine() == "arm64",
    reason="PowerShell not installed or not supported on platform",
)
def test_powershell_basic_integration(shell_wrapper_integration: tuple[str, str, str]):
    prefix, charizard, venusaur = shell_wrapper_integration

    posh_kind, posh_path = which_powershell()
    log.debug(f"## [PowerShell integration] Using {posh_path}.")
    with InteractiveShell(posh_kind) as shell:
        log.debug("## [PowerShell integration] Starting test.")
        shell.sendline("(Get-Command conda).CommandType")
        shell.expect_exact("Alias")
        shell.sendline("(Get-Command conda).Definition")
        shell.expect_exact("Invoke-Conda")
        shell.sendline("(Get-Command Invoke-Conda).Definition")

        log.debug("## [PowerShell integration] Activating.")
        shell.sendline(f'conda activate "{charizard}"')
        shell.assert_env_var("CONDA_SHLVL", "1")
        PATH = shell.get_env_var("PATH")
        assert "charizard" in PATH
        shell.sendline("conda --version")
        shell.expect_exact("conda " + conda_version)
        shell.sendline(f'conda activate "{prefix}"')
        shell.assert_env_var("CONDA_SHLVL", "2")
        shell.assert_env_var("CONDA_PREFIX", prefix, True)

        shell.sendline("conda deactivate")
        PATH = shell.get_env_var("PATH")
        assert "charizard" in PATH
        shell.sendline(f'conda activate -stack "{venusaur}"')
        PATH = shell.get_env_var("PATH")
        assert "venusaur" in PATH
        assert "charizard" in PATH

        log.debug("## [PowerShell integration] Installing.")
        shell.sendline(f"conda install -yq hdf5={HDF5_VERSION}")
        shell.expect(r"Executing transaction: ...working... done.*\n", timeout=100)
        shell.sendline("$LASTEXITCODE")
        shell.expect("0")
        # TODO: assert that reactivate worked correctly

        log.debug("## [PowerShell integration] Checking installed version.")
        shell.sendline("h5stat --version")
        shell.expect(rf".*h5stat: Version {HDF5_VERSION}.*")

        # conda run integration test
        log.debug("## [PowerShell integration] Checking conda run.")
        shell.sendline(f"conda run {DEV_ARG} h5stat --version")
        shell.expect(rf".*h5stat: Version {HDF5_VERSION}.*")

        log.debug("## [PowerShell integration] Deactivating")
        shell.sendline("conda deactivate")
        shell.assert_env_var("CONDA_SHLVL", "1")
        shell.sendline("conda deactivate")
        shell.assert_env_var("CONDA_SHLVL", "0")
        shell.sendline("conda deactivate")
        shell.assert_env_var("CONDA_SHLVL", "0")


@pytest.mark.skipif(
    not which_powershell() or not on_win, reason="Windows, PowerShell specific test"
)
def test_powershell_PATH_management(shell_wrapper_integration: tuple[str, str, str]):
    prefix, _, _ = shell_wrapper_integration

    posh_kind, posh_path = which_powershell()
    print(f"## [PowerShell activation PATH management] Using {posh_path}.")
    with InteractiveShell(posh_kind) as shell:
        prefix = join(prefix, "envs", "test")
        print("## [PowerShell activation PATH management] Starting test.")
        shell.sendline("(Get-Command conda).CommandType")
        shell.expect_exact("Alias")
        shell.sendline("(Get-Command conda).Definition")
        shell.expect_exact("Invoke-Conda")
        shell.sendline("(Get-Command Invoke-Conda).Definition")
        shell.clear()

        shell.sendline("conda deactivate")
        shell.sendline("conda deactivate")

        PATH0 = shell.get_env_var("PATH", "")
        print(f"PATH is {PATH0.split(os.pathsep)}")
        shell.sendline("(Get-Command conda).CommandType")
        shell.expect_exact("Alias")
        shell.sendline(f'conda create -yqp "{prefix}" bzip2')
        shell.expect(r"Executing transaction: ...working... done.*\n")


@pytest.mark.skipif(not which("cmd.exe"), reason="cmd.exe not installed")
def test_cmd_exe_basic_integration(shell_wrapper_integration: tuple[str, str, str]):
    prefix, charizard, _ = shell_wrapper_integration
    conda_bat = str(Path(CONDA_PACKAGE_ROOT, "shell", "condabin", "conda.bat"))

    with InteractiveShell("cmd.exe") as shell:
        shell.assert_env_var("_CE_CONDA", "conda")
        shell.assert_env_var("_CE_M", "-m")
        shell.assert_env_var("CONDA_EXE", escape(sys.executable))

        # We use 'PowerShell' here because 'where conda' returns all of them and
        # shell.expect_exact does not do what you would think it does given its name.
        shell.sendline('powershell -NoProfile -c "(Get-Command conda).Source"')
        shell.expect_exact(conda_bat)

        shell.sendline("chcp")
        shell.clear()

        PATH0 = shell.get_env_var("PATH", "").split(os.pathsep)
        log.debug(f"{PATH0=}")
        shell.sendline(f'conda {ACTIVATE_ARGS} "{charizard}"')

        shell.sendline("chcp")
        shell.clear()
        shell.assert_env_var("CONDA_SHLVL", "1")

        PATH1 = shell.get_env_var("PATH", "").split(os.pathsep)
        log.debug(f"{PATH1=}")
        shell.sendline('powershell -NoProfile -c "(Get-Command conda).Source"')
        shell.expect_exact(conda_bat)

        shell.assert_env_var("_CE_CONDA", "conda")
        shell.assert_env_var("_CE_M", "-m")
        shell.assert_env_var("CONDA_EXE", escape(sys.executable))
        shell.assert_env_var("CONDA_PREFIX", charizard, True)
        PATH2 = shell.get_env_var("PATH", "").split(os.pathsep)
        log.debug(f"{PATH2=}")

        shell.sendline('powershell -NoProfile -c "(Get-Command conda -All).Source"')
        shell.expect_exact(conda_bat)

        shell.sendline(f'conda {ACTIVATE_ARGS} "{prefix}"')
        shell.assert_env_var("_CE_CONDA", "conda")
        shell.assert_env_var("_CE_M", "-m")
        shell.assert_env_var("CONDA_EXE", escape(sys.executable))
        shell.assert_env_var("CONDA_SHLVL", "2")
        shell.assert_env_var("CONDA_PREFIX", prefix, True)

        # TODO: Make a dummy package and release it (somewhere?)
        #       should be a relatively light package, but also
        #       one that has activate.d or deactivate.d scripts.
        #       More imporant than size or script though, it must
        #       not require an old or incompatible version of any
        #       library critical to the correct functioning of
        #       Python (e.g. OpenSSL).
        shell.sendline(f"conda install --yes --quiet hdf5={HDF5_VERSION}")
        shell.expect(r"Executing transaction: ...working... done.*\n", timeout=100)
        shell.assert_env_var("errorlevel", "0", True)
        # TODO: assert that reactivate worked correctly

        shell.sendline("h5stat --version")
        shell.expect(rf".*h5stat: Version {HDF5_VERSION}.*")

        # conda run integration test
        shell.sendline(f"conda run {DEV_ARG} h5stat --version")
        shell.expect(rf".*h5stat: Version {HDF5_VERSION}.*")

        shell.sendline(f"conda {DEACTIVATE_ARGS}")
        shell.assert_env_var("CONDA_SHLVL", "1")
        shell.sendline(f"conda {DEACTIVATE_ARGS}")
        shell.assert_env_var("CONDA_SHLVL", "0")
        shell.sendline(f"conda {DEACTIVATE_ARGS}")
        shell.assert_env_var("CONDA_SHLVL", "0")


@skip_unsupported_bash
@pytest.mark.skipif(on_win, reason="Temporary skip, larger refactor necessary")
def test_bash_activate_error(shell_wrapper_integration: tuple[str, str, str]):
    context.dev = True
    with InteractiveShell("bash") as shell:
        shell.sendline("export CONDA_SHLVL=unaffected")
        if on_win:
            shell.sendline("uname -o")
            shell.expect("(Msys|Cygwin)")
        shell.sendline("conda activate environment-not-found-doesnt-exist")
        shell.expect(
            "Could not find conda environment: environment-not-found-doesnt-exist"
        )
        shell.assert_env_var("CONDA_SHLVL", "unaffected")

        shell.sendline("conda activate -h blah blah")
        shell.expect("usage: conda activate")


@pytest.mark.skipif(not which("cmd.exe"), reason="cmd.exe not installed")
def test_cmd_exe_activate_error(shell_wrapper_integration: tuple[str, str, str]):
    context.dev = True
    with InteractiveShell("cmd.exe") as shell:
        shell.sendline("set")
        shell.expect(".*")
        shell.sendline(f"conda {ACTIVATE_ARGS} environment-not-found-doesnt-exist")
        shell.expect(
            "Could not find conda environment: environment-not-found-doesnt-exist"
        )
        shell.expect(".*")
        shell.assert_env_var("errorlevel", "1")

        shell.sendline("conda activate -h blah blah")
        shell.expect("usage: conda activate")


@skip_unsupported_bash
def test_legacy_activate_deactivate_bash(
    shell_wrapper_integration: tuple[str, str, str],
):
    prefix, prefix2, prefix3 = shell_wrapper_integration

    with InteractiveShell("bash") as shell:
        CONDA_PACKAGE_ROOT_p = shell.path_conversion(CONDA_PACKAGE_ROOT)
        prefix2_p = shell.path_conversion(prefix2)
        prefix3_p = shell.path_conversion(prefix3)
        shell.sendline(f"export _CONDA_ROOT='{CONDA_PACKAGE_ROOT_p}/shell'")
        shell.sendline(
            f'source "${{_CONDA_ROOT}}/bin/activate" {DEV_ARG} "{prefix2_p}"'
        )
        PATH0 = shell.get_env_var("PATH")
        assert "charizard" in PATH0

        shell.sendline("type conda")
        shell.expect("conda is a function")

        shell.sendline("conda --version")
        shell.expect_exact("conda " + conda_version)

        shell.sendline(
            f'source "${{_CONDA_ROOT}}/bin/activate" {DEV_ARG} "{prefix3_p}"'
        )

        PATH1 = shell.get_env_var("PATH")
        assert "venusaur" in PATH1

        shell.sendline('source "${_CONDA_ROOT}/bin/deactivate"')
        PATH2 = shell.get_env_var("PATH")
        assert "charizard" in PATH2

        shell.sendline('source "${_CONDA_ROOT}/bin/deactivate"')
        shell.assert_env_var("CONDA_SHLVL", "0")


@pytest.mark.skipif(not which("cmd.exe"), reason="cmd.exe not installed")
def test_legacy_activate_deactivate_cmd_exe(
    shell_wrapper_integration: tuple[str, str, str],
):
    prefix, prefix2, prefix3 = shell_wrapper_integration

    with InteractiveShell("cmd.exe") as shell:
        shell.sendline("echo off")

        conda__ce_conda = shell.get_env_var("_CE_CONDA")
        assert conda__ce_conda == "conda"

        PATH = f"{CONDA_PACKAGE_ROOT}\\shell\\Scripts;%PATH%"

        shell.sendline("SET PATH=" + PATH)

        shell.sendline(f'activate --dev "{prefix2}"')
        shell.clear()

        conda_shlvl = shell.get_env_var("CONDA_SHLVL")
        assert conda_shlvl == "1", conda_shlvl

        PATH = shell.get_env_var("PATH")
        assert "charizard" in PATH

        conda__ce_conda = shell.get_env_var("_CE_CONDA")
        assert conda__ce_conda == "conda"

        shell.sendline("conda --version")
        shell.expect_exact("conda " + conda_version)

        shell.sendline(f'activate.bat --dev "{prefix3}"')
        PATH = shell.get_env_var("PATH")
        assert "venusaur" in PATH

        shell.sendline("deactivate.bat --dev")
        PATH = shell.get_env_var("PATH")
        assert "charizard" in PATH

        shell.sendline("deactivate --dev")
        conda_shlvl = shell.get_env_var("CONDA_SHLVL")
        assert conda_shlvl == "0", conda_shlvl


@pytest.fixture(scope="module")
def prefix(tmp_path_factory: TempPathFactory) -> Iterator[Path]:
    name = f"{uuid4().hex[:4]}{SPACER_CHARACTER}{uuid4().hex[:4]}"
    root = tmp_path_factory.mktemp(name)

    (root / "conda-meta").mkdir(parents=True)
    (root / "conda-meta" / "history").touch()

    prefix = root / "envs" / "charizard"

    (prefix / "conda-meta").mkdir(parents=True)
    (prefix / "conda-meta" / "history").touch()

    yield prefix


@pytest.mark.parametrize(
    ["shell"],
    [
        pytest.param(
            "bash",
            marks=skip_unsupported_bash,
        ),
        pytest.param(
            "cmd.exe",
            marks=pytest.mark.skipif(
                not which("cmd.exe"), reason="cmd.exe not installed"
            ),
        ),
    ],
)
def test_activate_deactivate_modify_path(
    test_recipes_channel: Path,
    shell,
    prefix,
    conda_cli: CondaCLIFixture,
):
    original_path = os.environ.get("PATH")
    conda_cli(
        "install",
        *("--prefix", prefix),
        "activate_deactivate_package",
        "--yes",
    )

    with InteractiveShell(shell) as sh:
        sh.sendline(f'conda activate "{prefix}"')
        activated_env_path = sh.get_env_var("PATH")
        sh.sendline("conda deactivate")

    assert "teststringfromactivate/bin/test" in activated_env_path
    assert original_path == os.environ.get("PATH")


@pytest.fixture
def create_stackable_envs(
    tmp_env: TmpEnvFixture,
) -> Iterator[tuple[str, dict[str, Any]]]:
    # generate stackable environments, two with curl and one without curl
    which = f"{'where' if on_win else 'which -a'} curl"

    class Env:
        def __init__(self, prefix=None, paths=None):
            self.prefix = Path(prefix) if prefix else None

            if not paths:
                if on_win:
                    path = self.prefix / "Library" / "bin" / "curl.exe"
                else:
                    path = self.prefix / "bin" / "curl"

                paths = (path,) if path.exists() else ()
            self.paths = paths

    sys = _run_command(
        "conda config --set auto_activate_base false",
        which,
    )

    with tmp_env("curl") as base, tmp_env("curl") as haspkg, tmp_env() as notpkg:
        yield (
            which,
            {
                "sys": Env(paths=sys),
                "base": Env(prefix=base),
                "has": Env(prefix=haspkg),
                "not": Env(prefix=notpkg),
            },
        )


def _run_command(*lines):
    # create a custom run command since this is specific to the shell integration
    if on_win:
        join = " && ".join
        source = f"{Path(context.root_prefix, 'condabin', 'conda_hook.bat')}"
    else:
        join = "\n".join
        source = f". {Path(context.root_prefix, 'etc', 'profile.d', 'conda.sh')}"

    marker = uuid4().hex
    script = join((source, *(["conda deactivate"] * 5), f"echo {marker}", *lines))
    output = check_output(script, shell=True).decode().splitlines()
    output = list(map(str.strip, output))
    output = output[output.index(marker) + 1 :]  # trim setup output

    return [Path(path) for path in filter(None, output)]


# see https://github.com/conda/conda/pull/11257#issuecomment-1050531320
@pytest.mark.parametrize(
    ("auto_stack", "stack", "run", "expected"),
    [
        # no environments activated
        (0, "", "base", "base,sys"),
        (0, "", "has", "has,sys"),
        (0, "", "not", "sys"),
        # one environment activated, no stacking
        (0, "base", "base", "base,sys"),
        (0, "base", "has", "has,sys"),
        (0, "base", "not", "sys"),
        (0, "has", "base", "base,sys"),
        (0, "has", "has", "has,sys"),
        (0, "has", "not", "sys"),
        (0, "not", "base", "base,sys"),
        (0, "not", "has", "has,sys"),
        (0, "not", "not", "sys"),
        # one environment activated, stacking allowed
        (5, "base", "base", "base,sys"),
        (5, "base", "has", "has,base,sys"),
        (5, "base", "not", "base,sys"),
        (5, "has", "base", "base,has,sys"),
        (5, "has", "has", "has,sys"),
        (5, "has", "not", "has,sys"),
        (5, "not", "base", "base,sys"),
        (5, "not", "has", "has,sys"),
        (5, "not", "not", "sys"),
        # two environments activated, stacking allowed
        (5, "base,has", "base", "base,has,sys" if on_win else "base,has,base,sys"),
        (5, "base,has", "has", "has,base,sys"),
        (5, "base,has", "not", "has,base,sys"),
        (5, "base,not", "base", "base,sys" if on_win else "base,base,sys"),
        (5, "base,not", "has", "has,base,sys"),
        (5, "base,not", "not", "base,sys"),
    ],
)
def test_stacking(
    create_stackable_envs: tuple[str, dict[str, Any]],
    auto_stack: int,
    stack: str,
    run: str,
    expected: str,
) -> None:
    which, envs = create_stackable_envs
    assert _run_command(
        f"conda config --set auto_stack {auto_stack}",
        *(
            f'conda activate "{envs[env.strip()].prefix}"'
            for env in filter(None, stack.split(","))
        ),
        f'conda run -p "{envs[run.strip()].prefix}" {which}',
    ) == [
        path
        for env in filter(None, expected.split(","))
        for path in envs[env.strip()].paths
    ]
