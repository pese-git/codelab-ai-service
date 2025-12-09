from typing import Dict, List

import httpx
from fastapi import WebSocket

from app.core.config import AppConfig, logger
from app.models.schemas import AgentRequest, AgentResponse, WSUserMessage

BUFFER_SIZE = 100

token_buffers: Dict[str, List[str]] = {}


def get_token_buffers():
    return token_buffers


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
            f"{AppConfig.AGENT_URL}/agent/message/stream",
            json=agent_req.model_dump(),
            headers={
                "Accept": "text/event-stream",
                "X-Internal-Auth": AppConfig.INTERNAL_API_KEY,
            },
            timeout=AppConfig.REQUEST_TIMEOUT,
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
                    data = AgentResponse.model_validate_json(raw_json)
                    logger.debug(f"[{session_id}] Parsed agent response: {data}")
                except Exception as e:
                    logger.error(f"[{session_id}] Invalid SSE JSON: {raw_json} ({e})")
                    continue

                if session_id not in token_buffers:
                    token_buffers[session_id] = []
                token_buffers[session_id].append(data.token)
                if len(token_buffers[session_id]) > BUFFER_SIZE:
                    token_buffers[session_id].pop(0)
                logger.debug(f"[{session_id}] Token buffer size: {len(token_buffers[session_id])}")

                await websocket.send_json(data.model_dump())
                logger.debug(
                    f"[{session_id}] Sent token to WS: {data.token!r}, is_final={data.is_final}"
                )

                if data.is_final:
                    logger.info(f"[{session_id}] Stream completed.")

    except Exception as e:
        logger.error(f"[{session_id}] Exception in stream_agent_sse: {e}")
        raise
