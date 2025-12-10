import logging
from typing import List

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.core.config import AppConfig
from app.models.schemas import ChatRequest, ChatResponse, HealthResponse, LLMModel, TokenChunk
from app.services.llm_adapters.fake import FakeLLMAdapter
from app.services.llm_adapters.openai import OpenAIAdapter
from app.services.llm_service import sse

router = APIRouter()
logger = logging.getLogger("llm-proxy")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    logger.info("[LLM Proxy] Health check called")
    return HealthResponse.model_construct(status="healthy", service="llm-proxy", version="0.1.0")


@router.get("/llm/models", response_model=List[LLMModel])
async def list_models():
    logger.info("[LLM Proxy] List models called")
    llm_mode = (getattr(AppConfig, "LLM_MODE", "mock") or "mock").lower()
    if llm_mode == "openai":
        adapter = OpenAIAdapter()
    else:
        adapter = FakeLLMAdapter()
    models = await adapter.get_models()
    # Преобразовать dict -> LLMModel
    return [LLMModel.model_construct(**model) for model in models]


@router.post("/llm/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    logger.info(
        f"[LLM Proxy] Chat request received: {request.messages[-1]['content'] if request.messages else ''}, stream={request.stream}"
    )

    # централизованный выбор адаптера
    llm_mode = (getattr(AppConfig, "LLM_MODE", "mock") or "mock").lower()
    is_openai_model = request.model.lower().startswith("gpt-")
    have_key = bool(getattr(AppConfig, "OPENAI_API_KEY", ""))
    if llm_mode == "openai" and is_openai_model and have_key:
        adapter = OpenAIAdapter()
    else:
        adapter = FakeLLMAdapter()

    try:
        content = await adapter.chat(request)
        return ChatResponse.model_construct(message=content, model=request.model)
    except Exception as e:
        logger.error(f"[LLM Proxy] LLM adapter error: {str(e)}")
        return ChatResponse.model_construct(message=f"[LLM error]: {e}", model=request.model)


@router.post("/llm/stream")
async def stream_chat(request: ChatRequest, raw_request: Request):
    logger.info(
        f"[LLM Proxy] Stream request received for content: {request.messages[-1]['content'] if request.messages else ''}"
    )

    # централизованный выбор адаптера
    llm_mode = (getattr(AppConfig, "LLM_MODE", "mock") or "mock").lower()
    is_openai_model = request.model.lower().startswith("gpt-")
    have_key = bool(getattr(AppConfig, "OPENAI_API_KEY", ""))
    if llm_mode == "openai" and is_openai_model and have_key:
        adapter = OpenAIAdapter()
    else:
        adapter = FakeLLMAdapter()

    async def event_generator():
        logger.info("[LLM Proxy] Starting SSE event generator")
        try:
            async for token in adapter.streaming_generator(request):
                chunk = TokenChunk.model_construct(token=token, is_final=False)
                logger.debug(f"[LLM Proxy] Yielding token SSE: {chunk.token}")
                yield sse("message", chunk)
            final_chunk = TokenChunk.model_construct(token="", is_final=True)
            yield sse("message", final_chunk)
            logger.info("[LLM Proxy] SSE stream completed")
        except Exception as e:
            logger.error(f"[LLM Proxy] LLM adapter streaming error: {str(e)}")
            chunk = TokenChunk.model_construct(token=f"[LLM adapter error]: {e}", is_final=True)
            yield sse("message", chunk)

    return EventSourceResponse(event_generator())
