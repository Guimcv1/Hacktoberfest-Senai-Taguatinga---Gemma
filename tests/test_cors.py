from fastapi.testclient import TestClient


def test_cors_allows_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_request_id_header_is_returned(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("x-request-id")
