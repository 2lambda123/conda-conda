#!/usr/bin/env bash

set -o errtrace -o pipefail -o errexit

eval "$(sudo ./devenv/bin/python -m conda init --dev bash)"
conda-build tests/test-recipes/activate_deactivate_package
pytest -m "integration" -v --splits ${TEST_SPLITS} --group=${TEST_GROUP}
python -m conda.common.io
