from app.main import app


def test_openapi_does_not_require_document_or_conversation_to_start() -> None:
    schema = app.openapi()
    create = schema["components"]["schemas"]["ConversationCreate"]
    chat = schema["components"]["schemas"]["ChatRequest"]
    upload = schema["components"]["schemas"]["Body_upload_document_api_documents_post"]

    assert "document_id" not in create.get("required", [])
    assert chat.get("required") == ["message"]
    assert upload.get("required") == ["file"]
    assert schema["paths"]["/api/conversations"]["post"].get("requestBody", {}).get("required") is not True


def test_app_initializes() -> None:
    assert app.title == "StudyBuddy AI"
    schema = app.openapi()
    assert "/health" in schema["paths"]
    assert "get" in schema["paths"]["/health"]
    assert "/api/documents" in schema["paths"]
    assert "post" in schema["paths"]["/api/documents"]
    assert "/api/documents/{document_id}/file" in schema["paths"]
    assert "/api/chat" in schema["paths"]
    assert "post" in schema["paths"]["/api/chat"]
    assert "/api/auth/register" in schema["paths"]
    assert "/api/auth/login" in schema["paths"]
    assert "/ready" in schema["paths"]
    assert "/api/conversations" in schema["paths"]
    assert "/api/conversations/{conversation_id}/documents" in schema["paths"]
    assert "/api/conversations/{conversation_id}/questions/generate" in schema["paths"]
    assert "/api/conversations/{conversation_id}/questions" in schema["paths"]
    assert "/api/ai/unload" in schema["paths"]
    assert "post" in schema["paths"]["/api/ai/unload"]
    generate = schema["paths"]["/api/conversations/{conversation_id}/questions/generate"]["post"]
    assert generate.get("security")
    request_schema = schema["components"]["schemas"]["GenerateQuestionsRequest"]
    assert "observation" not in request_schema.get("required", [])
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/docs" in paths
    assert "/openapi.json" in paths
