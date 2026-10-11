import os

# Must run before the app modules are imported: they read these at import time.
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

import pytest


@pytest.fixture(autouse=True)
def _reset_login_rate_limiter():
    from ..security import login_rate_limiter

    login_rate_limiter.clear()
    yield
    login_rate_limiter.clear()
