# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
Definition of specific return types for use when defining a conda plugin hook.

Each type corresponds to the plugin hook for which it is used.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NamedTuple, Protocol

from requests.auth import AuthBase

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from typing import Any, Callable, ContextManager, Union

    from ..common.configuration import Parameter
    from ..common.io import ProgressBarBase
    from ..core.solve import Solver
    from ..models.match_spec import MatchSpec
    from ..models.records import PackageRecord


@dataclass
class CondaSubcommand:
    """
    Return type to use when defining a conda subcommand plugin hook.

    For details on how this is used, see
    :meth:`~conda.plugins.hookspec.CondaSpecs.conda_subcommands`.

    :param name: Subcommand name (e.g., ``conda my-subcommand-name``).
    :param summary: Subcommand summary, will be shown in ``conda --help``.
    :param action: Callable that will be run when the subcommand is invoked.
    :param configure_parser: Callable that will be run when the subcommand parser is initialized.
    """

    name: str
    summary: str
    action: Callable[
        [Namespace | tuple[str]],  # arguments
        int | None,  # return code
    ]
    configure_parser: Callable[[ArgumentParser], None] | None = field(default=None)


class CondaVirtualPackage(NamedTuple):
    """
    Return type to use when defining a conda virtual package plugin hook.

    For details on how this is used, see
    :meth:`~conda.plugins.hookspec.CondaSpecs.conda_virtual_packages`.

    :param name: Virtual package name (e.g., ``my_custom_os``).
    :param version: Virtual package version (e.g., ``1.2.3``).
    :param build: Virtual package build string (e.g., ``x86_64``).
    """

    name: str
    version: str | None
    build: str | None


class CondaSolver(NamedTuple):
    """
    Return type to use when defining a conda solver plugin hook.

    For details on how this is used, see
    :meth:`~conda.plugins.hookspec.CondaSpecs.conda_solvers`.

    :param name: Solver name (e.g., ``custom-solver``).
    :param backend: Type that will be instantiated as the solver backend.
    """

    name: str
    backend: type[Solver]


class CondaPreCommand(NamedTuple):
    """
    Return type to use when defining a conda pre-command plugin hook.

    For details on how this is used, see
    :meth:`~conda.plugins.hookspec.CondaSpecs.conda_pre_commands`.

    :param name: Pre-command name (e.g., ``custom_plugin_pre_commands``).
    :param action: Callable which contains the code to be run.
    :param run_for: Represents the command(s) this will be run on (e.g. ``install`` or ``create``).
    """

    name: str
    action: Callable[[str], None]
    run_for: set[str]


class CondaPostCommand(NamedTuple):
    """
    Return type to use when defining a conda post-command plugin hook.

    For details on how this is used, see
    :meth:`~conda.plugins.hookspec.CondaSpecs.conda_post_commands`.

    :param name: Post-command name (e.g., ``custom_plugin_post_commands``).
    :param action: Callable which contains the code to be run.
    :param run_for: Represents the command(s) this will be run on (e.g. ``install`` or ``create``).
    """

    name: str
    action: Callable[[str], None]
    run_for: set[str]


class ChannelNameMixin:
    """
    Class mixin to make all plugin implementations compatible, e.g. when they
    use an existing (e.g. 3rd party) requests authentication handler.

    Please use the concrete :class:`~conda.plugins.types.ChannelAuthBase`
    in case you're creating an own implementation.
    """

    def __init__(self, channel_name: str, *args, **kwargs):
        self.channel_name = channel_name
        super().__init__(*args, **kwargs)


class ChannelAuthBase(ChannelNameMixin, AuthBase):
    """
    Base class that we require all plugin implementations to use to be compatible.

    Authentication is tightly coupled with individual channels. Therefore, an additional
    ``channel_name`` property must be set on the ``requests.auth.AuthBase`` based class.
    """


class CondaAuthHandler(NamedTuple):
    """
    Return type to use when the defining the conda auth handlers hook.

    :param name: Name (e.g., ``basic-auth``). This name should be unique
                 and only one may be registered at a time.
    :param handler: Type that will be used as the authentication handler
                    during network requests.
    """

    name: str
    handler: type[ChannelAuthBase]


class CondaHealthCheck(NamedTuple):
    """
    Return type to use when defining conda health checks plugin hook.
    """

    name: str
    action: Callable[[str, bool], None]


@dataclass
class CondaPreSolve:
    """
    Return type to use when defining a conda pre-solve plugin hook.

    For details on how this is used, see
    :meth:`~conda.plugins.hookspec.CondaSpecs.conda_pre_solves`.

    :param name: Pre-solve name (e.g., ``custom_plugin_pre_solve``).
    :param action: Callable which contains the code to be run.
    """

    name: str
    action: Callable[[frozenset[MatchSpec], frozenset[MatchSpec]], None]


@dataclass
class CondaPostSolve:
    """
    Return type to use when defining a conda post-solve plugin hook.

    For details on how this is used, see
    :meth:`~conda.plugins.hookspec.CondaSpecs.conda_post_solves`.

    :param name: Post-solve name (e.g., ``custom_plugin_post_solve``).
    :param action: Callable which contains the code to be run.
    """

    name: str
    action: Callable[[str, tuple[PackageRecord, ...], tuple[PackageRecord, ...]], None]


@dataclass
class CondaSetting:
    """
    Return type to use when defining a conda setting plugin hook.

    For details on how this is used, see
    :meth:`~conda.plugins.hookspec.CondaSpecs.conda_settings`.

    :param name: name of the setting (e.g., ``config_param``)
    :param description: description of the setting that should be targeted
                        towards users of the plugin
    :param parameter: Parameter instance containing the setting definition
    :param aliases: alternative names of the setting
    """

    name: str
    description: str
    parameter: Parameter
    aliases: tuple[str, ...] = tuple()


if TYPE_CHECKING:
    DetailRecord = dict[str, Union[str, int, bool]]


class ReporterHandlerBase(ABC):
    """
    Base class for all reporter handlers.

    Each method represents a component of the output that can be rendered. Some components, like
    :meth:`~ReporterHandlersBase.detail_view` are returned as strings whereas others like
    ``ReporterHandlerBase.progress_bar`` are objects with various methods that intended to be
    used interactively.
    """

    def render(self, data: Any, **kwargs) -> str:
        return str(data)

    @abstractmethod
    def detail_view(self, data: dict[str, str | int | bool], **kwargs) -> str:
        """
        Render the output in a "tabular" format.
        """

    @abstractmethod
    def envs_list(self, data, **kwargs) -> str:
        """
        Render a list of environments
        """

    @abstractmethod
    def progress_bar(
        self, description: str, render: Callable, **kwargs
    ) -> ProgressBarBase:
        """
        Return a :class:`conda.common.io.ProgressBarBase` object to use a progress bar
        """

    @classmethod
    def progress_bar_context_manager(cls) -> ContextManager:
        """
        Returns a null context by default but allows plugins to define their own if necessary
        """
        return nullcontext()


@dataclass
class CondaReporterHandler:
    """
    Return type to use when defining a conda reporter handler plugin hook.

    For details on this is used, see
    :meth:`~conda.plugins.hookspec.CondaSpecs.conda_reporter_handler`.

    :param name: name of the reporter handler (e.g., ``email_reporter``)
                 This is how the reporter handler with be references in configuration files.
    :param description: short description of what the reporter handler does
    :param handler: implementation of ``ReporterHandlerBase`` that will be used as the
                    reporter handler
    """

    name: str
    description: str
    handler: ReporterHandlerBase


class OutputRenderer(Protocol):
    """
    Protocol describing how the output render function should look.
    """

    def __call__(self, renderable: str, **kwargs: Any) -> None:
        """
        Function that accepts a ``renderable`` as a string and any number of keyword arguments. It
        is not expected to return anything.
        """


@dataclass
class CondaOutputHandler:
    """
    Return type to use when defining a conda output handler plugin hook.

    For details on this is used, see
    :meth:`~conda.plugins.hookspec.CondaSpecs.conda_output_handler`.

    :param name: name of the output handler (e.g., ``email_reporter``)
                 This is how the reporter handler with be references in configuration files.
    :param description: short description of what the reporter handler does
    :param render: a callable object accepting a ``str`` as the first argument and ``**kwargs``.
                   See :class:`~conda.plugins.types.OutputRenderer` for more information.
    """

    name: str
    description: str
    render: OutputRenderer
