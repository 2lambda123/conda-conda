#!/usr/bin/env bash

set -o errtrace -o pipefail -o errexit

TEST_SPLITS="${TEST_SPLITS:-1}"
TEST_GROUP="${TEST_GROUP:-1}"

conda info
conda run --name conda-tests pytest -m "not integration and not installed" -vv --splits ${TEST_SPLITS} --group=${TEST_GROUP}
