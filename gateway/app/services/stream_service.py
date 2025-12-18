import httpx
from fastapi import WebSocket
import pprint

from app.core.config import AppConfig, logger
from app.models.rest import AgentRequest, AgentResponse
from app.models.websocket import WSUserMessage

BUFFER_SIZE = 100

# TokenBufferManager теперь внедряется через Depends там, где это реально требуется

async def stream_agent_single(
    client: httpx.AsyncClient,
    session_id: str,
    message: WSUserMessage,
    websocket: WebSocket,
):
    agent_req = AgentRequest.model_construct(
        session_id=session_id, type=message.type, content=message.content
    )
    logger.debug(f"[{session_id}] Forwarding to agent (stream=False), request object:\n" + pprint.pformat(agent_req.model_dump(), indent=2, width=120))
    try:
        response = await client.post(
            f"{AppConfig.AGENT_URL}/agent/message/stream",
            json=agent_req.model_dump(),
            headers={
                "X-Internal-Auth": AppConfig.INTERNAL_API_KEY,
            },
            timeout=AppConfig.REQUEST_TIMEOUT,
        )
        logger.debug(f"[{session_id}] Agent responded: {response.status_code}, body head: {response.text[:500]}")
        response.raise_for_status()
        data = response.json()
        logger.debug(f"[{session_id}] Full agent response body:\n" + pprint.pformat(data, indent=2, width=120))
        await websocket.send_json(data)
        logger.debug(f"[{session_id}] Sent final response to WS: {pprint.pformat(data, indent=2, width=120)}")
    except Exception as e:
        logger.error(f"[{session_id}] Exception in stream_agent_single: {e}", exc_info=True)
        logger.error(f"[{session_id}] Failed request details:\n" + pprint.pformat(agent_req.model_dump(), indent=2, width=120))
        raise
