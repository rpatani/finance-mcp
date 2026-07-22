from __future__ import annotations

import pytest
import structlog


@pytest.fixture(autouse=True)
def _isolate_structlog() -> object:
    """Reset structlog global config around each test (avoids leaking a closed
    stdout/stderr capture buffer between tests)."""
    structlog.reset_defaults()
    yield
    structlog.reset_defaults()
