import logging
from typing import List

from fastapi import APIRouter, Request, Depends
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


from app.core.dependencies import get_llm_adapter

@router.get("/llm/models", response_model=List[LLMModel])
async def list_models(adapter=Depends(get_llm_adapter)):
    logger.info("[LLM Proxy] List models called")
    models = await adapter.get_models()
    return [LLMModel.model_construct(**model) for model in models]


@router.post("/llm/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, adapter=Depends(get_llm_adapter)):
    logger.info(
        f"[LLM Proxy] Chat request received: {request.messages[-1]['content'] if request.messages else ''}, stream={request.stream}"
    )
    try:
        content = await adapter.chat(request)
        return ChatResponse.model_construct(message=content, model=request.model)
    except Exception as e:
        logger.error(f"[LLM Proxy] LLM adapter error: {str(e)}")
        return ChatResponse.model_construct(message=f"[LLM error]: {e}", model=request.model)


@router.post("/llm/stream")
async def stream_chat(request: ChatRequest, raw_request: Request, adapter=Depends(get_llm_adapter)):
    logger.info(
        f"[LLM Proxy] Stream request received for content: {request.messages[-1]['content'] if request.messages else ''}"
    )
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
