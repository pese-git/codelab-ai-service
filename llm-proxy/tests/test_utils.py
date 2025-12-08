import pytest
from llm_proxy.app.main import fake_token_generator


@pytest.mark.asyncio
async def test_fake_token_generator():
    tokens = []
    async for token in fake_token_generator("one two three"):
        tokens.append(token.strip())
    assert tokens == ["one", "two", "three"]
