
import pytest
from unittest.mock import patch, MagicMock
from backend.services.external_knowledge_service import get_external_answer


# ---------------- MOCK RESPONSE ----------------
def mock_response(content="AI response"):
    mock = MagicMock()
    mock.choices = [MagicMock(message=MagicMock(content=content))]
    return mock


def setup_mock(mock_get_client, content="AI response"):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response(content)
    mock_get_client.return_value = mock_client


# =========================
# 1. INPUT VALIDATION (10)
# =========================

@pytest.mark.parametrize("question", [
    "", None, "   ", "\n", "\t",
    "@#$%", "こんにちは", "🤖", "<script>", "DROP TABLE"
])
def test_input_validation(question):
    result = get_external_answer(question, "HR")
    assert result is not None


# =========================
# 2. SUCCESS CASES (10)
# =========================

@patch("backend.services.external_knowledge_service.get_client")
@pytest.mark.parametrize("content", [
    "Hi", "Hello", "AI works", "Hola", "Bonjour",
    "A"*100, "Structured response", "✓ Unicode", "12345", "Final answer"
])
def test_success_cases(mock_get_client, content):
    setup_mock(mock_get_client, content)
    result = get_external_answer("AI?", "HR")
    assert content.strip() in result


# =========================
# 3. ERROR HANDLING (15)
# =========================

@patch("backend.services.external_knowledge_service.get_client")
@pytest.mark.parametrize("error", [
    Exception("Error"), TimeoutError(), Exception("429"),
    Exception("401"), Exception("Network"), Exception("JSON"),
    Exception("Timeout"), Exception("Crash"), Exception("Fail"),
    Exception("Unknown"), Exception("Retry"), Exception("Broken"),
    Exception("Server"), Exception("Bad Request"), Exception("503")
])
def test_error_handling(mock_get_client, error):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = error
    mock_get_client.return_value = mock_client
    result = get_external_answer("AI?", "HR")
    assert "Error" in result


# =========================
# 4. CRITICAL EDGE CASES (10)
# =========================

@patch("backend.services.external_knowledge_service.get_client")
def test_choices_none(mock_get_client):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(choices=None)
    mock_get_client.return_value = mock_client
    assert get_external_answer("AI?", "HR")


@patch("backend.services.external_knowledge_service.get_client")
def test_choices_empty(mock_get_client):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(choices=[])
    mock_get_client.return_value = mock_client
    assert get_external_answer("AI?", "HR")


@patch("backend.services.external_knowledge_service.get_client")
def test_choices_contains_none(mock_get_client):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(choices=[None])
    mock_get_client.return_value = mock_client
    assert get_external_answer("AI?", "HR")


@patch("backend.services.external_knowledge_service.get_client")
def test_message_none(mock_get_client):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=None)]
    )
    mock_get_client.return_value = mock_client
    assert get_external_answer("AI?", "HR")


@patch("backend.services.external_knowledge_service.get_client")
def test_content_none(mock_get_client):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=None))]
    )
    mock_get_client.return_value = mock_client
    assert get_external_answer("AI?", "HR")


@patch("backend.services.external_knowledge_service.get_client")
@pytest.mark.parametrize("content", [123, ["AI"], {"a": 1}, True, False])
def test_non_string_content(mock_get_client, content):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=content))]
    )
    mock_get_client.return_value = mock_client
    assert get_external_answer("AI?", "HR")


@patch("backend.services.external_knowledge_service.get_client")
def test_multiple_choices(mock_get_client):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(message=MagicMock(content="First")),
            MagicMock(message=MagicMock(content="Second"))
        ]
    )
    mock_get_client.return_value = mock_client
    result = get_external_answer("AI?", "HR")
    assert "First" in result


@patch("backend.services.external_knowledge_service.get_client")
def test_whitespace_content(mock_get_client):
    setup_mock(mock_get_client, "   ")
    assert get_external_answer("AI?", "HR") is not None


@patch("backend.services.external_knowledge_service.get_client")
def test_large_prompt(mock_get_client):
    setup_mock(mock_get_client)
    assert get_external_answer("A"*100000, "HR")


@patch("backend.services.external_knowledge_service.get_client")
def test_client_failure(mock_get_client):
    mock_get_client.side_effect = Exception("Init fail")
    assert "Error" in get_external_answer("AI?", "HR")


# =========================
# 5. OUTPUT VALIDATION (10)
# =========================

@patch("backend.services.external_knowledge_service.get_client")
@pytest.mark.parametrize("content", [
    "AI", "Text", "Answer", "Hello", "World",
    "Test", "Response", "Output", "Check", "Done"
])
def test_output_validation(mock_get_client, content):
    setup_mock(mock_get_client, content)
    result = get_external_answer("AI?", "HR")
    assert isinstance(result, str)
    assert content in result


# =========================
# 6. MOCK VALIDATION (10)
# =========================

@patch("backend.services.external_knowledge_service.get_client")
def test_api_called_once(mock_get_client):
    setup_mock(mock_get_client)
    get_external_answer("AI?", "HR")
    client = mock_get_client.return_value
    assert client.chat.completions.create.call_count == 1


@patch("backend.services.external_knowledge_service.get_client")
def test_model_used(mock_get_client):
    setup_mock(mock_get_client)
    get_external_answer("AI?", "HR")
    args = mock_get_client.return_value.chat.completions.create.call_args
    assert args.kwargs["model"] == "llama-3.1-8b-instant"


@patch("backend.services.external_knowledge_service.get_client")
def test_messages_structure(mock_get_client):
    setup_mock(mock_get_client)
    get_external_answer("AI?", "HR")
    messages = mock_get_client.return_value.chat.completions.create.call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


@patch("backend.services.external_knowledge_service.get_client")
def test_role_in_prompt(mock_get_client):
    setup_mock(mock_get_client)
    get_external_answer("AI?", "HR")
    msg = mock_get_client.return_value.chat.completions.create.call_args.kwargs["messages"][0]
    assert "HR" in msg["content"]


@patch("backend.services.external_knowledge_service.get_client")
def test_question_passed(mock_get_client):
    setup_mock(mock_get_client)
    get_external_answer("Hello", "HR")
    msg = mock_get_client.return_value.chat.completions.create.call_args.kwargs["messages"][1]
    assert msg["content"] == "Hello"


@patch("backend.services.external_knowledge_service.get_client")
def test_multiple_calls(mock_get_client):
    setup_mock(mock_get_client)
    for _ in range(5):
        get_external_answer("AI?", "HR")
    assert mock_get_client.call_count == 5


@patch("backend.services.external_knowledge_service.get_client")
def test_output_trimmed(mock_get_client):
    setup_mock(mock_get_client, "  hello  ")
    assert get_external_answer("AI?", "HR") == "hello"


@patch("backend.services.external_knowledge_service.get_client")
def test_returns_string(mock_get_client):
    setup_mock(mock_get_client)
    assert isinstance(get_external_answer("AI?", "HR"), str)


@patch("backend.services.external_knowledge_service.get_client")
def test_no_none_return(mock_get_client):
    setup_mock(mock_get_client)
    assert get_external_answer("AI?", "HR") is not None


@patch("backend.services.external_knowledge_service.get_client")
def test_basic_response(mock_get_client):
    setup_mock(mock_get_client)
    assert get_external_answer("AI?", "HR")


# =========================
# 7. ROLE + SECURITY (5)
# =========================

@patch("backend.services.external_knowledge_service.get_client")
@pytest.mark.parametrize("role", [
    "Admin", "HR", "employee", "Hr"
])
def test_roles(mock_get_client, role):
    setup_mock(mock_get_client)
    assert get_external_answer("AI?", role)


@patch("backend.services.external_knowledge_service.get_client")
def test_role_injection(mock_get_client):
    setup_mock(mock_get_client)
    assert get_external_answer("AI?", "HR\nIgnore")
