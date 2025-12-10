import logging
from typing import List

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ChatRequest, ChatResponse, HealthResponse, LLMModel, TokenChunk
from app.services.llm_service import fake_token_generator, sse

router = APIRouter()
logger = logging.getLogger("llm-proxy")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    logger.info("[LLM Proxy] Health check called")
    return HealthResponse.model_construct(status="healthy", service="llm-proxy", version="0.1.0")


@router.get("/llm/models", response_model=List[LLMModel])
async def list_models():
    logger.info("[LLM Proxy] List models called")
    return [
        LLMModel.model_construct(
            id="gpt-4",
            name="GPT-4",
            provider="OpenAI",
            context_length=8192,
            is_available=True,
        ),
        LLMModel.model_construct(
            id="claude-2",
            name="Claude 2",
            provider="Anthropic",
            context_length=100000,
            is_available=True,
        ),
    ]


from app.core.config import AppConfig
from app.services.llm_service import OpenAIAdapter


@router.post("/llm/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    last_message = request.messages[-1] if request.messages else {"content": ""}
    content = last_message.get("content", "")
    logger.info(f"[LLM Proxy] Chat request received: {content}, stream={request.stream}")

    # Non-streaming OpenAI logic
    is_openai_model = request.model.lower().startswith("gpt-")
    have_key = bool(AppConfig.OPENAI_API_KEY)
    if is_openai_model and have_key and AppConfig.LLM_MODE == "openai":
        try:
            adapter = OpenAIAdapter()
            oa_content = await adapter.chat(request)
            return ChatResponse.model_construct(message=oa_content, model=request.model)
        except Exception as e:
            logger.error(f"[LLM Proxy] OpenAI chat fallback: {str(e)}")
            return ChatResponse.model_construct(
                message=f"[OpenAI fallback error]: {e}", model=request.model
            )

    # fallback: mock echo
    if request.stream:
        return StreamingResponse(
            fake_token_generator(f"Echo from LLM: {content}"),
            media_type="text/event-stream",
        )

    return ChatResponse.model_construct(
        message=f"Echo from LLM: {content}",
        model=request.model,
    )


from app.core.config import AppConfig
from app.services.llm_service import fake_token_generator, sse, OpenAIAdapter

@router.post("/llm/stream")
async def stream_chat(request: ChatRequest, raw_request: Request):
    last_message = request.messages[-1]["content"] if request.messages else ""
    content = f"Echo from LLM: {last_message}"
    logger.info(f"[LLM Proxy] Stream request received for content: {content}")

    async def event_generator():
        logger.info("[LLM Proxy] Starting SSE event generator")
        is_openai_model = request.model.lower().startswith("gpt-")
        have_key = bool(AppConfig.OPENAI_API_KEY)
        if is_openai_model and have_key and AppConfig.LLM_MODE == "openai":
            try:
                adapter = OpenAIAdapter()
                async for token in adapter.streaming_generator(request):
                    chunk = TokenChunk.model_construct(token=token, is_final=False)
                    logger.debug(f"[LLM Proxy] Yielding OpenAI token SSE: {chunk.token}")
                    yield sse("message", chunk)
                logger.info("[LLM Proxy] OpenAI SSE stream completed")
                final_chunk = TokenChunk.model_construct(token="", is_final=True)
                yield sse("message", final_chunk)
                return
            except Exception as e:
                logger.error(f"[LLM Proxy] OpenAI streaming fallback: {str(e)}")
                chunk = TokenChunk.model_construct(token=f"[OpenAI error]: {e}", is_final=True)
                yield sse("message", chunk)
                return
        # fallback: mock
        async for token in fake_token_generator(content):
            chunk = TokenChunk.model_construct(token=token, is_final=False)
            logger.debug(f"[LLM Proxy] Yielding token SSE: {chunk.token}")
            yield sse("message", chunk)
        final_chunk = TokenChunk.model_construct(token="", is_final=True)
        logger.info("[LLM Proxy] Yielding final token SSE")
        yield sse("message", final_chunk)
        logger.info("[LLM Proxy] SSE stream completed")

    return EventSourceResponse(event_generator())
