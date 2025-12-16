import httpx
import logging
from typing import Optional
from app.core.config import AppConfig
from app.models.schemas import ToolCall, WSToolCall

logger = logging.getLogger("agent-runtime")

class ToolCallHandler:
    """
    Отвечает за вызов инструментов через Gateway и обработку результата.
    """
    def __init__(self, gateway_url: Optional[str] = None, api_key: Optional[str] = None):
        self.gateway_url = gateway_url or AppConfig.GATEWAY_URL
        self.api_key = api_key or AppConfig.INTERNAL_API_KEY

    async def execute(self, session_id: str, tool_call: ToolCall) -> Optional[dict]:
        """
        Отправляет tool_call на Gateway, ожидает ответ (REST-sync).
        Возвращает dict - результат выполнения инструмента.
        """
        try:
            path = f"{self.gateway_url}/tool/execute/{session_id}"
            logger.debug(f"ToolExecute path: {path}")
            ws_tool_call = WSToolCall(
                type="tool_call",
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
            )
            logger.debug(f"ToolCall payload: {ws_tool_call.model_dump()}")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    path,
                    json=ws_tool_call.model_dump(),
                    headers={"X-Internal-Auth": self.api_key},
                    timeout=35.0
                )
                response.raise_for_status()
                data = response.json()
                if data.get("status") == "ok" and "result" in data:
                    return data["result"]
                else:
                    err_msg = data.get("detail", "Unknown Gateway error")
                    logger.error(f"Gateway returned error: {err_msg}")
        except Exception as e:
            logger.error(f"Error communicating with Gateway for tool_call: {e}")
        return None

# Singleton instance
tool_call_handler = ToolCallHandler()
