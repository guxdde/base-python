from fastapi.testclient import TestClient
from app.main import app

def test_registered_tasks_endpoint():
    client = TestClient(app)
    resp = client.get("/api/v1/tasks/registered")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
