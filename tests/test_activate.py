# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import json
import os
import re
import sys
from contextlib import nullcontext
from itertools import chain
from logging import getLogger
from os.path import join
from pathlib import Path
from subprocess import check_output
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from conda import CondaError, activate
from conda.activate import (
    CmdExeActivator,
    CshActivator,
    FishActivator,
    PosixActivator,
    PowerShellActivator,
    XonshActivator,
    _build_activator_cls,
    native_path_to_unix,
    unix_path_to_native,
)
from conda.auxlib.ish import dals
from conda.base.constants import (
    CONDA_ENV_VARS_UNSET_VAR,
    PACKAGE_ENV_VARS_DIR,
    PREFIX_STATE_FILE,
    ROOT_ENV_NAME,
)
from conda.base.context import context, reset_context
from conda.cli.main import main_sourced
from conda.common.compat import on_win
from conda.exceptions import EnvironmentLocationNotFound, EnvironmentNameNotFound
from conda.gateways.disk.create import mkdir_p
from conda.gateways.disk.delete import rm_rf
from conda.gateways.disk.update import touch
from conda.testing.helpers import tempdir

if TYPE_CHECKING:
    from typing import Iterable

    from pytest import CaptureFixture, MonkeyPatch
    from pytest_mock import MockerFixture

    from conda.activate import _Activator
    from conda.testing import PathFactoryFixture, TmpEnvFixture


log = getLogger(__name__)

dev_arg = "--dev"
activate_args = ["activate", dev_arg]
reactivate_args = ["reactivate", dev_arg]
deactivate_args = ["deactivate", dev_arg]

# a unique prompt (makes it easy to know that our values are showing up correctly)
DEFAULT_PROMPT = " >>(testing)>> "

# a unique context.env_prompt (makes it easy to know that our values are showing up correctly)
DEFAULT_ENV_PROMPT = "-- ==({default_env})== --"

# unique environment variables to set via packages and state files
PKG_A_ENV = "pkg_a-" + uuid4().hex
PKG_B_ENV = "pkg_b-" + uuid4().hex
ENV_ONE = "one-" + uuid4().hex
ENV_TWO = "two-" + uuid4().hex
ENV_THREE = "three-" + uuid4().hex
ENV_WITH_SAME_VALUE = "with_same_value-" + uuid4().hex
ENV_FOUR = "four-" + uuid4().hex
ENV_FIVE = "five-" + uuid4().hex


skip_unsupported_posix_path = pytest.mark.skipif(
    on_win,
    reason=(
        "You are using Windows. These tests involve setting PATH to POSIX values\n"
        "but our Python is a Windows program and Windows doesn't understand POSIX values."
    ),
)


def get_prompt_modifier(default_env: str | os.PathLike | Path) -> str:
    return DEFAULT_ENV_PROMPT.format(default_env=default_env)


def get_prompt(default_env: str | os.PathLike | Path | None = None) -> str:
    if not default_env:
        return DEFAULT_PROMPT
    return get_prompt_modifier(default_env) + DEFAULT_PROMPT


@pytest.fixture(autouse=True)
def reset_environ(monkeypatch: MonkeyPatch) -> None:
    for name in (
        "CONDA_SHLVL",
        "CONDA_DEFAULT_ENV",
        "CONDA_PREFIX",
        "CONDA_PREFIX_0",
        "CONDA_PREFIX_1",
        "CONDA_PREFIX_2",
    ):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("PS1", DEFAULT_PROMPT)
    monkeypatch.setenv("prompt", DEFAULT_PROMPT)

    monkeypatch.setenv("CONDA_CHANGEPS1", "true")
    monkeypatch.setenv("CONDA_ENV_PROMPT", DEFAULT_ENV_PROMPT)
    reset_context()
    assert context.changeps1


def write_pkg_A(prefix: str | os.PathLike | Path) -> None:
    activate_pkg_env_vars = Path(prefix, PACKAGE_ENV_VARS_DIR)
    activate_pkg_env_vars.mkdir(exist_ok=True)
    (activate_pkg_env_vars / "pkg_a.json").write_text(
        json.dumps({"PKG_A_ENV": PKG_A_ENV})
    )


def write_pkg_B(prefix: str | os.PathLike | Path) -> None:
    activate_pkg_env_vars = Path(prefix, PACKAGE_ENV_VARS_DIR)
    activate_pkg_env_vars.mkdir(exist_ok=True)
    (activate_pkg_env_vars / "pkg_b.json").write_text(
        json.dumps({"PKG_B_ENV": PKG_B_ENV})
    )


def write_pkgs(prefix: str | os.PathLike | Path) -> None:
    write_pkg_A(prefix)
    write_pkg_B(prefix)


def write_state_file(
    prefix: str | os.PathLike | Path,
    **envvars,
) -> None:
    Path(prefix, PREFIX_STATE_FILE).write_text(
        json.dumps(
            {
                "version": 1,
                "env_vars": (
                    envvars
                    or {
                        "ENV_ONE": ENV_ONE,
                        "ENV_TWO": ENV_TWO,
                        "ENV_THREE": ENV_THREE,
                        "ENV_WITH_SAME_VALUE": ENV_WITH_SAME_VALUE,
                    }
                ),
            }
        )
    )


@pytest.fixture
def env_activate(tmp_env: TmpEnvFixture) -> tuple[str, str, str]:
    with tmp_env() as prefix:
        activate_d = prefix / "etc" / "conda" / "activate.d"
        activate_d.mkdir(parents=True)

        activate_sh = activate_d / "activate.sh"
        activate_sh.touch()

        activate_bat = activate_d / "activate.bat"
        activate_bat.touch()

        return str(prefix), str(activate_sh), str(activate_bat)


@pytest.fixture
def env_activate_deactivate(tmp_env: TmpEnvFixture) -> tuple[str, str, str, str, str]:
    with tmp_env() as prefix:
        activate_d = prefix / "etc" / "conda" / "activate.d"
        activate_d.mkdir(parents=True)

        activate_sh = activate_d / "activate.sh"
        activate_sh.touch()

        activate_bat = activate_d / "activate.bat"
        activate_bat.touch()

        deactivate_d = prefix / "etc" / "conda" / "deactivate.d"
        deactivate_d.mkdir(parents=True)

        deactivate_sh = deactivate_d / "deactivate.sh"
        deactivate_sh.touch()

        deactivate_bat = deactivate_d / "deactivate.bat"
        deactivate_bat.touch()

        return (
            str(prefix),
            str(activate_sh),
            str(activate_bat),
            str(deactivate_sh),
            str(deactivate_bat),
        )


@pytest.fixture
def env_deactivate(tmp_env: TmpEnvFixture) -> tuple[str, str, str]:
    with tmp_env() as prefix:
        deactivate_d = prefix / "etc" / "conda" / "deactivate.d"
        deactivate_d.mkdir(parents=True)

        deactivate_sh = deactivate_d / "deactivate.sh"
        deactivate_sh.touch()

        deactivate_bat = deactivate_d / "deactivate.bat"
        deactivate_bat.touch()

        return str(prefix), str(deactivate_sh), str(deactivate_bat)


def get_scripts_export_unset_vars(
    activator: _Activator,
    **kwargs: str,
) -> tuple[str, str]:
    export_vars, unset_vars = activator.get_export_unset_vars(**kwargs)
    return (
        activator.command_join.join(
            activator.export_var_tmpl % (k, v) for k, v in (export_vars or {}).items()
        ),
        activator.command_join.join(
            activator.unset_var_tmpl % (k) for k in (unset_vars or [])
        ),
    )


def test_activate_environment_not_found(reset_environ: None):
    activator = PosixActivator()

    with tempdir() as td:
        with pytest.raises(EnvironmentLocationNotFound):
            activator.build_activate(td)

    with pytest.raises(EnvironmentLocationNotFound):
        activator.build_activate("/not/an/environment")

    with pytest.raises(EnvironmentNameNotFound):
        activator.build_activate("wontfindmeIdontexist_abc123")


def test_PS1(tmp_path: Path):
    conda_prompt_modifier = get_prompt_modifier(ROOT_ENV_NAME)
    activator = PosixActivator()
    assert activator._prompt_modifier(tmp_path, ROOT_ENV_NAME) == conda_prompt_modifier

    instructions = activator.build_activate("base")
    assert instructions["export_vars"]["CONDA_PROMPT_MODIFIER"] == conda_prompt_modifier


def test_PS1_no_changeps1(monkeypatch: MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("CONDA_CHANGEPS1", "false")
    reset_context()
    assert not context.changeps1

    activator = PosixActivator()
    assert activator._prompt_modifier(tmp_path, "root") == ""

    instructions = activator.build_activate("base")
    assert instructions["export_vars"]["CONDA_PROMPT_MODIFIER"] == ""


def test_add_prefix_to_path_posix():
    if on_win and "PWD" not in os.environ:
        pytest.skip("This test cannot be run from the cmd.exe shell.")

    activator = PosixActivator()

    path_dirs = activator.path_conversion(
        ["/path1/bin", "/path2/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    )
    assert len(path_dirs) == 5
    test_prefix = "/usr/mytest/prefix"
    added_paths = activator.path_conversion(activator._get_path_dirs(test_prefix))
    if isinstance(added_paths, str):
        added_paths = (added_paths,)

    new_path = activator._add_prefix_to_path(test_prefix, path_dirs)
    condabin_dir = activator.path_conversion(
        os.path.join(context.conda_prefix, "condabin")
    )
    assert new_path == added_paths + (condabin_dir,) + path_dirs


@pytest.mark.skipif(not on_win, reason="windows-specific test")
def test_add_prefix_to_path_cmdexe():
    activator = CmdExeActivator()

    path_dirs = activator.path_conversion(
        ["C:\\path1", "C:\\Program Files\\Git\\cmd", "C:\\WINDOWS\\system32"]
    )
    assert len(path_dirs) == 3
    test_prefix = "/usr/mytest/prefix"
    added_paths = activator.path_conversion(activator._get_path_dirs(test_prefix))
    if isinstance(added_paths, str):
        added_paths = (added_paths,)

    new_path = activator._add_prefix_to_path(test_prefix, path_dirs)
    assert new_path[: len(added_paths)] == added_paths
    assert new_path[-len(path_dirs) :] == path_dirs
    assert len(new_path) == len(added_paths) + len(path_dirs) + 1
    assert new_path[len(added_paths)].endswith("condabin")


def test_remove_prefix_from_path_1():
    activator = PosixActivator()
    original_path = tuple(activator._get_starting_path_list())
    keep_path = activator.path_conversion("/keep/this/path")
    final_path = (keep_path,) + original_path
    final_path = activator.path_conversion(final_path)

    test_prefix = join(os.getcwd(), "mytestpath")
    new_paths = tuple(activator._get_path_dirs(test_prefix))
    prefix_added_path = (keep_path,) + new_paths + original_path
    new_path = activator._remove_prefix_from_path(test_prefix, prefix_added_path)
    assert final_path == new_path


def test_remove_prefix_from_path_2():
    # this time prefix doesn't actually exist in path
    activator = PosixActivator()
    original_path = tuple(activator._get_starting_path_list())
    keep_path = activator.path_conversion("/keep/this/path")
    final_path = (keep_path,) + original_path
    final_path = activator.path_conversion(final_path)

    test_prefix = join(os.getcwd(), "mytestpath")
    prefix_added_path = (keep_path,) + original_path
    new_path = activator._remove_prefix_from_path(test_prefix, prefix_added_path)

    assert final_path == new_path


def test_replace_prefix_in_path_1():
    activator = PosixActivator()
    original_path = tuple(activator._get_starting_path_list())
    new_prefix = join(os.getcwd(), "mytestpath-new")
    new_paths = activator.path_conversion(activator._get_path_dirs(new_prefix))
    if isinstance(new_paths, str):
        new_paths = (new_paths,)
    keep_path = activator.path_conversion("/keep/this/path")
    final_path = (keep_path,) + new_paths + original_path
    final_path = activator.path_conversion(final_path)

    replace_prefix = join(os.getcwd(), "mytestpath")
    replace_paths = tuple(activator._get_path_dirs(replace_prefix))
    prefix_added_path = (keep_path,) + replace_paths + original_path
    new_path = activator._replace_prefix_in_path(
        replace_prefix, new_prefix, prefix_added_path
    )

    assert final_path == new_path


@pytest.mark.skipif(not on_win, reason="windows-specific test")
def test_replace_prefix_in_path_2(monkeypatch: MonkeyPatch):
    path1 = join("c:\\", "temp", "6663 31e0")
    path2 = join("c:\\", "temp", "6663 31e0", "envs", "charizard")
    one_more = join("d:\\", "one", "more")
    #   old_prefix: c:\users\builder\appdata\local\temp\6663 31e0
    #   new_prefix: c:\users\builder\appdata\local\temp\6663 31e0\envs\charizard
    activator = CmdExeActivator()
    old_path = activator.pathsep_join(activator._add_prefix_to_path(path1))
    old_path = one_more + ";" + old_path

    monkeypatch.setenv("PATH", old_path)
    activator = PosixActivator()
    path_elements = activator._replace_prefix_in_path(path1, path2)

    assert path_elements[0] == native_path_to_unix(one_more)
    assert path_elements[1] == native_path_to_unix(
        next(activator._get_path_dirs(path2))
    )
    assert len(path_elements) == len(old_path.split(";"))


def test_default_env(reset_environ: None):
    activator = PosixActivator()
    assert ROOT_ENV_NAME == activator._default_env(context.root_prefix)

    with tempdir() as td:
        assert td == activator._default_env(td)

        p = mkdir_p(join(td, "envs", "named-env"))
        assert "named-env" == activator._default_env(p)


def test_build_activate_dont_activate_unset_var(
    monkeypatch: MonkeyPatch,
    env_activate: tuple[str, str, str],
):
    prefix, activate_sh, _ = env_activate

    write_pkgs(prefix)
    write_state_file(
        prefix,
        ENV_ONE=ENV_ONE,
        ENV_TWO=ENV_TWO,
        ENV_THREE=CONDA_ENV_VARS_UNSET_VAR,
    )

    activator = PosixActivator()
    builder = activator.build_activate(prefix)
    new_path = activator.pathsep_join(activator._add_prefix_to_path(prefix))

    set_vars = {"PS1": get_prompt(prefix)}
    export_vars, unset_vars = activator.get_export_unset_vars(
        PATH=new_path,
        CONDA_PREFIX=prefix,
        CONDA_SHLVL=1,
        CONDA_DEFAULT_ENV=prefix,
        CONDA_PROMPT_MODIFIER=get_prompt_modifier(prefix),
        # write_pkgs
        PKG_A_ENV=PKG_A_ENV,
        PKG_B_ENV=PKG_B_ENV,
        # write_state_file
        ENV_ONE=ENV_ONE,
        ENV_TWO=ENV_TWO,
    )
    assert builder["unset_vars"] == unset_vars
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["activate_scripts"] == (activator.path_conversion(activate_sh),)
    assert builder["deactivate_scripts"] == ()


def test_build_activate_shlvl_warn_clobber_vars(
    monkeypatch: MonkeyPatch,
    env_activate: tuple[str, str, str],
):
    prefix, activate_sh, _ = env_activate

    write_pkgs(prefix)
    write_state_file(
        prefix,
        ENV_ONE=ENV_ONE,
        ENV_TWO=ENV_TWO,
        ENV_THREE=ENV_THREE,
        PKG_A_ENV=(overwrite_a := "overwrite_a"),
    )

    activator = PosixActivator()
    builder = activator.build_activate(prefix)
    new_path = activator.pathsep_join(activator._add_prefix_to_path(prefix))

    set_vars = {"PS1": get_prompt(prefix)}
    export_vars, unset_vars = activator.get_export_unset_vars(
        PATH=new_path,
        CONDA_PREFIX=prefix,
        CONDA_SHLVL=1,
        CONDA_DEFAULT_ENV=prefix,
        CONDA_PROMPT_MODIFIER=get_prompt_modifier(prefix),
        # write_pkgs
        PKG_B_ENV=PKG_B_ENV,
        # write_state_file
        ENV_ONE=ENV_ONE,
        ENV_TWO=ENV_TWO,
        ENV_THREE=ENV_THREE,
        PKG_A_ENV=overwrite_a,
    )
    assert builder["unset_vars"] == unset_vars
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["activate_scripts"] == (activator.path_conversion(activate_sh),)
    assert builder["deactivate_scripts"] == ()


def test_build_activate_shlvl_0(
    monkeypatch: MonkeyPatch,
    env_activate: tuple[str, str, str],
):
    prefix, activate_sh, _ = env_activate

    write_pkgs(prefix)
    write_state_file(prefix)

    activator = PosixActivator()
    builder = activator.build_activate(prefix)
    new_path = activator.pathsep_join(activator._add_prefix_to_path(prefix))

    set_vars = {"PS1": get_prompt(prefix)}
    export_vars, unset_vars = activator.get_export_unset_vars(
        PATH=new_path,
        CONDA_PREFIX=prefix,
        CONDA_SHLVL=1,
        CONDA_DEFAULT_ENV=prefix,
        CONDA_PROMPT_MODIFIER=get_prompt_modifier(prefix),
        # write_pkgs
        PKG_A_ENV=PKG_A_ENV,
        PKG_B_ENV=PKG_B_ENV,
        # write_state_file
        ENV_ONE=ENV_ONE,
        ENV_TWO=ENV_TWO,
        ENV_THREE=ENV_THREE,
        ENV_WITH_SAME_VALUE=ENV_WITH_SAME_VALUE,
    )
    assert builder["unset_vars"] == unset_vars
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["activate_scripts"] == (activator.path_conversion(activate_sh),)
    assert builder["deactivate_scripts"] == ()


@skip_unsupported_posix_path
def test_build_activate_shlvl_1(
    monkeypatch: MonkeyPatch,
    env_activate: tuple[str, str, str],
):
    prefix, activate_sh, _ = env_activate

    write_pkgs(prefix)
    write_state_file(prefix)

    old_prefix = "/old/prefix"
    activator = PosixActivator()
    old_path = activator.pathsep_join(activator._add_prefix_to_path(old_prefix))

    monkeypatch.setenv("CONDA_SHLVL", "1")
    monkeypatch.setenv("CONDA_PREFIX", old_prefix)
    monkeypatch.setenv("PATH", old_path)

    activator = PosixActivator()
    builder = activator.build_activate(prefix)
    new_path = activator.pathsep_join(
        activator._replace_prefix_in_path(old_prefix, prefix)
    )

    assert activator.path_conversion(prefix) in new_path
    assert old_prefix not in new_path

    set_vars = {"PS1": get_prompt(prefix)}
    export_vars, unset_vars = activator.get_export_unset_vars(
        PATH=new_path,
        CONDA_PREFIX=prefix,
        CONDA_PREFIX_1=old_prefix,
        CONDA_SHLVL=2,
        CONDA_DEFAULT_ENV=prefix,
        CONDA_PROMPT_MODIFIER=(conda_prompt_modifier := get_prompt_modifier(prefix)),
        # write_pkgs
        PKG_A_ENV=PKG_A_ENV,
        PKG_B_ENV=PKG_B_ENV,
        # write_state_file
        ENV_ONE=ENV_ONE,
        ENV_TWO=ENV_TWO,
        ENV_THREE=ENV_THREE,
        ENV_WITH_SAME_VALUE=ENV_WITH_SAME_VALUE,
    )
    assert builder["unset_vars"] == unset_vars
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["activate_scripts"] == (activator.path_conversion(activate_sh),)
    assert builder["deactivate_scripts"] == ()

    monkeypatch.setenv("PATH", new_path)
    monkeypatch.setenv("CONDA_PREFIX", prefix)
    monkeypatch.setenv("CONDA_PREFIX_1", old_prefix)
    monkeypatch.setenv("CONDA_SHLVL", 2)
    monkeypatch.setenv("CONDA_DEFAULT_ENV", prefix)
    monkeypatch.setenv("CONDA_PROMPT_MODIFIER", conda_prompt_modifier)
    # write_pkgs
    monkeypatch.setenv("PKG_A_ENV", PKG_A_ENV)
    monkeypatch.setenv("PKG_B_ENV", PKG_B_ENV)
    # write_state_file
    monkeypatch.setenv("ENV_ONE", ENV_ONE)
    monkeypatch.setenv("ENV_TWO", ENV_TWO)
    monkeypatch.setenv("ENV_THREE", ENV_THREE)
    monkeypatch.setenv("ENV_WITH_SAME_VALUE", ENV_WITH_SAME_VALUE)

    activator = PosixActivator()
    builder = activator.build_deactivate()

    set_vars = {"PS1": get_prompt(old_prefix)}
    export_path = {"PATH": old_path}
    export_vars, unset_vars = activator.get_export_unset_vars(
        CONDA_PREFIX=old_prefix,
        CONDA_SHLVL=1,
        CONDA_DEFAULT_ENV=old_prefix,
        CONDA_PROMPT_MODIFIER=get_prompt_modifier(old_prefix),
        CONDA_PREFIX_1=None,
        # write_pkgs
        PKG_A_ENV=None,
        PKG_B_ENV=None,
        # write_state_file
        ENV_ONE=None,
        ENV_TWO=None,
        ENV_THREE=None,
        ENV_WITH_SAME_VALUE=None,
    )
    assert builder["unset_vars"] == unset_vars
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["export_path"] == export_path
    assert builder["activate_scripts"] == ()
    assert builder["deactivate_scripts"] == ()


@skip_unsupported_posix_path
def test_build_stack_shlvl_1(
    monkeypatch: MonkeyPatch,
    env_activate: tuple[str, str, str],
):
    prefix, activate_sh, _ = env_activate

    write_pkgs(prefix)
    write_state_file(prefix)

    old_prefix = "/old/prefix"
    activator = PosixActivator()
    old_path = activator.pathsep_join(activator._add_prefix_to_path(old_prefix))

    monkeypatch.setenv("CONDA_SHLVL", "1")
    monkeypatch.setenv("CONDA_PREFIX", old_prefix)
    monkeypatch.setenv("PATH", old_path)

    activator = PosixActivator()
    builder = activator.build_stack(prefix)
    new_path = activator.pathsep_join(activator._add_prefix_to_path(prefix))

    assert prefix in new_path
    assert old_prefix in new_path

    set_vars = {"PS1": get_prompt(prefix)}
    export_vars, unset_vars = activator.get_export_unset_vars(
        PATH=new_path,
        CONDA_PREFIX=prefix,
        CONDA_PREFIX_1=old_prefix,
        CONDA_SHLVL=2,
        CONDA_DEFAULT_ENV=prefix,
        CONDA_PROMPT_MODIFIER=(conda_prompt_modifier := get_prompt_modifier(prefix)),
        CONDA_STACKED_2="true",
        # write_pkgs
        PKG_A_ENV=PKG_A_ENV,
        PKG_B_ENV=PKG_B_ENV,
        # write_state_file
        ENV_ONE=ENV_ONE,
        ENV_TWO=ENV_TWO,
        ENV_THREE=ENV_THREE,
        ENV_WITH_SAME_VALUE=ENV_WITH_SAME_VALUE,
    )
    assert builder["unset_vars"] == unset_vars
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["activate_scripts"] == (activator.path_conversion(activate_sh),)
    assert builder["deactivate_scripts"] == ()

    monkeypatch.setenv("PATH", new_path)
    monkeypatch.setenv("CONDA_PREFIX", prefix)
    monkeypatch.setenv("CONDA_PREFIX_1", old_prefix)
    monkeypatch.setenv("CONDA_SHLVL", 2)
    monkeypatch.setenv("CONDA_DEFAULT_ENV", prefix)
    monkeypatch.setenv("CONDA_PROMPT_MODIFIER", conda_prompt_modifier)
    monkeypatch.setenv("CONDA_STACKED_2", "true")
    # write_pkgs
    monkeypatch.setenv("PKG_A_ENV", PKG_A_ENV)
    monkeypatch.setenv("PKG_B_ENV", PKG_B_ENV)
    # write_state_file
    monkeypatch.setenv("ENV_ONE", ENV_ONE)
    monkeypatch.setenv("ENV_TWO", ENV_TWO)
    monkeypatch.setenv("ENV_THREE", ENV_THREE)

    activator = PosixActivator()
    builder = activator.build_deactivate()

    set_vars = {"PS1": get_prompt(old_prefix)}
    export_vars, unset_vars = activator.get_export_unset_vars(
        CONDA_PREFIX=old_prefix,
        CONDA_SHLVL=1,
        CONDA_DEFAULT_ENV=old_prefix,
        CONDA_PROMPT_MODIFIER=get_prompt_modifier(old_prefix),
        CONDA_PREFIX_1=None,
        CONDA_STACKED_2=None,
        # write_pkgs
        PKG_A_ENV=None,
        PKG_B_ENV=None,
        # write_state_file
        ENV_ONE=None,
        ENV_TWO=None,
        ENV_THREE=None,
        ENV_WITH_SAME_VALUE=None,
    )
    assert builder["unset_vars"] == unset_vars
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["activate_scripts"] == ()
    assert builder["deactivate_scripts"] == ()


def test_activate_same_environment(
    monkeypatch: MonkeyPatch,
    env_activate_deactivate: tuple[str, str, str, str, str],
):
    prefix, activate_sh, _, deactivate_sh, _ = env_activate_deactivate

    monkeypatch.setenv("CONDA_SHLVL", "1")
    monkeypatch.setenv("CONDA_PREFIX", prefix)

    activator = PosixActivator()

    builder = activator.build_activate(prefix)

    new_path_parts = activator._replace_prefix_in_path(prefix, prefix)

    set_vars = {"PS1": get_prompt(prefix)}
    export_vars = {
        "PATH": activator.pathsep_join(new_path_parts),
        "CONDA_SHLVL": 1,
        "CONDA_PROMPT_MODIFIER": get_prompt_modifier(prefix),
    }
    assert builder["unset_vars"] == ()
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["activate_scripts"] == (activator.path_conversion(activate_sh),)
    assert builder["deactivate_scripts"] == (activator.path_conversion(deactivate_sh),)


@skip_unsupported_posix_path
def test_build_deactivate_shlvl_2_from_stack(
    monkeypatch: MonkeyPatch,
    env_activate: tuple[str, str, str],
    env_deactivate: tuple[str, str, str],
):
    old_prefix, activate_sh, _ = env_activate

    write_pkg_B(old_prefix)
    write_state_file(
        old_prefix,
        ENV_FOUR=ENV_FOUR,
        ENV_FIVE=ENV_FIVE,
    )

    prefix, deactivate_sh, _ = env_deactivate

    write_pkg_A(prefix)
    write_state_file(prefix)

    activator = PosixActivator()
    original_path = activator.pathsep_join(activator._add_prefix_to_path(old_prefix))

    monkeypatch.setenv("PATH", original_path)

    activator = PosixActivator()
    starting_path = activator.pathsep_join(activator._add_prefix_to_path(prefix))

    monkeypatch.setenv("CONDA_SHLVL", "2")
    monkeypatch.setenv("CONDA_PREFIX_1", old_prefix)
    monkeypatch.setenv("CONDA_PREFIX", prefix)
    monkeypatch.setenv("CONDA_STACKED_2", "true")
    monkeypatch.setenv("PATH", starting_path)
    # write_pkg_B (old_prefix)
    monkeypatch.setenv("PKG_B_ENV", PKG_B_ENV)
    # write_state_file (old_prefix)
    monkeypatch.setenv("ENV_FOUR", ENV_FOUR)
    monkeypatch.setenv("ENV_FIVE", ENV_FIVE)
    # write_pkg_A (prefix)
    monkeypatch.setenv("PKG_A_ENV", PKG_A_ENV)
    # write_state_file (prefix)
    monkeypatch.setenv("ENV_ONE", ENV_ONE)
    monkeypatch.setenv("ENV_TWO", ENV_TWO)
    monkeypatch.setenv("ENV_THREE", ENV_THREE)
    monkeypatch.setenv("ENV_WITH_SAME_VALUE", ENV_WITH_SAME_VALUE)

    activator = PosixActivator()
    builder = activator.build_deactivate()

    set_vars = {"PS1": get_prompt(old_prefix)}
    export_path = {"PATH": original_path}
    export_vars, unset_vars = activator.get_export_unset_vars(
        CONDA_PREFIX=old_prefix,
        CONDA_SHLVL=1,
        CONDA_DEFAULT_ENV=old_prefix,
        CONDA_PROMPT_MODIFIER=get_prompt_modifier(old_prefix),
        CONDA_PREFIX_1=None,
        CONDA_STACKED_2=None,
        # write_pkg_B (old_prefix)
        PKG_B_ENV=PKG_B_ENV,
        # write_state_file (old_prefix)
        ENV_FOUR=ENV_FOUR,
        ENV_FIVE=ENV_FIVE,
        # write_pkg_A (prefix)
        PKG_A_ENV=None,
        # write_state_file (prefix)
        ENV_ONE=None,
        ENV_TWO=None,
        ENV_THREE=None,
        ENV_WITH_SAME_VALUE=None,
    )
    assert builder["unset_vars"] == unset_vars
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["export_path"] == export_path
    assert builder["activate_scripts"] == (activator.path_conversion(activate_sh),)
    assert builder["deactivate_scripts"] == (activator.path_conversion(deactivate_sh),)


@skip_unsupported_posix_path
def test_build_deactivate_shlvl_2_from_activate(
    monkeypatch: MonkeyPatch,
    env_activate: tuple[str, str, str],
    env_deactivate: tuple[str, str, str],
):
    old_prefix, activate_sh, _ = env_activate

    write_pkg_B(old_prefix)
    write_state_file(
        old_prefix,
        ENV_FOUR=ENV_FOUR,
        ENV_FIVE=ENV_FIVE,
    )

    prefix, deactivate_sh, _ = env_deactivate

    write_pkg_A(prefix)
    write_state_file(prefix)

    activator = PosixActivator()
    original_path = activator.pathsep_join(activator._add_prefix_to_path(old_prefix))
    new_path = activator.pathsep_join(activator._add_prefix_to_path(prefix))

    monkeypatch.setenv("CONDA_SHLVL", "2")
    monkeypatch.setenv("CONDA_PREFIX_1", old_prefix)
    monkeypatch.setenv("CONDA_PREFIX", prefix)
    monkeypatch.setenv("PATH", new_path)
    # write_pkg_A (prefix)
    monkeypatch.setenv("PKG_A_ENV", PKG_A_ENV)
    # write_state_file (prefix)
    monkeypatch.setenv("ENV_ONE", ENV_ONE)
    monkeypatch.setenv("ENV_TWO", ENV_TWO)
    monkeypatch.setenv("ENV_THREE", ENV_THREE)
    monkeypatch.setenv("ENV_WITH_SAME_VALUE", ENV_WITH_SAME_VALUE)

    activator = PosixActivator()
    builder = activator.build_deactivate()

    set_vars = {"PS1": get_prompt(old_prefix)}
    export_path = {"PATH": original_path}
    export_vars, unset_vars = activator.get_export_unset_vars(
        CONDA_PREFIX=old_prefix,
        CONDA_SHLVL=1,
        CONDA_DEFAULT_ENV=old_prefix,
        CONDA_PROMPT_MODIFIER=get_prompt_modifier(old_prefix),
        CONDA_PREFIX_1=None,
        # write_pkg_B (old_prefix)
        PKG_B_ENV=PKG_B_ENV,
        # write_state_file (old_prefix)
        ENV_FOUR=ENV_FOUR,
        ENV_FIVE=ENV_FIVE,
        # write_pkg_A (prefix)
        PKG_A_ENV=None,
        # write_state_file (prefix)
        ENV_ONE=None,
        ENV_TWO=None,
        ENV_THREE=None,
        ENV_WITH_SAME_VALUE=None,
    )

    assert builder["unset_vars"] == unset_vars
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["export_path"] == export_path
    assert builder["activate_scripts"] == (activator.path_conversion(activate_sh),)
    assert builder["deactivate_scripts"] == (activator.path_conversion(deactivate_sh),)


def test_build_deactivate_shlvl_1(
    monkeypatch: MonkeyPatch,
    env_deactivate: tuple[str, str, str],
):
    prefix, deactivate_sh, _ = env_deactivate

    write_pkgs(prefix)
    write_state_file(prefix)

    monkeypatch.setenv("CONDA_SHLVL", "1")
    monkeypatch.setenv("CONDA_PREFIX", prefix)

    activator = PosixActivator()
    original_path = tuple(activator._get_starting_path_list())
    builder = activator.build_deactivate()

    new_path = activator.pathsep_join(activator.path_conversion(original_path))
    set_vars = {"PS1": get_prompt()}
    export_vars, unset_vars = activator.get_export_unset_vars(
        CONDA_SHLVL=0,
        CONDA_PREFIX=None,
        CONDA_DEFAULT_ENV=None,
        CONDA_PROMPT_MODIFIER=None,
        # write_pkgs
        PKG_A_ENV=None,
        PKG_B_ENV=None,
        # write_state_file
        ENV_ONE=None,
        ENV_TWO=None,
        ENV_THREE=None,
        ENV_WITH_SAME_VALUE=None,
    )
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["unset_vars"] == unset_vars
    assert builder["export_path"] == {"PATH": new_path}
    assert builder["activate_scripts"] == ()
    assert builder["deactivate_scripts"] == (activator.path_conversion(deactivate_sh),)


def test_get_env_vars_big_whitespace(tmp_env: TmpEnvFixture):
    with tmp_env() as prefix:
        write_state_file(prefix)

        activator = PosixActivator()
        env_vars = activator._get_environment_env_vars(prefix)
        assert env_vars == {
            "ENV_ONE": ENV_ONE,
            "ENV_TWO": ENV_TWO,
            "ENV_THREE": ENV_THREE,
            "ENV_WITH_SAME_VALUE": ENV_WITH_SAME_VALUE,
        }


def test_get_env_vars_empty_file(tmp_env: TmpEnvFixture):
    with tmp_env() as prefix:
        (prefix / "conda-meta" / "env_vars").touch()

        activator = PosixActivator()
        env_vars = activator._get_environment_env_vars(prefix)
        assert env_vars == {}


@skip_unsupported_posix_path
def test_build_activate_restore_unset_env_vars(
    monkeypatch: MonkeyPatch,
    env_activate: tuple[str, str, str],
):
    prefix, activate_sh, _ = env_activate

    write_pkgs(prefix)
    write_state_file(prefix)

    old_prefix = "/old/prefix"
    activator = PosixActivator()
    old_path = activator.pathsep_join(activator._add_prefix_to_path(old_prefix))

    monkeypatch.setenv("CONDA_SHLVL", "1")
    monkeypatch.setenv("CONDA_PREFIX", old_prefix)
    monkeypatch.setenv("PATH", old_path)
    monkeypatch.setenv("ENV_ONE", "already_set_env_var")
    monkeypatch.setenv("ENV_WITH_SAME_VALUE", ENV_WITH_SAME_VALUE)

    activator = PosixActivator()
    builder = activator.build_activate(prefix)
    new_path = activator.pathsep_join(
        activator._replace_prefix_in_path(old_prefix, prefix)
    )

    assert activator.path_conversion(prefix) in new_path
    assert old_prefix not in new_path

    set_vars = {"PS1": get_prompt(prefix)}
    export_vars, unset_vars = activator.get_export_unset_vars(
        PATH=new_path,
        CONDA_PREFIX=prefix,
        CONDA_PREFIX_1=old_prefix,
        CONDA_SHLVL=2,
        CONDA_DEFAULT_ENV=prefix,
        CONDA_PROMPT_MODIFIER=(conda_prompt_modifier := get_prompt_modifier(prefix)),
        __CONDA_SHLVL_1_ENV_ONE="already_set_env_var",
        __CONDA_SHLVL_1_ENV_WITH_SAME_VALUE=ENV_WITH_SAME_VALUE,
        # write_pkgs
        PKG_A_ENV=PKG_A_ENV,
        PKG_B_ENV=PKG_B_ENV,
        # write_state_file
        ENV_ONE=ENV_ONE,
        ENV_TWO=ENV_TWO,
        ENV_THREE=ENV_THREE,
        ENV_WITH_SAME_VALUE=ENV_WITH_SAME_VALUE,
    )

    assert builder["unset_vars"] == unset_vars
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["activate_scripts"] == (activator.path_conversion(activate_sh),)
    assert builder["deactivate_scripts"] == ()

    monkeypatch.setenv("PATH", new_path)
    monkeypatch.setenv("CONDA_PREFIX", prefix)
    monkeypatch.setenv("CONDA_PREFIX_1", old_prefix)
    monkeypatch.setenv("CONDA_SHLVL", 2)
    monkeypatch.setenv("CONDA_DEFAULT_ENV", prefix)
    monkeypatch.setenv("CONDA_PROMPT_MODIFIER", conda_prompt_modifier)
    monkeypatch.setenv("__CONDA_SHLVL_1_ENV_ONE", "already_set_env_var")
    # write_pkgs
    monkeypatch.setenv("PKG_A_ENV", PKG_A_ENV)
    monkeypatch.setenv("PKG_B_ENV", PKG_B_ENV)
    # write_state_file
    monkeypatch.setenv("ENV_ONE", ENV_ONE)
    monkeypatch.setenv("ENV_TWO", ENV_TWO)
    monkeypatch.setenv("ENV_THREE", ENV_THREE)
    monkeypatch.setenv("ENV_WITH_SAME_VALUE", ENV_WITH_SAME_VALUE)

    activator = PosixActivator()
    builder = activator.build_deactivate()

    set_vars = {"PS1": get_prompt(old_prefix)}
    export_path = {"PATH": old_path}
    export_vars, unset_vars = activator.get_export_unset_vars(
        CONDA_PREFIX=old_prefix,
        CONDA_SHLVL=1,
        CONDA_DEFAULT_ENV=old_prefix,
        CONDA_PROMPT_MODIFIER=get_prompt_modifier(old_prefix),
        CONDA_PREFIX_1=None,
        # write_pkgs
        PKG_A_ENV=None,
        PKG_B_ENV=None,
        # write_state_file
        ENV_ONE=None,
        ENV_TWO=None,
        ENV_THREE=None,
        ENV_WITH_SAME_VALUE=None,
    )
    export_vars["ENV_ONE"] = "already_set_env_var"
    assert builder["unset_vars"] == unset_vars
    assert builder["set_vars"] == set_vars
    assert builder["export_vars"] == export_vars
    assert builder["export_path"] == export_path
    assert builder["activate_scripts"] == ()
    assert builder["deactivate_scripts"] == ()


@pytest.fixture
def shell_wrapper_unit(path_factory: PathFactoryFixture) -> str:
    prefix = path_factory()
    history = prefix / "conda-meta" / "history"
    history.parent.mkdir(parents=True, exist_ok=True)
    history.touch()

    yield str(prefix)


def make_dot_d_files(prefix, extension):
    mkdir_p(join(prefix, "etc", "conda", "activate.d"))
    mkdir_p(join(prefix, "etc", "conda", "deactivate.d"))

    touch(join(prefix, "etc", "conda", "activate.d", "ignore.txt"))
    touch(join(prefix, "etc", "conda", "deactivate.d", "ignore.txt"))

    touch(join(prefix, "etc", "conda", "activate.d", f"activate1{extension}"))
    touch(join(prefix, "etc", "conda", "deactivate.d", f"deactivate1{extension}"))


@pytest.mark.skipif(
    not on_win,
    reason="native_path_to_unix is path_identity on non-windows",
)
@pytest.mark.parametrize(
    "paths,expected",
    [
        # falsy
        pytest.param(None, [None], id="None"),
        pytest.param("", ["."], id="empty string"),
        pytest.param((), [()], id="empty tuple"),
        # native
        pytest.param(
            "C:\\path\\to\\One",
            [
                "/c/path/to/One",  # MSYS2
                "/cygdrive/c/path/to/One",  # cygwin
            ],
            id="path",
        ),
        pytest.param(
            ["C:\\path\\to\\One"],
            [
                ("/c/path/to/One",),  # MSYS2
                ("/cygdrive/c/path/to/One",),  # cygwin
            ],
            id="list[path]",
        ),
        pytest.param(
            ("C:\\path\\to\\One", "C:\\path\\Two", "\\\\mount\\Three"),
            [
                ("/c/path/to/One", "/c/path/Two", "//mount/Three"),  # MSYS2
                (
                    "/cygdrive/c/path/to/One",
                    "/cygdrive/c/path/Two",
                    "//mount/Three",
                ),  # cygwin
            ],
            id="tuple[path, ...]",
        ),
        pytest.param(
            "C:\\path\\to\\One;C:\\path\\Two;\\\\mount\\Three",
            [
                "/c/path/to/One:/c/path/Two://mount/Three",  # MSYS2
                "/cygdrive/c/path/to/One:/cygdrive/c/path/Two://mount/Three",  # cygwin
            ],
            id="path;...",
        ),
    ],
)
@pytest.mark.parametrize(
    "cygpath",
    [pytest.param(True, id="cygpath"), pytest.param(False, id="fallback")],
)
def test_native_path_to_unix(
    mocker: MockerFixture,
    paths: str | Iterable[str] | None,
    expected: str | list[str] | None,
    cygpath: bool,
) -> None:
    if not cygpath:
        # test without cygpath
        mocker.patch("subprocess.run", side_effect=FileNotFoundError)

    assert native_path_to_unix(paths) in expected


@pytest.mark.skipif(
    not on_win,
    reason="native_path_to_unix is path_identity on non-windows",
)
@pytest.mark.parametrize(
    "paths,expected",
    [
        # falsy
        pytest.param(None, None, id="None"),
        pytest.param("", ".", id="empty string"),
        pytest.param((), (), id="empty tuple"),
        # MSYS2
        pytest.param(
            # 1 leading slash = root
            "/",
            "{WINDOWS}\\Library\\",
            id="root",
        ),
        pytest.param(
            # 1 leading slash + 1 letter = drive
            "/c",
            "C:\\",
            id="drive",
        ),
        pytest.param(
            # 1 leading slash + 1 letter = drive
            "/c/",
            "C:\\",
            id="drive [trailing]",
        ),
        pytest.param(
            # 1 leading slash + 2+ letters = root path
            "/root",
            "{WINDOWS}\\Library\\root",
            id="root path",
        ),
        pytest.param(
            # 1 leading slash + 2+ letters = root path
            "/root/",
            "{WINDOWS}\\Library\\root\\",
            id="root path [trailing]",
        ),
        pytest.param(
            # 2 leading slashes = UNC mount
            "//",
            "\\\\",
            id="bare UNC mount",
        ),
        pytest.param(
            # 2 leading slashes = UNC mount
            "//mount",
            "\\\\mount",
            id="UNC mount",
        ),
        pytest.param(
            # 2 leading slashes = UNC mount
            "//mount/",
            "\\\\mount\\",
            id="UNC mount [trailing]",
        ),
        pytest.param(
            # 3+ leading slashes = root
            "///",
            "{WINDOWS}\\Library\\",
            id="root [leading]",
        ),
        pytest.param(
            # 3+ leading slashes = root path
            "///root",
            "{WINDOWS}\\Library\\root",
            id="root path [leading]",
        ),
        pytest.param(
            # 3+ leading slashes = root
            "////",
            "{WINDOWS}\\Library\\",
            id="root [leading, trailing]",
        ),
        pytest.param(
            # 3+ leading slashes = root path
            "///root/",
            "{WINDOWS}\\Library\\root\\",
            id="root path [leading, trailing]",
        ),
        pytest.param(
            # a normal path
            "/c/path/to/One",
            "C:\\path\\to\\One",
            id="normal path",
        ),
        pytest.param(
            # a normal path
            "/c//path///to////One",
            "C:\\path\\to\\One",
            id="normal path [extra]",
        ),
        pytest.param(
            # a normal path
            "/c/path/to/One/",
            "C:\\path\\to\\One\\",
            id="normal path [trailing]",
        ),
        pytest.param(
            # a normal UNC path
            "//mount/to/One",
            "\\\\mount\\to\\One",
            id="UNC path",
        ),
        pytest.param(
            # a normal UNC path
            "//mount//to///One",
            "\\\\mount\\to\\One",
            id="UNC path [extra]",
        ),
        pytest.param(
            # a normal root path
            "/path/to/One",
            "{WINDOWS}\\Library\\path\\to\\One",
            id="root path",
        ),
        pytest.param(
            # a normal root path
            "/path//to///One",
            "{WINDOWS}\\Library\\path\\to\\One",
            id="root path [extra]",
        ),
        pytest.param(
            # relative path stays relative
            "relative/path/to/One",
            "relative\\path\\to\\One",
            id="relative",
        ),
        pytest.param(
            # relative path stays relative
            "relative//path///to////One",
            "relative\\path\\to\\One",
            id="relative [extra]",
        ),
        pytest.param(
            "/c/path/to/One://path/to/One:/path/to/One:relative/path/to/One",
            (
                "C:\\path\\to\\One;"
                "\\\\path\\to\\One;"
                "{WINDOWS}\\Library\\path\\to\\One;"
                "relative\\path\\to\\One"
            ),
            id="path;...",
        ),
        pytest.param(
            ["/c/path/to/One"],
            ("C:\\path\\to\\One",),
            id="list[path]",
        ),
        pytest.param(
            ("/c/path/to/One", "/c/path/Two", "//mount/Three"),
            ("C:\\path\\to\\One", "C:\\path\\Two", "\\\\mount\\Three"),
            id="tuple[path, ...]",
        ),
        # XXX Cygwin and MSYS2's cygpath programs are not mutually
        # aware meaning that MSYS2's cygpath treats
        # /cygrive/c/here/there as a regular absolute path and returns
        # {prefix}\Library\cygdrive\c\here\there.  And vice versa.
        #
        # cygwin
        # pytest.param(
        #     "/cygdrive/c/path/to/One",
        #     "C:\\path\\to\\One",
        #     id="Cygwin drive letter path (cygwin)",
        # ),
        # pytest.param(
        #     ["/cygdrive/c/path/to/One"],
        #     ("C:\\path\\to\\One",),
        #     id="list[path] (cygwin)",
        # ),
        # pytest.param(
        #     ("/cygdrive/c/path/to/One", "/cygdrive/c/path/Two", "//mount/Three"),
        #     ("C:\\path\\to\\One", "C:\\path\\Two", "\\\\mount\\Three"),
        #     id="tuple[path, ...] (cygwin)",
        # ),
    ],
)
@pytest.mark.parametrize(
    "unix",
    [
        pytest.param(True, id="Unix"),
        pytest.param(False, id="Windows"),
    ],
)
@pytest.mark.parametrize(
    "cygpath",
    [pytest.param(True, id="cygpath"), pytest.param(False, id="fallback")],
)
def test_unix_path_to_native(
    tmp_env: TmpEnvFixture,
    mocker: MockerFixture,
    paths: str | Iterable[str] | None,
    expected: str | tuple[str, ...] | None,
    unix: bool,
    cygpath: bool,
) -> None:
    windows_prefix = context.target_prefix
    unix_prefix = native_path_to_unix(windows_prefix)

    def format(path: str) -> str:
        return path.format(UNIX=unix_prefix, WINDOWS=windows_prefix)

    prefix = unix_prefix if unix else windows_prefix
    if expected:
        expected = (
            tuple(map(format, expected))
            if isinstance(expected, tuple)
            else format(expected)
        )

    if not cygpath:
        # test without cygpath
        mocker.patch("subprocess.run", side_effect=FileNotFoundError)

    assert unix_path_to_native(paths, prefix) == expected


def test_posix_basic(
    shell_wrapper_unit: str,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture,
) -> None:
    activator = PosixActivator()
    make_dot_d_files(shell_wrapper_unit, activator.script_extension)

    err = main_sourced("shell.posix", *activate_args, shell_wrapper_unit)
    activate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path_parts = activator._add_prefix_to_path(shell_wrapper_unit)
    conda_exe_export, conda_exe_unset = get_scripts_export_unset_vars(activator)

    e_activate_data = dals(
        """
    PS1='%(ps1)s'
    %(conda_exe_unset)s
    export PATH='%(new_path)s'
    export CONDA_PREFIX='%(native_prefix)s'
    export CONDA_SHLVL='1'
    export CONDA_DEFAULT_ENV='%(native_prefix)s'
    export CONDA_PROMPT_MODIFIER='%(conda_prompt_modifier)s'
    %(conda_exe_export)s
    . "%(activate1)s"
    """
    ) % {
        "native_prefix": shell_wrapper_unit,
        "new_path": activator.pathsep_join(new_path_parts),
        "sys_executable": activator.path_conversion(sys.executable),
        "activate1": activator.path_conversion(
            join(shell_wrapper_unit, "etc", "conda", "activate.d", "activate1.sh")
        ),
        "ps1": get_prompt(shell_wrapper_unit),
        "conda_prompt_modifier": get_prompt_modifier(shell_wrapper_unit),
        "conda_exe_unset": conda_exe_unset,
        "conda_exe_export": conda_exe_export,
    }

    assert activate_data == re.sub(r"\n\n+", "\n", e_activate_data)

    monkeypatch.setenv("CONDA_PREFIX", shell_wrapper_unit)
    monkeypatch.setenv("CONDA_SHLVL", "1")
    monkeypatch.setenv("PATH", os.pathsep.join((*new_path_parts, os.environ["PATH"])))

    activator = PosixActivator()
    err = main_sourced("shell.posix", *reactivate_args)
    reactivate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path_parts = activator._replace_prefix_in_path(
        shell_wrapper_unit, shell_wrapper_unit
    )
    e_reactivate_data = dals(
        """
    . "%(deactivate1)s"
    PS1='%(ps1)s'
    export PATH='%(new_path)s'
    export CONDA_SHLVL='1'
    export CONDA_PROMPT_MODIFIER='%(conda_prompt_modifier)s'
    . "%(activate1)s"
    """
    ) % {
        "activate1": activator.path_conversion(
            join(shell_wrapper_unit, "etc", "conda", "activate.d", "activate1.sh")
        ),
        "deactivate1": activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "deactivate.d",
                "deactivate1.sh",
            )
        ),
        "native_prefix": shell_wrapper_unit,
        "new_path": activator.pathsep_join(new_path_parts),
        "ps1": get_prompt(shell_wrapper_unit),
        "conda_prompt_modifier": get_prompt_modifier(shell_wrapper_unit),
    }
    assert reactivate_data == re.sub(r"\n\n+", "\n", e_reactivate_data)

    err = main_sourced("shell.posix", *deactivate_args)
    deactivate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path = activator.pathsep_join(
        activator._remove_prefix_from_path(shell_wrapper_unit)
    )
    (
        conda_exe_export,
        conda_exe_unset,
    ) = get_scripts_export_unset_vars(activator)

    e_deactivate_data = dals(
        """
    export PATH='%(new_path)s'
    . "%(deactivate1)s"
    %(conda_exe_unset)s
    unset CONDA_PREFIX
    unset CONDA_DEFAULT_ENV
    unset CONDA_PROMPT_MODIFIER
    PS1='%(ps1)s'
    export CONDA_SHLVL='0'
    %(conda_exe_export)s
    """
    ) % {
        "new_path": new_path,
        "deactivate1": activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "deactivate.d",
                "deactivate1.sh",
            )
        ),
        "ps1": get_prompt(),
        "conda_exe_unset": conda_exe_unset,
        "conda_exe_export": conda_exe_export,
    }
    assert deactivate_data == re.sub(r"\n\n+", "\n", e_deactivate_data)


@pytest.mark.skipif(not on_win, reason="cmd.exe only on Windows")
def test_cmd_exe_basic(
    shell_wrapper_unit: str,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture,
) -> None:
    # NOTE :: We do not want dev mode here.
    context.dev = False
    activator = CmdExeActivator()
    make_dot_d_files(shell_wrapper_unit, activator.script_extension)

    err = main_sourced("shell.cmd.exe", "activate", shell_wrapper_unit)
    activate_result, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    with open(activate_result) as fh:
        activate_data = fh.read()
    rm_rf(activate_result)

    new_path_parts = activator._add_prefix_to_path(shell_wrapper_unit)
    conda_exe_export, conda_exe_unset = get_scripts_export_unset_vars(activator)

    e_activate_data = dals(
        """
    @SET "PATH=%(new_path)s"
    @SET "CONDA_PREFIX=%(converted_prefix)s"
    @SET "CONDA_SHLVL=1"
    @SET "CONDA_DEFAULT_ENV=%(native_prefix)s"
    @SET "CONDA_PROMPT_MODIFIER=%(conda_prompt_modifier)s"
    %(conda_exe_export)s
    @CALL "%(activate1)s"
    """
    ) % {
        "converted_prefix": activator.path_conversion(shell_wrapper_unit),
        "native_prefix": shell_wrapper_unit,
        "new_path": activator.pathsep_join(new_path_parts),
        "sys_executable": activator.path_conversion(sys.executable),
        "activate1": activator.path_conversion(
            join(shell_wrapper_unit, "etc", "conda", "activate.d", "activate1.bat")
        ),
        "conda_exe_export": conda_exe_export,
        "conda_prompt_modifier": get_prompt_modifier(shell_wrapper_unit),
    }
    assert activate_data == e_activate_data

    monkeypatch.setenv("CONDA_PREFIX", shell_wrapper_unit)
    monkeypatch.setenv("CONDA_SHLVL", "1")
    monkeypatch.setenv("PATH", os.pathsep.join((*new_path_parts, os.environ["PATH"])))

    activator = CmdExeActivator()
    err = main_sourced("shell.cmd.exe", "reactivate")
    reactivate_result, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    with open(reactivate_result) as fh:
        reactivate_data = fh.read()
    rm_rf(reactivate_result)

    new_path_parts = activator._replace_prefix_in_path(
        shell_wrapper_unit, shell_wrapper_unit
    )
    assert reactivate_data == dals(
        """
    @CALL "%(deactivate1)s"
    @SET "PATH=%(new_path)s"
    @SET "CONDA_SHLVL=1"
    @SET "CONDA_PROMPT_MODIFIER=%(conda_prompt_modifier)s"
    @CALL "%(activate1)s"
    """
    ) % {
        "activate1": activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "activate.d",
                "activate1.bat",
            )
        ),
        "deactivate1": activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "deactivate.d",
                "deactivate1.bat",
            )
        ),
        "native_prefix": shell_wrapper_unit,
        "new_path": activator.pathsep_join(new_path_parts),
        "conda_prompt_modifier": get_prompt_modifier(shell_wrapper_unit),
    }

    err = main_sourced("shell.cmd.exe", "deactivate")
    deactivate_result, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    with open(deactivate_result) as fh:
        deactivate_data = fh.read()
    rm_rf(deactivate_result)

    new_path = activator.pathsep_join(
        activator._remove_prefix_from_path(shell_wrapper_unit)
    )
    e_deactivate_data = dals(
        """
    @SET "PATH=%(new_path)s"
    @CALL "%(deactivate1)s"
    @SET CONDA_PREFIX=
    @SET CONDA_DEFAULT_ENV=
    @SET CONDA_PROMPT_MODIFIER=
    @SET "CONDA_SHLVL=0"
    %(conda_exe_export)s
    """
    ) % {
        "new_path": new_path,
        "deactivate1": activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "deactivate.d",
                "deactivate1.bat",
            )
        ),
        "conda_exe_export": conda_exe_export,
    }
    assert deactivate_data == e_deactivate_data


def test_csh_basic(
    shell_wrapper_unit: str,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture,
) -> None:
    activator = CshActivator()
    make_dot_d_files(shell_wrapper_unit, activator.script_extension)

    err = main_sourced("shell.csh", *activate_args, shell_wrapper_unit)
    activate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path_parts = activator._add_prefix_to_path(shell_wrapper_unit)
    conda_exe_export, conda_exe_unset = get_scripts_export_unset_vars(activator)

    e_activate_data = dals(
        """
    set prompt='%(prompt)s';
    setenv PATH "%(new_path)s";
    setenv CONDA_PREFIX "%(native_prefix)s";
    setenv CONDA_SHLVL "1";
    setenv CONDA_DEFAULT_ENV "%(native_prefix)s";
    setenv CONDA_PROMPT_MODIFIER "%(conda_prompt_modifier)s";
    %(conda_exe_export)s;
    source "%(activate1)s";
    """
    ) % {
        "converted_prefix": activator.path_conversion(shell_wrapper_unit),
        "native_prefix": shell_wrapper_unit,
        "new_path": activator.pathsep_join(new_path_parts),
        "sys_executable": activator.path_conversion(sys.executable),
        "activate1": activator.path_conversion(
            join(shell_wrapper_unit, "etc", "conda", "activate.d", "activate1.csh")
        ),
        "prompt": get_prompt(shell_wrapper_unit),
        "conda_prompt_modifier": get_prompt_modifier(shell_wrapper_unit),
        "conda_exe_export": conda_exe_export,
    }
    assert activate_data == e_activate_data

    monkeypatch.setenv("CONDA_PREFIX", shell_wrapper_unit)
    monkeypatch.setenv("CONDA_SHLVL", "1")
    monkeypatch.setenv("PATH", os.pathsep.join((*new_path_parts, os.environ["PATH"])))

    activator = CshActivator()
    err = main_sourced("shell.csh", *reactivate_args)
    reactivate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path_parts = activator._replace_prefix_in_path(
        shell_wrapper_unit, shell_wrapper_unit
    )
    e_reactivate_data = dals(
        """
    source "%(deactivate1)s";
    set prompt='%(prompt)s';
    setenv PATH "%(new_path)s";
    setenv CONDA_SHLVL "1";
    setenv CONDA_PROMPT_MODIFIER "%(conda_prompt_modifier)s";
    source "%(activate1)s";
    """
    ) % {
        "prompt": get_prompt(shell_wrapper_unit),
        "conda_prompt_modifier": get_prompt_modifier(shell_wrapper_unit),
        "new_path": activator.pathsep_join(new_path_parts),
        "activate1": activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "activate.d",
                "activate1.csh",
            )
        ),
        "deactivate1": activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "deactivate.d",
                "deactivate1.csh",
            )
        ),
        "native_prefix": shell_wrapper_unit,
    }
    assert reactivate_data == e_reactivate_data

    err = main_sourced("shell.csh", *deactivate_args)
    deactivate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path = activator.pathsep_join(
        activator._remove_prefix_from_path(shell_wrapper_unit)
    )

    (
        conda_exe_export,
        conda_exe_unset,
    ) = get_scripts_export_unset_vars(activator)

    e_deactivate_data = dals(
        """
    setenv PATH "%(new_path)s";
    source "%(deactivate1)s";
    unsetenv CONDA_PREFIX;
    unsetenv CONDA_DEFAULT_ENV;
    unsetenv CONDA_PROMPT_MODIFIER;
    set prompt='%(prompt)s';
    setenv CONDA_SHLVL "0";
    %(conda_exe_export)s;
    """
    ) % {
        "new_path": new_path,
        "deactivate1": activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "deactivate.d",
                "deactivate1.csh",
            )
        ),
        "prompt": get_prompt(),
        "conda_exe_export": conda_exe_export,
    }
    assert deactivate_data == e_deactivate_data


def test_xonsh_basic(
    shell_wrapper_unit: str,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture,
) -> None:
    activator = XonshActivator()
    make_dot_d_files(shell_wrapper_unit, activator.script_extension)

    err = main_sourced("shell.xonsh", *activate_args, shell_wrapper_unit)
    activate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path_parts = activator._add_prefix_to_path(shell_wrapper_unit)
    conda_exe_export, conda_exe_unset = get_scripts_export_unset_vars(activator)
    e_activate_template = dals(
        """
    $PATH = '%(new_path)s'
    $CONDA_PREFIX = '%(native_prefix)s'
    $CONDA_SHLVL = '1'
    $CONDA_DEFAULT_ENV = '%(native_prefix)s'
    $CONDA_PROMPT_MODIFIER = '%(conda_prompt_modifier)s'
    %(conda_exe_export)s
    %(sourcer)s "%(activate1)s"
    """
    )
    e_activate_info = {
        "converted_prefix": activator.path_conversion(shell_wrapper_unit),
        "native_prefix": shell_wrapper_unit,
        "new_path": activator.pathsep_join(new_path_parts),
        "sys_executable": activator.path_conversion(sys.executable),
        "conda_exe_export": conda_exe_export,
        "conda_prompt_modifier": get_prompt_modifier(shell_wrapper_unit),
    }
    if on_win:
        e_activate_info["sourcer"] = "source-cmd --suppress-skip-message"
        e_activate_info["activate1"] = activator.path_conversion(
            join(shell_wrapper_unit, "etc", "conda", "activate.d", "activate1.bat")
        )
    else:
        e_activate_info["sourcer"] = "source-bash --suppress-skip-message -n"
        e_activate_info["activate1"] = activator.path_conversion(
            join(shell_wrapper_unit, "etc", "conda", "activate.d", "activate1.sh")
        )
    e_activate_data = e_activate_template % e_activate_info
    assert activate_data == e_activate_data

    monkeypatch.setenv("CONDA_PREFIX", shell_wrapper_unit)
    monkeypatch.setenv("CONDA_SHLVL", "1")
    monkeypatch.setenv("PATH", os.pathsep.join((*new_path_parts, os.environ["PATH"])))

    activator = XonshActivator()
    err = main_sourced("shell.xonsh", *reactivate_args)
    reactivate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path_parts = activator._replace_prefix_in_path(
        shell_wrapper_unit, shell_wrapper_unit
    )
    e_reactivate_template = dals(
        """
    %(sourcer)s "%(deactivate1)s"
    $PATH = '%(new_path)s'
    $CONDA_SHLVL = '1'
    $CONDA_PROMPT_MODIFIER = '%(conda_prompt_modifier)s'
    %(sourcer)s "%(activate1)s"
    """
    )
    e_reactivate_info = {
        "new_path": activator.pathsep_join(new_path_parts),
        "native_prefix": shell_wrapper_unit,
        "conda_prompt_modifier": get_prompt_modifier(shell_wrapper_unit),
    }
    if on_win:
        e_reactivate_info["sourcer"] = "source-cmd --suppress-skip-message"
        e_reactivate_info["activate1"] = activator.path_conversion(
            join(shell_wrapper_unit, "etc", "conda", "activate.d", "activate1.bat")
        )
        e_reactivate_info["deactivate1"] = activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "deactivate.d",
                "deactivate1.bat",
            )
        )
    else:
        e_reactivate_info["sourcer"] = "source-bash --suppress-skip-message -n"
        e_reactivate_info["activate1"] = activator.path_conversion(
            join(shell_wrapper_unit, "etc", "conda", "activate.d", "activate1.sh")
        )
        e_reactivate_info["deactivate1"] = activator.path_conversion(
            join(shell_wrapper_unit, "etc", "conda", "deactivate.d", "deactivate1.sh")
        )
    e_reactivate_data = e_reactivate_template % e_reactivate_info
    assert reactivate_data == e_reactivate_data

    err = main_sourced("shell.xonsh", *deactivate_args)
    deactivate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path = activator.pathsep_join(
        activator._remove_prefix_from_path(shell_wrapper_unit)
    )
    (
        conda_exe_export,
        conda_exe_unset,
    ) = get_scripts_export_unset_vars(activator)
    e_deactivate_template = dals(
        """
    $PATH = '%(new_path)s'
    %(sourcer)s "%(deactivate1)s"
    del $CONDA_PREFIX
    del $CONDA_DEFAULT_ENV
    del $CONDA_PROMPT_MODIFIER
    $CONDA_SHLVL = '0'
    %(conda_exe_export)s
    """
    )
    e_deactivate_info = {
        "new_path": new_path,
        "conda_exe_export": conda_exe_export,
    }
    if on_win:
        e_deactivate_info["sourcer"] = "source-cmd --suppress-skip-message"
        e_deactivate_info["deactivate1"] = activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "deactivate.d",
                "deactivate1.bat",
            )
        )
    else:
        e_deactivate_info["sourcer"] = "source-bash --suppress-skip-message -n"
        e_deactivate_info["deactivate1"] = activator.path_conversion(
            join(shell_wrapper_unit, "etc", "conda", "deactivate.d", "deactivate1.sh")
        )
    e_deactivate_data = e_deactivate_template % e_deactivate_info
    assert deactivate_data == e_deactivate_data


def test_fish_basic(
    shell_wrapper_unit: str,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture,
) -> None:
    activator = FishActivator()
    make_dot_d_files(shell_wrapper_unit, activator.script_extension)

    err = main_sourced("shell.fish", *activate_args, shell_wrapper_unit)
    activate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path_parts = activator._add_prefix_to_path(shell_wrapper_unit)
    conda_exe_export, conda_exe_unset = get_scripts_export_unset_vars(activator)
    e_activate_data = dals(
        """
    set -gx PATH "%(new_path)s";
    set -gx CONDA_PREFIX "%(native_prefix)s";
    set -gx CONDA_SHLVL "1";
    set -gx CONDA_DEFAULT_ENV "%(native_prefix)s";
    set -gx CONDA_PROMPT_MODIFIER "%(conda_prompt_modifier)s";
    %(conda_exe_export)s;
    source "%(activate1)s";
    """
    ) % {
        "converted_prefix": activator.path_conversion(shell_wrapper_unit),
        "native_prefix": shell_wrapper_unit,
        "new_path": activator.pathsep_join(new_path_parts),
        "sys_executable": activator.path_conversion(sys.executable),
        "activate1": activator.path_conversion(
            join(shell_wrapper_unit, "etc", "conda", "activate.d", "activate1.fish")
        ),
        "conda_exe_export": conda_exe_export,
        "conda_prompt_modifier": get_prompt_modifier(shell_wrapper_unit),
    }
    assert activate_data == e_activate_data

    monkeypatch.setenv("CONDA_PREFIX", shell_wrapper_unit)
    monkeypatch.setenv("CONDA_SHLVL", "1")
    monkeypatch.setenv("PATH", os.pathsep.join((*new_path_parts, os.environ["PATH"])))

    activator = FishActivator()
    err = main_sourced("shell.fish", *reactivate_args)
    reactivate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path_parts = activator._replace_prefix_in_path(
        shell_wrapper_unit, shell_wrapper_unit
    )
    e_reactivate_data = dals(
        """
    source "%(deactivate1)s";
    set -gx PATH "%(new_path)s";
    set -gx CONDA_SHLVL "1";
    set -gx CONDA_PROMPT_MODIFIER "%(conda_prompt_modifier)s";
    source "%(activate1)s";
    """
    ) % {
        "new_path": activator.pathsep_join(new_path_parts),
        "activate1": activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "activate.d",
                "activate1.fish",
            )
        ),
        "deactivate1": activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "deactivate.d",
                "deactivate1.fish",
            )
        ),
        "native_prefix": shell_wrapper_unit,
        "conda_prompt_modifier": get_prompt_modifier(shell_wrapper_unit),
    }
    assert reactivate_data == e_reactivate_data

    err = main_sourced("shell.fish", *deactivate_args)
    deactivate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path = activator.pathsep_join(
        activator._remove_prefix_from_path(shell_wrapper_unit)
    )
    (
        conda_exe_export,
        conda_exe_unset,
    ) = get_scripts_export_unset_vars(activator)
    e_deactivate_data = dals(
        """
    set -gx PATH "%(new_path)s";
    source "%(deactivate1)s";
    set -e CONDA_PREFIX;
    set -e CONDA_DEFAULT_ENV;
    set -e CONDA_PROMPT_MODIFIER;
    set -gx CONDA_SHLVL "0";
    %(conda_exe_export)s;
    """
    ) % {
        "new_path": new_path,
        "deactivate1": activator.path_conversion(
            join(
                shell_wrapper_unit,
                "etc",
                "conda",
                "deactivate.d",
                "deactivate1.fish",
            )
        ),
        "conda_exe_export": conda_exe_export,
    }
    assert deactivate_data == e_deactivate_data


def test_powershell_basic(
    shell_wrapper_unit: str,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture,
) -> None:
    activator = PowerShellActivator()
    make_dot_d_files(shell_wrapper_unit, activator.script_extension)

    err = main_sourced("shell.powershell", *activate_args, shell_wrapper_unit)
    activate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path_parts = activator._add_prefix_to_path(shell_wrapper_unit)
    conda_exe_export, conda_exe_unset = get_scripts_export_unset_vars(activator)
    e_activate_data = dals(
        """
    $Env:PATH = "%(new_path)s"
    $Env:CONDA_PREFIX = "%(prefix)s"
    $Env:CONDA_SHLVL = "1"
    $Env:CONDA_DEFAULT_ENV = "%(prefix)s"
    $Env:CONDA_PROMPT_MODIFIER = "%(conda_prompt_modifier)s"
    %(conda_exe_export)s
    . "%(activate1)s"
    """
    ) % {
        "prefix": shell_wrapper_unit,
        "new_path": activator.pathsep_join(new_path_parts),
        "sys_executable": sys.executable,
        "activate1": join(
            shell_wrapper_unit, "etc", "conda", "activate.d", "activate1.ps1"
        ),
        "conda_exe_export": conda_exe_export,
        "conda_prompt_modifier": get_prompt_modifier(shell_wrapper_unit),
    }
    assert activate_data == e_activate_data

    monkeypatch.setenv("CONDA_PREFIX", shell_wrapper_unit)
    monkeypatch.setenv("CONDA_SHLVL", "1")
    monkeypatch.setenv("PATH", os.pathsep.join((*new_path_parts, os.environ["PATH"])))

    activator = PowerShellActivator()
    err = main_sourced("shell.powershell", *reactivate_args)
    reactivate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path_parts = activator._replace_prefix_in_path(
        shell_wrapper_unit, shell_wrapper_unit
    )
    assert reactivate_data == dals(
        """
    . "%(deactivate1)s"
    $Env:PATH = "%(new_path)s"
    $Env:CONDA_SHLVL = "1"
    $Env:CONDA_PROMPT_MODIFIER = "%(conda_prompt_modifier)s"
    . "%(activate1)s"
    """
    ) % {
        "activate1": join(
            shell_wrapper_unit, "etc", "conda", "activate.d", "activate1.ps1"
        ),
        "deactivate1": join(
            shell_wrapper_unit,
            "etc",
            "conda",
            "deactivate.d",
            "deactivate1.ps1",
        ),
        "prefix": shell_wrapper_unit,
        "new_path": activator.pathsep_join(new_path_parts),
        "conda_prompt_modifier": get_prompt_modifier(shell_wrapper_unit),
    }

    err = main_sourced("shell.powershell", *deactivate_args)
    deactivate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path = activator.pathsep_join(
        activator._remove_prefix_from_path(shell_wrapper_unit)
    )

    assert deactivate_data == dals(
        """
    $Env:PATH = "%(new_path)s"
    . "%(deactivate1)s"
    $Env:CONDA_PREFIX = ""
    $Env:CONDA_DEFAULT_ENV = ""
    $Env:CONDA_PROMPT_MODIFIER = ""
    $Env:CONDA_SHLVL = "0"
    %(conda_exe_export)s
    """
    ) % {
        "new_path": new_path,
        "deactivate1": join(
            shell_wrapper_unit,
            "etc",
            "conda",
            "deactivate.d",
            "deactivate1.ps1",
        ),
        "conda_exe_export": conda_exe_export,
    }


def test_json_basic(
    shell_wrapper_unit: str,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture,
) -> None:
    activator = _build_activator_cls("posix+json")()
    make_dot_d_files(shell_wrapper_unit, activator.script_extension)

    err = main_sourced("shell.posix+json", *activate_args, shell_wrapper_unit)
    activate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path_parts = activator._add_prefix_to_path(shell_wrapper_unit)
    export_vars, unset_vars = activator.get_export_unset_vars(
        CONDA_PREFIX=shell_wrapper_unit,
        CONDA_SHLVL=1,
        CONDA_DEFAULT_ENV=shell_wrapper_unit,
        CONDA_PROMPT_MODIFIER=get_prompt_modifier(shell_wrapper_unit),
    )
    e_activate_data = {
        "path": {"PATH": list(new_path_parts)},
        "vars": {
            "export": export_vars,
            "set": {"PS1": get_prompt(shell_wrapper_unit)},
            "unset": unset_vars,
        },
        "scripts": {
            "activate": [
                activator.path_conversion(
                    join(
                        shell_wrapper_unit, "etc", "conda", "activate.d", "activate1.sh"
                    )
                ),
            ],
            "deactivate": [],
        },
    }
    assert json.loads(activate_data) == e_activate_data

    monkeypatch.setenv("CONDA_PREFIX", shell_wrapper_unit)
    monkeypatch.setenv("CONDA_SHLVL", "1")
    monkeypatch.setenv("PATH", os.pathsep.join((*new_path_parts, os.environ["PATH"])))

    activator = _build_activator_cls("posix+json")()
    err = main_sourced("shell.posix+json", *reactivate_args)
    reactivate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path_parts = activator._replace_prefix_in_path(
        shell_wrapper_unit, shell_wrapper_unit
    )
    e_reactivate_data = {
        "path": {"PATH": list(new_path_parts)},
        "vars": {
            "export": {
                "CONDA_SHLVL": 1,
                "CONDA_PROMPT_MODIFIER": get_prompt_modifier(shell_wrapper_unit),
            },
            "set": {"PS1": get_prompt(shell_wrapper_unit)},
            "unset": [],
        },
        "scripts": {
            "activate": [
                activator.path_conversion(
                    join(
                        shell_wrapper_unit,
                        "etc",
                        "conda",
                        "activate.d",
                        "activate1.sh",
                    )
                ),
            ],
            "deactivate": [
                activator.path_conversion(
                    join(
                        shell_wrapper_unit,
                        "etc",
                        "conda",
                        "deactivate.d",
                        "deactivate1.sh",
                    )
                ),
            ],
        },
    }
    assert json.loads(reactivate_data) == e_reactivate_data

    err = main_sourced("shell.posix+json", *deactivate_args)
    deactivate_data, stderr = capsys.readouterr()
    assert not stderr
    assert not err

    new_path = activator.pathsep_join(
        activator._remove_prefix_from_path(shell_wrapper_unit)
    )
    export_vars, unset_vars = activator.get_export_unset_vars(
        CONDA_SHLVL=0,
        CONDA_PREFIX=None,
        CONDA_DEFAULT_ENV=None,
        CONDA_PROMPT_MODIFIER=None,
    )
    e_deactivate_data = {
        "path": {"PATH": list(new_path)},
        "vars": {
            "export": export_vars,
            "set": {"PS1": get_prompt()},
            "unset": unset_vars,
        },
        "scripts": {
            "activate": [],
            "deactivate": [
                activator.path_conversion(
                    join(
                        shell_wrapper_unit,
                        "etc",
                        "conda",
                        "deactivate.d",
                        "deactivate1.sh",
                    )
                ),
            ],
        },
    }
    assert json.loads(deactivate_data) == e_deactivate_data


@pytest.fixture
def create_stackable_envs(tmp_env: TmpEnvFixture):
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
@pytest.mark.integration
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
def test_stacking(create_stackable_envs, auto_stack, stack, run, expected):
    which, envs = create_stackable_envs
    stack = filter(None, stack.split(","))
    expected = filter(None, expected.split(","))
    expected = list(chain.from_iterable(envs[env.strip()].paths for env in expected))
    assert (
        _run_command(
            f"conda config --set auto_stack {auto_stack}",
            *(f'conda activate "{envs[env.strip()].prefix}"' for env in stack),
            f'conda run -p "{envs[run.strip()].prefix}" {which}',
        )
        == expected
    )


def test_activate_and_deactivate_for_uninitialized_env(conda_cli):
    # Call activate (with and without env argument) and check that the proper error shows up
    with pytest.raises(CondaError) as conda_error:
        conda_cli("activate")
    assert conda_error.value.message.startswith(
        "Run 'conda init' before 'conda activate'"
    )
    with pytest.raises(CondaError) as conda_error:
        conda_cli("activate", "env")
    assert conda_error.value.message.startswith(
        "Run 'conda init' before 'conda activate'"
    )

    # Call deactivate and check that the proper error shows up
    with pytest.raises(CondaError) as conda_error:
        conda_cli("deactivate")
    assert conda_error.value.message.startswith(
        "Run 'conda init' before 'conda deactivate'"
    )


# The MSYS2_PATH tests are slightly unusual in two regards: firstly
# they stat(2) for potential directories which indicate which (of
# several) possible MSYS2 environments have been installed; secondly,
# conda will pass a Windows pathname prefix but conda-build will pass
# a Unix pathname prefix (in particular, an MSYS2 pathname).
MINGW_W64 = ["mingw-w64"]
UCRT64 = ["ucrt64"]
CLANG64 = ["clang64"]
MINGW64 = ["mingw64"]


@pytest.mark.skipif(not on_win, reason="windows-specific test")
@pytest.mark.parametrize(
    "create,expected,unexpected",
    [
        # No Library/* => Library/mingw-w64/bin
        pytest.param([], MINGW_W64, UCRT64, id="nothing"),
        # Library/mingw-w64 => Library/mingw-w64/bin
        pytest.param(MINGW_W64, MINGW_W64, UCRT64, id="legacy"),
        # Library/ucrt64 => Library/ucrt64/bin
        pytest.param(UCRT64, UCRT64 + MINGW_W64, CLANG64, id="ucrt64"),
        # Library/ucrt64 and Library/mingw-w64 => Library/ucrt64/bin
        pytest.param(
            UCRT64 + MINGW_W64,
            UCRT64 + MINGW_W64,
            CLANG64,
            id="ucrt64 legacy",
        ),
        # Library/clang64 and Library/mingw-w64 => Library/clang64/bin
        pytest.param(
            CLANG64 + MINGW_W64,
            CLANG64 + MINGW_W64,
            UCRT64,
            id="clang64 legacy",
        ),
        # Library/ucrt64 and Library/clang64 => Library/ucrt64/bin
        pytest.param(
            UCRT64 + CLANG64,
            UCRT64 + MINGW_W64,
            CLANG64,
            id="ucrt64 clang64",
        ),
        # Library/clang64 and Library/mingw64 => Library/clang64/bin
        pytest.param(
            CLANG64 + MINGW64,
            CLANG64 + MINGW_W64,
            MINGW64,
            id="clang64 mingw64",
        ),
        # Library/mingw64 and Library/mingw-w64 => Library/mingw64/bin
        pytest.param(
            MINGW64 + MINGW_W64,
            MINGW64 + MINGW_W64,
            UCRT64,
            id="mingw64 legacy",
        ),
    ],
)
@pytest.mark.parametrize("activator_cls", [CmdExeActivator, PowerShellActivator])
def test_MSYS2_PATH(
    tmp_env: TmpEnvFixture,
    create: list[str],
    expected: list[str],
    unexpected: list[str],
    activator_cls: type[_Activator],
) -> None:
    with tmp_env() as prefix:
        # create MSYS2 directories
        (library := prefix / "Library").mkdir()
        for path in create:
            (library / path / "bin").mkdir(parents=True)

        activator = activator_cls()
        paths = activator._replace_prefix_in_path(str(prefix), str(prefix))

        # ensure expected bin directories are included in %PATH%/$env:PATH
        for path in expected:
            assert activator.path_conversion(str(library / path / "bin")) in paths

        # ensure unexpected bin directories are not included in %PATH%/$env:PATH
        for path in unexpected:
            assert activator.path_conversion(str(library / path / "bin")) not in paths


@pytest.mark.parametrize("force_uppercase_boolean", [True, False])
def test_force_uppercase(monkeypatch: MonkeyPatch, force_uppercase_boolean):
    monkeypatch.setenv("CONDA_ENVVARS_FORCE_UPPERCASE", force_uppercase_boolean)
    reset_context()
    assert context.envvars_force_uppercase is force_uppercase_boolean

    activator = PosixActivator()
    export_vars, unset_vars = activator.get_export_unset_vars(
        one=1,
        TWO=2,
        three=None,
        FOUR=None,
    )

    # preserved case vars present if  keep_case is True
    assert ("one" in export_vars) is not force_uppercase_boolean
    assert ("three" in unset_vars) is not force_uppercase_boolean

    # vars uppercased when keep_case is False
    assert ("ONE" in export_vars) is force_uppercase_boolean
    assert ("THREE" in unset_vars) is force_uppercase_boolean

    # original uppercase
    assert "TWO" in export_vars
    assert "FOUR" in unset_vars


@pytest.mark.parametrize("force_uppercase_boolean", [True, False])
def test_metavars_force_uppercase(
    mocker: MockerFixture, monkeypatch: MonkeyPatch, force_uppercase_boolean: bool
):
    monkeypatch.setenv("CONDA_ENVVARS_FORCE_UPPERCASE", force_uppercase_boolean)
    reset_context()
    assert context.envvars_force_uppercase is force_uppercase_boolean

    returned_dict = {
        "ONE": "1",
        "two": "2",
        "three": None,
        "FOUR": None,
        "five": "a/path/to/something",
        "SIX": "a\\path",
    }
    mocker.patch(
        "conda.base.context.Context.conda_exe_vars_dict",
        new_callable=mocker.PropertyMock,
        return_value=returned_dict,
    )
    assert context.conda_exe_vars_dict == returned_dict

    activator = PosixActivator()
    export_vars, unset_vars = activator.get_export_unset_vars()

    # preserved case vars present if keep_case is True
    assert ("two" in export_vars) is not force_uppercase_boolean
    assert ("three" in unset_vars) is not force_uppercase_boolean
    assert ("five" in export_vars) is not force_uppercase_boolean

    # vars uppercased when keep_case is False
    assert ("TWO" in export_vars) is force_uppercase_boolean
    assert ("THREE" in unset_vars) is force_uppercase_boolean

    # original uppercase
    assert "ONE" in export_vars
    assert "FOUR" in unset_vars
    assert "SIX" in export_vars


@pytest.mark.parametrize(
    "function,raises",
    [
        ("path_identity", TypeError),
    ],
)
def test_deprecations(function: str, raises: type[Exception] | None) -> None:
    raises_context = pytest.raises(raises) if raises else nullcontext()
    with pytest.deprecated_call(), raises_context:
        getattr(activate, function)()
