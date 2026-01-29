"""Pytest configuration and shared fixtures."""

import os

import pytest
from dotenv import load_dotenv


def pytest_configure(config: pytest.Config) -> None:
    """Load .env file before running tests."""
    load_dotenv()


@pytest.fixture(scope="session")
def integration_test_enabled() -> bool:
    """Check if integration tests should run.

    Set INTEGRATION_TESTS=1 to run integration tests.
    """
    return os.environ.get("INTEGRATION_TESTS", "0") == "1"
