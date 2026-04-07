"""Shared test configuration."""

import os

# Ensure tests don't accidentally call real APIs
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-secret")
