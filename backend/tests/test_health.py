from fastapi.testclient import TestClient
from app.main import app


def test_health_does_not_claim_dependencies_are_ready():
    response = TestClient(app).get('/api/v1/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'alive'
    assert 'api_key' not in response.text


def test_business_routes_require_authentication():
    assert TestClient(app).get('/api/v1/tickets').status_code == 401
