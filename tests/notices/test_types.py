# -*- coding: utf-8 -*-
# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause

import pytest

from conda.notices.types import ChannelNoticeResponse

from .conftest import get_test_notices


def test_channel_notice_response():
    """
    Tests a normal invocation of the ChannelNoticeResponse class
    """
    messages = tuple(f"Test {idx}" for idx in range(1, 4, 1))
    expected_num_notices = len(messages)
    json_data = get_test_notices(messages)

    chn_ntc_resp = ChannelNoticeResponse("http://localhost", "local", json_data)

    notices = chn_ntc_resp.notices

    assert len(notices) == expected_num_notices


def test_channel_notice_response_date_parse_error():
    """
    Test a creation of the ChannelNoticeResponse object where we pass in bad values for
     "created_at" and "level" and make sure the appropriate defaults are there.
    """
    messages = tuple(f"Test {idx}" for idx in range(1, 4, 1))
    json_data = get_test_notices(messages)
    json_data["notices"][0]["created_at"] = "Not a valid datetime string"
    json_data["notices"][0]["level"] = "Not a valid level"

    chn_ntc_resp = ChannelNoticeResponse("http://localhost", "local", json_data)

    notices = chn_ntc_resp.notices

    assert notices[0].created_at is None
    assert notices[0].level.value == "info"
