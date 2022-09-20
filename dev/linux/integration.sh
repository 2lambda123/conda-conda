#!/usr/bin/env bash

set -o errtrace -o pipefail -o errexit

TEST_SPLITS="${TEST_SPLITS:-1}"
TEST_GROUP="${TEST_GROUP:-1}"

# TODO: once #11865 is merged this can be updated
SCRIPT="$(sudo /opt/conda/bin/conda init bash --dev)"
eval "${SCRIPT}" >/dev/null
conda info
conda clean -ayq

sudo /opt/conda/bin/conda install -yq conda-build
# TODO: make this a pytest fixture
conda build tests/test-recipes/activate_deactivate_package tests/test-recipes/pre_link_messages_package

pytest -m "integration" -v --splits ${TEST_SPLITS} --group=${TEST_GROUP}
python -m conda.common.io
