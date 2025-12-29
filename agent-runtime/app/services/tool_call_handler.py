"""
DEPRECATED: This module is not used in the current architecture.

In the current WebSocket-based architecture:
1. Agent sends tool_call in SSE stream
2. Gateway forwards to IDE via WebSocket
3. IDE executes tool locally
4. IDE sends tool_result back via WebSocket

Tool execution happens on the IDE side, not via REST API calls.
See: codelab_ide/doc/websocket-protocol.md
"""

# import logging
# import pprint
# from typing import Optional
#
# import httpx
#
# from app.core.config import AppConfig
# from app.models.schemas import ToolCall, WSToolCall
#
# logger = logging.getLogger("agent-runtime.tool_call_handler")
#
#
# class ToolCallHandler:
#     """
#     Отвечает за вызов инструментов через Gateway и обработку результата.
#     """
#
#     def __init__(self, gateway_url: Optional[str] = None, api_key: Optional[str] = None):
#         self.gateway_url = gateway_url or AppConfig.GATEWAY_URL
#         self.api_key = api_key or AppConfig.INTERNAL_API_KEY
#
#     async def execute(self, session_id: str, tool_call: ToolCall) -> Optional[dict]:
#         """
#         Отправляет tool_call на Gateway, ожидает ответ (REST-sync).
#         Возвращает dict - результат выполнения инструмента.
#
#         Поддерживает все инструменты, включая read_file и write_file.
#         Для write_file автоматически устанавливается requires_approval=True.
#         """
#         try:
#             logger.info(f"[ToolCallHandler] Executing tool_call for session={session_id}, tool={tool_call.tool_name}")
#             logger.debug(f"[ToolCallHandler] tool_call object:\n" + pprint.pformat(tool_call.model_dump(), indent=2, width=120))
#             path = f"{self.gateway_url}/tool/execute/{session_id}"
#             logger.debug(f"[ToolCallHandler] ToolExecute path: {path}")
#
#             # Определяем, требуется ли подтверждение пользователя (HITL)
#             requires_approval = tool_call.tool_name in ["write_file", "delete_file", "move_file"]
#
#             # Для run_command проверяем опасность команды
#             if tool_call.tool_name == "run_command":
#                 command = tool_call.arguments.get("command", "")
#                 dangerous_patterns = [
#                     "rm ", "del ", "format", "mkfs",
#                     "dd ", "sudo", "su ", "chmod",
#                     "chown", ">", ">>", "|", "&&", ";",
#                     "curl", "wget", "nc ", "netcat"
#                 ]
#                 requires_approval = any(pattern in command.lower() for pattern in dangerous_patterns)
#
#             if requires_approval:
#                 logger.info(f"[ToolCallHandler] Tool '{tool_call.tool_name}' requires user approval (HITL)")
#
#             ws_tool_call = WSToolCall.model_construct(
#                 type="tool_call",
#                 call_id=tool_call.id,
#                 tool_name=tool_call.tool_name,
#                 arguments=tool_call.arguments,
#                 requires_approval=requires_approval,
#             )
#             logger.debug(f"[ToolCallHandler] ToolCall payload:\n" + pprint.pformat(ws_tool_call.model_dump(), indent=2, width=120))
#             async with httpx.AsyncClient() as client:
#                 response = await client.post(
#                     path,
#                     json=ws_tool_call.model_dump(),
#                     headers={"X-Internal-Auth": self.api_key},
#                     timeout=35.0,
#                 )
#                 logger.debug(f"[ToolCallHandler] Raw Gateway response [{response.status_code}]: {response.text[:300]}")
#                 response.raise_for_status()
#                 data = response.json()
#                 logger.debug(f"[ToolCallHandler] Gateway parsed response:\n" + pprint.pformat(data, indent=2, width=120))
#                 if data.get("status") == "ok" and "result" in data:
#                     logger.info(f"[ToolCallHandler] Gateway tool execution ok. Result keys: {list(data['result'].keys()) if isinstance(data['result'], dict) else type(data['result'])}")
#                     return data["result"]
#                 else:
#                     err_msg = data.get("detail", "Unknown Gateway error")
#                     logger.error(f"[ToolCallHandler] Gateway returned error: {err_msg}\nFull data: {pprint.pformat(data, indent=2, width=120)}")
#         except Exception as e:
#             logger.error(f"[ToolCallHandler] Error communicating with Gateway for tool_call: {e}", exc_info=True)
#             logger.error(f"[ToolCallHandler] tool_call params/locals:\n" + pprint.pformat(locals(), indent=2, width=120))
#         return None
#
#
# # Singleton instance
# # tool_call_handler = ToolCallHandler()
