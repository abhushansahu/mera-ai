"""Contract compatibility tests for migration-safe APIs."""

from fastapi.testclient import TestClient

from app.api import create_app
from app.contracts import CONTRACT_VERSION


def test_contract_version_endpoint() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/contracts/version")
    assert response.status_code == 200
    assert response.json() == {"contract_version": CONTRACT_VERSION}


def test_status_includes_contract_header() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/status")
    assert response.status_code == 200
    assert response.headers.get("x-contract-version") == CONTRACT_VERSION
