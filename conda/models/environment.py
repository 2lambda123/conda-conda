"""
Models to specify input variables for the creation of conda environments

This could actually be merged with conda.core.prefix_data. They kind of have the same kind of scope.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from ..base.constants import PREFIX_MAGIC_FILE, PREFIX_STATE_FILE, ChannelPriority
from ..base.context import context, locate_prefix_by_name
from ..common.serialize import yaml_safe_load
from ..core.prefix_data import PrefixData
from ..core.solve import get_pinned_specs
from ..exceptions import DirectoryNotACondaEnvironmentError, DirectoryNotFoundError
from ..history import History
from .channel import Channel
from .match_spec import MatchSpec

if TYPE_CHECKING:
    from os import PathLike
    from typing import Any, Iterable

    from ..models.records import PrefixRecord

log = getLogger(__name__)


@dataclass
class SolverOptions:
    explicit: bool = False
    solver: str | None = None
    channel_priority: ChannelPriority = ChannelPriority.STRICT

    def __post_init__(self):
        if self.solver is None:
            self.solver = context.solver

    def to_dict(self):
        return {
            "explicit": self.explicit,
            "solver": self.solver,
            "channel_priority": self.channel_priority,
        }


@dataclass
class ChannelOptions:
    repodata_fns: str | Iterable[str] | None = None

    def __post_init__(self):
        if self.repodata_fns is None:
            self.repodata_fns = context.repodata_fns
        elif isinstance(self.repodata_fns, str):
            self.repodata_fns = [self.repodata_fns]

    def to_dict(self):
        return {
            "repodata_fns": self.repodata_fns,
        }


@dataclass
class Environment:
    _default_filename: ClassVar[str] = "conda.environment.yaml"
    _max_supported_version: ClassVar[int] = 2

    version: int = _max_supported_version
    name: str | None = None
    prefix: PathLike | None = None
    description: str | None = None
    last_modified: str | None = None
    channels: Iterable[Channel | str] | None = None
    channel_options: ChannelOptions = None
    requirements: Iterable[MatchSpec | str] | None = None
    constraints: Iterable[MatchSpec | str] | None = None
    solver_options: SolverOptions | None = None
    configuration: dict[str, Any] | None = None
    variables: dict[str, str] | None = None

    def __post_init__(self):
        if self.version > self._max_supported_version:
            raise ValueError(
                f"This conda version only supports schema versions up to "
                f"{self._max_supported_version}, but this one is version {self.version}. "
                "Try updating to a more recent conda to handle this input."
            )
        if self.name and not self.prefix:
            self.prefix = Path(locate_prefix_by_name(self.name))
        elif self.prefix:
            self.prefix = Path(self.prefix)
            if not self.name:
                self.name = self.prefix.name
        elif not self.name and not self.prefix:
            raise ValueError("'Environment' needs either 'name' or 'prefix'.")
        self.channels = [
            Channel(channel) for channel in self.channels or context.channels
        ]
        self.requirements = [MatchSpec(spec) for spec in self.requirements or ()]
        self.constraints = [MatchSpec(spec) for spec in self.constraints or ()]
        if self.channel_options is None:
            self.channel_options = ChannelOptions()
        if self.solver_options is None:
            self.solver_options = SolverOptions()

        self._prefix_data = None

    @classmethod
    def merge(cls, *environments: Environment) -> Environment:
        """
        Keeps first name and/or prefix. Both if their basename match. Otherwise name wins.
        Keeps first description, channel_options, solver_options.
        Keeps max last_modified.
        Concatenates and deduplicates requirements and constraints.
        Reduces configuration and variables (last key wins).
        """
        name = None
        prefix = None
        names = [env.name for env in environments if env.name]
        prefixes = [env.prefix for env in environments if env.prefix]
        if names:
            name = names[0]
            if len(names) > 1:
                log.warning("Picking first environment name %s", name)
        if prefixes:
            prefix = prefixes[0]
            if len(prefixes) > 1:
                log.warning("Picking first environment prefix %s", prefix)
        if name and prefix and name != prefix.name:
            log.warning("Picked name %s and prefix %s do not match. Overriding prefix")
            prefix = None
        description = next(
            (env.description for env in environments if env.description), None
        )
        channel_options = next(
            (env.channel_options for env in environments if env.channel_options), None
        )
        solver_options = next(
            (env.solver_options for env in environments if env.solver_options), None
        )
        last_modified = max([env.last_modified or 0 for env in environments])
        channels = list(dict.fromkeys(chain(env.channels for env in environments)))
        requirements = list(
            dict.fromkeys(chain(env.requirements for env in environments))
        )
        constraints = list(
            dict.fromkeys(chain(env.constraints for env in environments))
        )
        configuration = {
            k: v for env in environments for (k, v) in env.configuration.items()
        }
        variables = {k: v for env in environments for (k, v) in env.variables.items()}
        return cls(
            name=name,
            prefix=prefix,
            description=description,
            last_modified=last_modified,
            channels=channels,
            channel_options=channel_options,
            requirements=requirements,
            constraints=constraints,
            solver_options=solver_options,
            configuration=configuration,
            variables=variables,
        )

    @classmethod
    def from_prefix(cls, prefix: PathLike) -> Environment:
        prefix = Path(prefix)
        if not prefix.is_dir():
            raise DirectoryNotFoundError(f"Prefix {prefix} is not a directory!")
        if (prefix / "conda-meta" / cls._default_filename).is_file():
            return cls.from_conda_meta(
                prefix / "conda-meta" / cls._default_filename, check_exists=False
            )

        if not (prefix / PREFIX_MAGIC_FILE).is_file():
            raise DirectoryNotACondaEnvironmentError(prefix)

        # This is an import from an old "history-only" conda environment

        name = prefix.name
        channels = (
            context.channels
        )  # TODO: Check with channels coming from PrefixData info?
        channel_options = ChannelOptions()  # TODO: Check if this is saved anywhere
        last_modified = (prefix / PREFIX_MAGIC_FILE).stat().st_mtime
        requirements = list(History(prefix).get_requested_specs_map().values())
        constraints = get_pinned_specs(prefix)
        solver_options = SolverOptions()  # TODO: Check if this is saved anywhere
        if (prefix / "condarc").is_file():
            configuration = yaml_safe_load(prefix / "condarc")
        if (prefix / PREFIX_STATE_FILE).is_file():
            variables = json.loads((prefix / PREFIX_STATE_FILE).read_text()).get(
                "env_vars"
            )
        return cls(
            name=name,
            prefix=prefix,
            description=f"Imported on {datetime.now()}",
            last_modified=last_modified,
            channels=channels,
            channel_options=channel_options,
            requirements=requirements,
            constraints=constraints,
            solver_options=solver_options,
            configuration=configuration,
            variables=variables,
        )

    @classmethod
    def from_conda_meta(cls, path: PathLike, check_exists: bool = True):
        path = Path(path)
        if check_exists and not path.is_file():
            raise OSError(f"'{cls._default_filename}' file not found at {path}")
        with path.open() as f:
            data = yaml_safe_load(f)
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "version": self.version,
            "name": self.name,
            "prefix": str(self.prefix),
            "channels": self.channels,
            "channel_options": self.channel_options.to_dict(),
            "solver_options": self.solver_options.to_dict(),
        }
        if self.description:
            data["description"] = self.description
        if self.requirements:
            data["requirements"] = [str(spec) for spec in self.requirements]
        if self.constraints:
            data["constraints"] = [str(spec) for spec in self.constraints]
        if self.configuration:
            data["configuration"] = self.configuration
        if self.variables:
            data["variables"] = self.variables
        data["last_modified"] = datetime.now()
        return data

    def installed(self) -> Iterable[PrefixRecord]:
        if self._prefix_data is None:
            self._prefix_data = PrefixData(self.prefix)
        yield from self._prefix_data.iter_records()
