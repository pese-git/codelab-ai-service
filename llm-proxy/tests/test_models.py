import pytest

from app.models.schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    OpenAIError,
)


def test_chat_completion_request_example():
    example = ChatCompletionRequest.model_config["json_schema_extra"]["example"]
    req = ChatCompletionRequest(**example)
    assert req.model == "gpt-4"
    assert req.messages[0].role == "user"
    # Проверим сериализацию
    out = req.model_dump_json()
    assert "model" in out and "messages" in out


def test_chat_completion_response_example():
    example = ChatCompletionResponse.model_config["json_schema_extra"]["example"]
    resp = ChatCompletionResponse(**example)
    # Проверяем поля базовые
    assert resp.object == "chat.completion"
    assert resp.choices[0].message.role == "assistant"


def test_chat_completion_chunk_example():
    example = ChatCompletionChunk.model_config["json_schema_extra"]["example"]
    chunk = ChatCompletionChunk(**example)
    assert chunk.object == "chat.completion.chunk"
    assert chunk.choices[0].delta.content == "Hello,"


def test_openai_error_example():
    example = OpenAIError.model_config["json_schema_extra"]["example"]
    err = OpenAIError(**example)
    assert "does not exist" in err.message


@pytest.mark.parametrize(
    "bad_request",
    [
        {},  # пустое
        {"model": 42, "messages": []},  # неверный тип model
        {"model": "gpt-4", "messages": [{}]},  # невалидный messages
    ],
)
def test_chat_completion_request_invalid(bad_request):
    with pytest.raises(Exception):
        ChatCompletionRequest(**bad_request)
