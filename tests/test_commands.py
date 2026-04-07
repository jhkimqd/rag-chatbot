"""Tests for the Command Registry."""

from src.commands.registry import has_command, list_commands


def test_has_command_registered():
    assert has_command("gas-usage") is True
    assert has_command("health") is True
    assert has_command("help") is True


def test_has_command_unknown():
    assert has_command("nonexistent") is False


def test_list_commands():
    cmds = list_commands()
    assert "gas-usage" in cmds
    assert "health" in cmds
    assert "help" in cmds
    assert cmds == sorted(cmds)
