"""Conftest for swing tests — overrides session-scope container fixtures from root conftest
so swing tests can run without Docker."""
import pytest


@pytest.fixture(scope="session")
def postgres_container():
    pytest.skip("no Docker in swing tests")


@pytest.fixture(scope="session")
def redis_container():
    pytest.skip("no Docker in swing tests")


@pytest.fixture(scope="session")
def database_url(postgres_container):
    return "sqlite://"


@pytest.fixture(scope="session")
def redis_url(redis_container):
    return "redis://localhost:6379/0"


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """No-op override — swing tests don't need DB/Redis env vars."""
    yield
