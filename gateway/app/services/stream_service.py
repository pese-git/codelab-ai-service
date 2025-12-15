from typing import Dict, List

import httpx
from fastapi import WebSocket

from app.core.config import AppConfig, logger
from app.models.schemas import AgentRequest, AgentResponse, WSUserMessage

BUFFER_SIZE = 100

token_buffers: Dict[str, List[str]] = {}


def get_token_buffers():
    return token_buffers


async def stream_agent_single(
    client: httpx.AsyncClient,
    session_id: str,
    message: WSUserMessage,
    websocket: WebSocket,
):
    agent_req = AgentRequest.model_construct(
        session_id=session_id, type=message.type, content=message.content
    )
    logger.debug(f"[{session_id}] Forwarding to agent (stream=False): {agent_req.model_dump_json()}")
    try:
        response = await client.post(
            f"{AppConfig.AGENT_URL}/agent/message/stream",
            json=agent_req.model_dump(),
            headers={
                "X-Internal-Auth": AppConfig.INTERNAL_API_KEY,
            },
            timeout=AppConfig.REQUEST_TIMEOUT,
        )
        logger.debug(f"[{session_id}] Agent responded: {response.status_code}, body: {response.text[:500]}")
        response.raise_for_status()
        data = response.json()
        await websocket.send_json(data)
        logger.debug(f"[{session_id}] Sent final response to WS.")
    except Exception as e:
        logger.error(f"[{session_id}] Exception in stream_agent_single: {e}")
        raise
