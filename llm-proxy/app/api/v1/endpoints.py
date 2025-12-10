import logging
from typing import List

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import get_llm_adapter
from app.models.schemas import ChatRequest, ChatResponse, HealthResponse, LLMModel, TokenChunk
from app.services.llm_service import sse

router = APIRouter()
logger = logging.getLogger("llm-proxy")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    logger.info("[LLM Proxy] Health check called")
    return HealthResponse.model_construct(status="healthy", service="llm-proxy", version="0.1.0")


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
        result = await adapter.chat(request)
        if not getattr(request, "stream", False):
            # обычный ответ
            return ChatResponse.model_construct(message=result, model=request.model)
        else:
            # stream: result — async generator of tokens
            async def event_generator():
                async for token in result:
                    chunk = TokenChunk.model_construct(token=token, is_final=False)
                    logger.debug(f"[LLM Proxy] Yielding stream token SSE: {chunk.token}")
                    yield sse("message", chunk)
                final_chunk = TokenChunk.model_construct(token="", is_final=True)
                yield sse("message", final_chunk)

            return EventSourceResponse(event_generator())
    except Exception as e:
        logger.error(f"[LLM Proxy] LLM adapter error: {str(e)}")
        if not getattr(request, "stream", False):
            return ChatResponse.model_construct(message=f"[LLM error]: {e}", model=request.model)
        else:

            async def err_event():
                chunk = TokenChunk.model_construct(token=f"[LLM error]: {e}", is_final=True)
                yield sse("message", chunk)

            return EventSourceResponse(err_event())
