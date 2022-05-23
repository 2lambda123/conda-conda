# -*- coding: utf-8 -*-
# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause

from unittest.mock import patch

import requests

from conda.notices.main import display_notices

from conda.testing.notices.helpers import add_resp_to_mock


def test_get_channel_notice_response_timeout_error(
    notices_cache_dir, notices_mock_http_session_get
):
    """
    Tests the timeout error case for the get_channel_notice_response function
    """
    with patch("conda.notices.http.logger") as mock_logger:
        notices_mock_http_session_get.side_effect = requests.exceptions.Timeout

        display_notices()

        assert len(mock_logger.mock_calls) == 2

        for mock_call in mock_logger.mock_calls:
            for arg in mock_call.args:
                assert "Request timed out for channel" in arg


def test_get_channel_notice_response_malformed_json(
    notices_cache_dir, notices_mock_http_session_get
):
    """
    Tests malformed json error case for the get_channel_notice_response function
    """
    messages = ("hello", "hello 2")
    with patch("conda.notices.http.logger") as mock_logger:
        add_resp_to_mock(notices_mock_http_session_get, 200, messages, raise_exc=True)

        display_notices()

        assert len(mock_logger.mock_calls) == 2

        expected_log_mesgs = (
            "Unable to parse JSON data",
            "Received 404 when trying to GET",
        )

        for expected, mock_call in zip(expected_log_mesgs, mock_logger.mock_calls):
            for arg in mock_call.args:
                assert expected in arg
