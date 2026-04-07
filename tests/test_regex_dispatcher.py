"""Tests for the Regex Dispatcher."""

from src.router.regex_dispatcher import ParsedCommand, try_parse_command


def test_valid_command_no_args():
    result = try_parse_command("/health")
    assert result == ParsedCommand(name="health", raw_args="")


def test_valid_command_with_args():
    result = try_parse_command("/gas-usage 20")
    assert result == ParsedCommand(name="gas-usage", raw_args="20")


def test_valid_command_with_multiple_args():
    result = try_parse_command("/gas-usage 100 verbose")
    assert result == ParsedCommand(name="gas-usage", raw_args="100 verbose")


def test_command_with_whitespace():
    result = try_parse_command("  /health  ")
    assert result == ParsedCommand(name="health", raw_args="")


def test_non_command_returns_none():
    assert try_parse_command("How do I deploy on Polygon?") is None


def test_empty_string_returns_none():
    assert try_parse_command("") is None


def test_slash_only_returns_none():
    assert try_parse_command("/") is None


def test_command_name_normalized_lowercase():
    result = try_parse_command("/GAS-USAGE")
    assert result is not None
    assert result.name == "gas-usage"


def test_command_with_underscores():
    result = try_parse_command("/my_command arg1")
    assert result == ParsedCommand(name="my_command", raw_args="arg1")


def test_message_with_slash_in_middle():
    assert try_parse_command("Is the /health endpoint working?") is None
