# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import json
from importlib.metadata import version
from logging import getLogger

import pytest

from conda.base.context import context
from conda.common.io import stderr_log_level
from conda.core.solve import Solver
from conda.exceptions import DryRunExit
from conda.testing import CondaCLIFixture, TmpEnvFixture
from conda.testing.integration import TEST_LOG_LEVEL
from conda.testing.solver_helpers import SolverTests

log = getLogger(__name__)
stderr_log_level(TEST_LOG_LEVEL, "conda")
stderr_log_level(TEST_LOG_LEVEL, "requests")


class TestClassicSolver(SolverTests):
    @property
    def solver_class(self) -> type[Solver]:
        return Solver


class TestLibMambaSolver(SolverTests):
    @property
    def solver_class(self) -> type[Solver]:
        from conda_libmamba_solver.solver import LibMambaSolver

        return LibMambaSolver

    @property
    def tests_to_skip(self):
        return {
            "conda-libmamba-solver does not support features": [
                "test_iopro_mkl",
                "test_iopro_nomkl",
                "test_mkl",
                "test_accelerate",
                "test_scipy_mkl",
                "test_pseudo_boolean",
                "test_no_features",
                "test_surplus_features_1",
                "test_surplus_features_2",
                "test_remove",
                # this one below only fails reliably on windows;
                # it passes Linux on CI, but not locally?
                "test_unintentional_feature_downgrade",
            ],
        }


@pytest.mark.integration
@pytest.mark.usefixtures("parametrized_solver_fixture")
@pytest.mark.xfail(
    context.solver == "libmamba" and version("conda_libmamba_solver") <= "24.1.0",
    reason="Removing using wildcards is not available in older versions of the libmamba solver.",
)
def test_remove_globbed_package_names(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    log.error(f"libmamba-solver version: {version('conda_libmamba_solver')}")
    with tmp_env("zlib", "ca-certificates") as prefix:
        stdout, stderr, _ = conda_cli(
            "remove",
            "--yes",
            f"--prefix={prefix}",
            "*lib*",
            "--dry-run",
            "--json",
            f"--solver={context.solver}",
            raises=DryRunExit,
        )
        log.info(stdout)
        log.info(stderr)
        data = json.loads(stdout)
        assert data.get("success")
        assert any(pkg["name"] == "zlib" for pkg in data["actions"]["UNLINK"])
        if "LINK" in data["actions"]:
            assert all(pkg["name"] != "zlib" for pkg in data["actions"]["LINK"])
        # if ca-certificates is in the unlink list,
        # it should also be in the link list (reinstall)
        for package in data["actions"]["UNLINK"]:
            if package["name"] == "ca-certificates":
                assert any(
                    pkg["name"] == "ca-certificates" for pkg in data["actions"]["LINK"]
                )
