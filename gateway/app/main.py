import json
import logging
import os
from typing import Dict, List, Literal

import httpx
import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.websockets import WebSocketDisconnect

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "change-me-internal-key")


logging.basicConfig(level=os.getenv("LOG_LEVEL", "DEBUG"))
logger = logging.getLogger(__name__)

app = FastAPI(title="Gateway Service")


# --- Internal Auth Middleware --- #
class InternalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health",) or request.url.path.startswith("/ws/"):
            return await call_next(request)
        # Только для внутренних endpoint-ов
        auth = request.headers.get("x-internal-auth")
        logger.debug(
            f"[gateway][AUTH] Incoming X-Internal-Auth: '{auth}', INTERNAL_API_KEY: '{INTERNAL_API_KEY}'"
        )
        if auth != INTERNAL_API_KEY:
            logger.warning(
                f"[gateway][AUTH_FAIL] Unauthorized: header='{auth}' != key='{INTERNAL_API_KEY}'"
            )
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)


app.add_middleware(InternalAuthMiddleware)

AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8001")
REQUEST_TIMEOUT = 30.0

token_buffers: Dict[str, List[str]] = {}
BUFFER_SIZE = 100


# --- Models --- #


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class WSUserMessage(BaseModel):
    type: Literal["user_message"]
    content: str


class AgentRequest(BaseModel):
    session_id: str
    type: str
    content: str


class AgentResponse(BaseModel):
    type: Literal["assistant_message"]
    token: str
    is_final: bool


class WSErrorResponse(BaseModel):
    type: Literal["error"]
    content: str


# --- Routes --- #


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse.model_construct(status="healthy", service="gateway", version="0.1.0")


# --- SSE Streaming --- #
async def stream_agent_sse(
    client: httpx.AsyncClient,
    session_id: str,
    message: WSUserMessage,
    websocket: WebSocket,
):
    agent_req = AgentRequest.model_construct(
        session_id=session_id, type=message.type, content=message.content
    )
    logger.debug(f"[{session_id}] Forwarding to agent: {agent_req.model_dump_json()}")

    try:
        async with client.stream(
            "POST",
            f"{AGENT_URL}/agent/message/stream",
            json=agent_req.model_dump(),
            headers={
                "Accept": "text/event-stream",
                "X-Internal-Auth": INTERNAL_API_KEY,
            },
            timeout=REQUEST_TIMEOUT,
        ) as response:
            logger.debug(f"[{session_id}] Connected to agent, status code: {response.status_code}")
            response.raise_for_status()

            async for line in response.aiter_lines():
                logger.debug(f"[{session_id}] Raw SSE line: {line!r}")
                line = line.strip()
                if not line.startswith("data:"):
                    continue

                raw_json = line[len("data:") :].strip()
                logger.debug(f"[{session_id}] SSE data payload: {raw_json}")

                try:
                    data = AgentResponse.model_validate(json.loads(raw_json))
                    logger.debug(f"[{session_id}] Parsed agent response: {data}")
                except Exception as e:
                    logger.error(f"[{session_id}] Invalid SSE JSON: {raw_json} ({e})")
                    continue

                # Буфер токенов
                if session_id not in token_buffers:
                    token_buffers[session_id] = []
                token_buffers[session_id].append(data.token)
                if len(token_buffers[session_id]) > BUFFER_SIZE:
                    token_buffers[session_id].pop(0)
                logger.debug(f"[{session_id}] Token buffer size: {len(token_buffers[session_id])}")

                # Отправка токена клиенту по WebSocket
                await websocket.send_json(data.model_dump())
                logger.debug(
                    f"[{session_id}] Sent token to WS: {data.token!r}, is_final={data.is_final}"
                )

                if data.is_final:
                    logger.info(f"[{session_id}] Stream completed.")

    except Exception as e:
        logger.error(f"[{session_id}] Exception in stream_agent_sse: {e}")
        raise


# --- WebSocket --- #
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logger.info(f"[{session_id}] WebSocket connected")

    try:
        async with httpx.AsyncClient() as client:
            while True:
                raw_msg = await websocket.receive_text()
                logger.debug(f"[{session_id}] Received WS message: {raw_msg!r}")

                try:
                    msg = WSUserMessage.model_validate(json.loads(raw_msg))
                    logger.debug(f"[{session_id}] Parsed WSUserMessage: {msg}")
                except Exception:
                    err = WSErrorResponse.model_construct(
                        type="error", content="Invalid JSON message"
                    )
                    await websocket.send_json(err.model_dump())
                    logger.warning(f"[{session_id}] Invalid WS JSON, sent error")
                    continue

                try:
                    await stream_agent_sse(client, session_id, msg, websocket)
                except Exception as e:
                    err = WSErrorResponse.model_construct(type="error", content=str(e))
                    await websocket.send_json(err.model_dump())
                    logger.error(f"[{session_id}] Error streaming: {e}")

    except WebSocketDisconnect:
        logger.info(f"[{session_id}] WebSocket disconnected")
        token_buffers.pop(session_id, None)

    except Exception as e:
        logger.error(f"[{session_id}] WS fatal error: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
