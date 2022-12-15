# SPDX-FileCopyrightText: © 2012 Continuum Analytics, Inc. <http://continuum.io>
# SPDX-FileCopyrightText: © 2017 Anaconda, Inc. <https://www.anaconda.com>
# SPDX-License-Identifier: BSD-3-Clause
from argparse import Namespace, ArgumentParser

from ..notices import core as notices


def execute(args: Namespace, _: ArgumentParser):
    """
    Command that retrieves channel notifications, caches them and displays them.
    """
    channel_notice_set = notices.retrieve_notices()

    notices.display_notices(channel_notice_set)
