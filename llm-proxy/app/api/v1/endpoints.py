import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import get_llm_adapter
from app.models.schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChoiceDelta,
    ChoiceMsg,
    DeltaMessage,
    LLMModel,
    OpenAIError,
)

router = APIRouter()
logger = logging.getLogger("llm-proxy")


@router.get("/v1/llm/models", response_model=List[LLMModel])
async def list_models(adapter=Depends(get_llm_adapter)):
    logger.info("[LLM Proxy] List models called")
    models = await adapter.get_models()
    return [LLMModel.model_construct(**model) for model in models]


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: Optional[str] = Header(None),  # для совместимости с openai sdk
    adapter=Depends(get_llm_adapter),
):
    logger.info(f"[OpenAI] Completion req, model={request.model}, stream={request.stream}")
    req_id = f"chatcmpl-{int(time.time() * 1000)}"
    created = int(time.time())
    try:
        result = await adapter.chat(request)
        if not request.stream:
            # НЕ-СТРИМОВЫЙ РЕЖИМ
            # Формируем openai-совместимый ответ
            choices = [
                ChoiceMsg.model_construct(
                    index=0,
                    message=ChatMessage.model_construct(role="assistant", content=result),
                    finish_reason="stop",
                )
            ]
            resp = ChatCompletionResponse.model_construct(
                id=req_id,
                object="chat.completion",
                created=created,
                model=request.model,
                choices=choices,
                # usage -- опционально
            )
            return resp
        else:
            # СТРИМИНГОВЫЙ РЕЖИМ (sse)
            async def event_generator():
                idx = 0
                delta_started = False
                try:
                    async for token in result:
                        if not delta_started:
                            # Сначала отправляем роль assistant
                            delta = ChoiceDelta.model_construct(
                                index=idx,
                                delta=DeltaMessage.model_construct(role="assistant", content=None),
                                finish_reason=None,
                            )
                            chunk = ChatCompletionChunk.model_construct(
                                id=req_id,
                                object="chat.completion.chunk",
                                created=created,
                                model=request.model,
                                choices=[delta],
                            )
                            yield chunk.model_dump_json() + "\n"
                            delta_started = True
                        # Отправляем токен как delta-content
                        delta = ChoiceDelta.model_construct(
                            index=idx,
                            delta=DeltaMessage.model_construct(content=token),
                            finish_reason=None,
                        )
                        chunk = ChatCompletionChunk.model_construct(
                            id=req_id,
                            object="chat.completion.chunk",
                            created=created,
                            model=request.model,
                            choices=[delta],
                        )
                        yield chunk.model_dump_json() + "\n"
                    # Финальный пустой дельта-чанк с finish_reason
                    delta = ChoiceDelta.model_construct(
                        index=idx, delta=DeltaMessage.model_construct(), finish_reason="stop"
                    )
                    chunk = ChatCompletionChunk.model_construct(
                        id=req_id,
                        object="chat.completion.chunk",
                        created=created,
                        model=request.model,
                        choices=[delta],
                    )
                    yield chunk.model_dump_json() + "\n"
                    yield "[DONE]\n"
                except Exception as e:
                    logger.error(f"[OpenAI] Streaming error: {e}")
                    yield '{"error": "Internal server error"}\n'

            return EventSourceResponse(event_generator())
    except Exception as e:
        logger.error(f"[OpenAI] Error: {e}")
        err = OpenAIError.model_construct(message=str(e), type="internal_error")
        return JSONResponse(content=err.model_dump(), status_code=500)
