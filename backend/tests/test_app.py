from fastapi.testclient import TestClient

from backend.main import app


def test_app_serves_openapi() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert isinstance(schema["paths"], dict)
