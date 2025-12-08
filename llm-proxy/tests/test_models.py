from app.main import ChatRequest, ChatResponse, LLMModel, TokenChunk  # ty:ignore[unresolved-import]


def test_chatrequest_valid():
    r = ChatRequest.model_construct(model="gpt-4", messages=[{"role": "user", "content": "hi"}])
    assert r.model == "gpt-4"
    assert r.messages[0]["content"] == "hi"


def test_chatresponse_valid():
    cr = ChatResponse.model_construct(message="hello", model="gpt-4")
    assert cr.message == "hello"
    assert cr.model == "gpt-4"


def test_tokenchunk_valid():
    c = TokenChunk.model_construct(token="foo", is_final=False)
    assert c.type == "assistant_message"
    assert c.token == "foo"
    assert c.is_final is False


def test_llmmodel_valid():
    m = LLMModel.model_construct(
        id="gpt-4", name="GPT-4", provider="OpenAI", context_length=2048, is_available=True
    )
    assert m.id == "gpt-4"
    assert m.name == "GPT-4"
    assert m.is_available is True
