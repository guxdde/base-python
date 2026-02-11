import asyncio
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.db.binds import BindManager


class DummySession:
    async def execute(self, *args, **kwargs):
        return None
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass

def dummy_get_session(bind_name: str = "postgres_main"):
    async def _gen():
        yield DummySession()
    return _gen()


def test_db_bindings_and_health_endpoint(monkeypatch):
    # Ensure we can add a bind and obtain a session via dependency
    BindManager._engines.clear()
    BindManager._sessionmakers.clear()
    BindManager.add_bind("postgres_main", "postgresql+asyncpg://user:pass@localhost/db")
    # Patch get_session to return a dummy session
    monkeypatch.setattr("app.db.postgres.get_session", dummy_get_session("postgres_main"))
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
