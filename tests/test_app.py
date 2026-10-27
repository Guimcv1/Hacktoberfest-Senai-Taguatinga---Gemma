from app.main import app


def test_app_initializes() -> None:
    assert app.title == "StudyBuddy AI"
    schema = app.openapi()
    assert "/health" in schema["paths"]
    assert "get" in schema["paths"]["/health"]
    assert "/api/documents" in schema["paths"]
    assert "post" in schema["paths"]["/api/documents"]
    assert "/api/chat" in schema["paths"]
    assert "post" in schema["paths"]["/api/chat"]
    assert "/api/auth/register" in schema["paths"]
    assert "/api/auth/login" in schema["paths"]
    assert "/ready" in schema["paths"]
    assert "/api/conversations" in schema["paths"]
    assert "/api/conversations/{conversation_id}/documents" in schema["paths"]
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/docs" in paths
    assert "/openapi.json" in paths
