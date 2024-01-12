# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from pathlib import Path

from conda.testing import CondaCLIFixture, TmpEnvFixture
from conda.testing.integration import package_is_installed


def test_install_track_features_upgrade(
    solver_classic: None,  # features not supported in libmamba
    test_recipes_channel: Path,
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    # install an older track_feature
    with tmp_env("track_feature=1.0") as prefix:
        assert package_is_installed(prefix, "track_feature=1.0")
        assert not package_is_installed(prefix, "feature")

        # install package that depends on track_feature
        conda_cli("install", f"--prefix={prefix}", "feature", "--yes")
        assert package_is_installed(prefix, "track_feature=1.0")
        assert package_is_installed(prefix, "feature=1.0")

        # install a newer track_feature
        conda_cli("install", f"--prefix={prefix}", "track_feature=2.0", "--yes")
        assert package_is_installed(prefix, "track_feature=2.0")
        assert package_is_installed(prefix, "feature=2.0")


def test_install_track_features_downgrade(
    solver_classic: None,  # features not supported in libmamba
    test_recipes_channel: Path,
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    # install a newer track_feature
    with tmp_env("track_feature=2.0") as prefix:
        assert package_is_installed(prefix, "track_feature=2.0")
        assert not package_is_installed(prefix, "feature")

        # install package that depends on track_feature
        conda_cli("install", f"--prefix={prefix}", "feature", "--yes")
        assert package_is_installed(prefix, "track_feature=2.0")
        assert package_is_installed(prefix, "feature=2.0")

        # install an older track_feature
        conda_cli("install", f"--prefix={prefix}", "track_feature=1.0", "--yes")
        assert package_is_installed(prefix, "track_feature=1.0")
        assert package_is_installed(prefix, "feature=1.0")


def test_remove_features_upgrade(
    solver_classic: None,  # features not supported in libmamba
    test_recipes_channel: Path,
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    # install an older track_feature
    with tmp_env("track_feature=1.0", "feature") as prefix:
        assert package_is_installed(prefix, "track_feature=1.0")
        assert package_is_installed(prefix, "feature=1.0")

        # remove the track_feature1, expecting to see track_feature2 be installed instead
        conda_cli(
            "remove", f"--prefix={prefix}", "--features", "track_feature1", "--yes"
        )
        assert package_is_installed(prefix, "track_feature=2.0")
        assert package_is_installed(prefix, "feature=2.0")


def test_remove_features_downgrade(
    solver_classic: None,  # features not supported in libmamba
    test_recipes_channel: Path,
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    # install a newer track_feature
    with tmp_env("track_feature=2.0", "feature") as prefix:
        assert package_is_installed(prefix, "track_feature=2.0")
        assert package_is_installed(prefix, "feature=2.0")

        # remove the track_feature2, expecting to see track_feature1 be installed instead
        conda_cli(
            "remove", f"--prefix={prefix}", "--features", "track_feature2", "--yes"
        )
        assert package_is_installed(prefix, "track_feature=1.0")
        assert package_is_installed(prefix, "feature=1.0")
