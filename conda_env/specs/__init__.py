# -*- coding: utf-8 -*-
# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause

import os

from conda.exceptions import (
    EnvironmentFileExtensionNotValid,
    EnvironmentFileNotFound,
    SpecNotFound,
)
from conda.gateways.connection.session import CONDA_SESSION_SCHEMES

from .binstar import BinstarSpec
from .notebook import NotebookSpec
from .requirements import RequirementsSpec
from .yaml_file import YamlFileSpec


def detect(**kwargs):
    filename = kwargs.get("filename")

    if filename is not None:
        # Check extensions
        all_valid_exts = YamlFileSpec.extensions.union(RequirementsSpec.extensions)
        fname, ext = os.path.splitext(filename)

        # First check if file exists and test the known valid extension for specs
        file_exists = (
            os.path.isfile(filename) or filename.split("://", 1)[0] in CONDA_SESSION_SCHEMES
        )
        if file_exists:
            if ext == "" or ext not in all_valid_exts:
                raise EnvironmentFileExtensionNotValid(filename or None)
            elif ext in YamlFileSpec.extensions:
                specs = [YamlFileSpec]
            elif ext in RequirementsSpec.extensions:
                specs = [RequirementsSpec]
        else:
            raise EnvironmentFileNotFound(filename=filename)
    else:
        specs = [NotebookSpec, BinstarSpec]

    # Check specifications
    spec_instances = []
    for SpecClass in specs:
        spec = SpecClass(**kwargs)
        spec_instances.append(spec)
        if spec.can_handle():
            return spec

    raise SpecNotFound(build_message(spec_instances))


def build_message(spec_instances):
    binstar_spec = next((s for s in spec_instances if isinstance(s, BinstarSpec)), None)
    if binstar_spec:
        return binstar_spec.msg
    else:
        return "\n".join([s.msg for s in spec_instances if s.msg is not None])
