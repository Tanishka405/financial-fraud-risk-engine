from __future__ import annotations

import pytest

from core.config import Config


@pytest.fixture
def config() -> Config:
    """Default config with deterministic seed, used across most tests."""
    return Config()
