# -*- coding: utf-8 -*-
# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
import pytest

from conda.notices import main as notices

from conda.testing.notices.helpers import (
    add_resp_to_mock,
    notices_decorator_assert_message_in_stdout,
    DummyArgs,
)


@pytest.mark.parametrize("status_code", (200, 404, 500))
def test_display_notices_happy_path(
    status_code, capsys, notices_cache_dir, notices_mock_http_session_get
):
    """
    Happy path for displaying notices. We test two error codes to make sure we get
    display that we assume
    """
    messages = ("Test One", "Test Two")
    add_resp_to_mock(notices_mock_http_session_get, status_code, messages)

    notices.display_notices()
    captured = capsys.readouterr()

    assert captured.err == ""

    for message in messages:
        if status_code < 300:
            assert message in captured.out
        else:
            assert message not in captured.out


def test_notices_decorator(capsys, notices_cache_dir, notices_mock_http_session_get):
    """
    Create a dummy function to wrap with our notices decorator and test it with
    two test messages.
    """
    messages = ("Test One", "Test Two")
    add_resp_to_mock(notices_mock_http_session_get, 200, messages)
    dummy_mesg = "Dummy mesg"

    @notices.notices
    def dummy(args, parser):
        print(dummy_mesg)

    dummy_args = DummyArgs()
    dummy(dummy_args, None)

    captured = capsys.readouterr()

    notices_decorator_assert_message_in_stdout(
        captured,
        messages=messages,
        dummy_mesg=dummy_mesg,
    )


def test__conda_user_story__only_see_once(
    capsys, notices_cache_dir, notices_mock_http_session_get
):
    """
    As a conda user, I only want to see a channel notice once while running
    commands like, 'install', 'update', or 'create'.
    """
    messages = ("Test One",)
    dummy_mesg = "Dummy Mesg"
    add_resp_to_mock(notices_mock_http_session_get, 200, messages)

    @notices.notices
    def dummy(args, parser):
        print(dummy_mesg)

    dummy_args = DummyArgs()
    dummy(dummy_args, None)

    captured = capsys.readouterr()
    notices_decorator_assert_message_in_stdout(captured, messages=messages, dummy_mesg=dummy_mesg)

    dummy(dummy_args, None)
    captured = capsys.readouterr()
    notices_decorator_assert_message_in_stdout(
        captured, messages=messages, dummy_mesg=dummy_mesg, not_in=True
    )


def test__conda_user_story__disable_notices(
    capsys, notices_cache_dir, notices_mock_http_session_get, disable_channel_notices
):
    """
    As a conda user, if I disable channel notifications in my .condarc file,
    I do not want to see notifications while running commands like,  "install",
    "update" or "create".
    """
    messages = ("Test One", "Test Two")
    dummy_mesg = "Dummy Mesg"
    add_resp_to_mock(notices_mock_http_session_get, 200, messages)

    @notices.notices
    def dummy(args, parser):
        print(dummy_mesg)

    dummy_args = DummyArgs()
    dummy(dummy_args, None)
    captured = capsys.readouterr()

    notices_decorator_assert_message_in_stdout(
        captured, messages=messages, dummy_mesg=dummy_mesg, not_in=True
    )


def test__conda_user_story__more_notices_message(
    capsys, notices_cache_dir, notices_mock_http_session_get
):
    """
    As a conda user, I want to see a message telling me there are more notices
    if there are more to display.
    """
    messages = tuple(f"Test {idx}" for idx in range(1, 11, 1))
    add_resp_to_mock(notices_mock_http_session_get, 200, messages)

    @notices.notices
    def dummy(args, parser):
        pass

    dummy(None, None)

    captured = capsys.readouterr()

    assert captured.err == ""
    assert "There are 5 more messages" in captured.out


def test__developer_story__useful_error_message(
    capsys, notices_cache_dir, notices_mock_http_session_get
):
    """
    As a developer, if I improperly use the "notices" decorator, I want
    to see a helpful error message.
    """

    @notices.notices
    def dummy():
        print("Dummy Test")

    dummy()

    captured = capsys.readouterr()

    assert notices.NOTICES_DECORATOR_CONFIG_ERROR in captured.err
