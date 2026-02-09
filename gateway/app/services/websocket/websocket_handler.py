"""
Главный обработчик WebSocket соединений.

Координирует работу парсера сообщений, SSE handler и взаимодействие с Agent Runtime.
"""

import logging

import httpx
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.models.websocket import WSErrorResponse
from .message_parser import WebSocketMessageParser, WSMessage
from .sse_stream_handler import SSEStreamHandler

logger = logging.getLogger("gateway.websocket.handler")


class WebSocketHandler:
    """Главный обработчик WebSocket соединений."""
    
    def __init__(
        self,
        message_parser: WebSocketMessageParser,
        sse_handler: SSEStreamHandler,
        agent_runtime_url: str,
        internal_api_key: str,
        stream_timeout: float = 60.0
    ):
        """
        Инициализация WebSocket handler.
        
        Args:
            message_parser: Парсер WebSocket сообщений
            sse_handler: Обработчик SSE stream
            agent_runtime_url: URL Agent Runtime сервиса
            internal_api_key: Ключ для внутренней аутентификации
            stream_timeout: Таймаут для streaming запросов
        """
        self._parser = message_parser
        self._sse_handler = sse_handler
        self._agent_runtime_url = agent_runtime_url.rstrip('/')
        self._internal_api_key = internal_api_key
        self._stream_timeout = stream_timeout
    
    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        is_temp_session: bool = False
    ) -> None:
        """
        Обрабатывает WebSocket соединение.
        
        Flow:
        1. IDE отправляет сообщение через WebSocket
        2. Gateway парсит и валидирует сообщение
        3. Gateway пересылает в Agent через HTTP streaming (SSE)
        4. Agent отправляет SSE события
        5. Gateway пересылает SSE события в IDE через WebSocket
        6. Для новых сессий Agent отправляет session_info с реальным session_id
        
        Args:
            websocket: WebSocket соединение
            session_id: ID сессии (может быть временным new_*)
            is_temp_session: True если session_id временный
        """
        await websocket.accept()
        logger.info(f"[{session_id}] WebSocket connected (temp={is_temp_session})")
        
        # Храним реальный session_id после получения session_info
        actual_session_id = session_id
        
        try:
            async with httpx.AsyncClient(timeout=self._stream_timeout) as client:
                while True:
                    # Получаем сообщение от IDE
                    raw_msg = await websocket.receive_text()
                    logger.debug(f"[{actual_session_id}] Received WS message: {raw_msg!r}")
                    
                    # Парсим и валидируем сообщение
                    try:
                        message = self._parser.parse(raw_msg)
                        self._log_message(actual_session_id, message)
                    except ValueError as e:
                        logger.error(f"[{actual_session_id}] Failed to parse message: {e}")
                        logger.error(f"[{actual_session_id}] Raw message was: {raw_msg!r}")
                        await self._send_error(websocket, str(e))
                        continue
                    
                    # Пересылаем в Agent Runtime
                    # Для временных сессий передаем is_temp_session=True
                    new_session_id = await self._forward_to_agent(
                        client,
                        websocket,
                        actual_session_id,
                        message,
                        raw_msg,
                        is_temp_session
                    )
                    
                    # Если получили новый session_id от Agent Runtime, обновляем
                    if new_session_id and new_session_id != actual_session_id:
                        logger.info(
                            f"[{actual_session_id}] Session ID updated: "
                            f"{actual_session_id} -> {new_session_id}"
                        )
                        actual_session_id = new_session_id
                        # После первого сообщения сессия больше не временная
                        is_temp_session = False
        
        except WebSocketDisconnect:
            logger.info(f"[{actual_session_id}] WebSocket disconnected")
        except Exception as e:
            logger.error(f"[{actual_session_id}] WS fatal error: {e}", exc_info=True)
    
    def _log_message(self, session_id: str, message: WSMessage) -> None:
        """
        Логирует полученное сообщение.
        
        Args:
            session_id: ID сессии
            message: Валидированное сообщение
        """
        msg_type = message.type
        
        if msg_type == "user_message":
            logger.info(f"[{session_id}] Received user_message: role={message.role}")
        elif msg_type == "tool_result":
            logger.info(
                f"[{session_id}] Received tool_result: "
                f"call_id={message.call_id}, has_error={message.error is not None}"
            )
        elif msg_type == "switch_agent":
            logger.info(
                f"[{session_id}] Received switch_agent: "
                f"target={message.agent_type}"
            )
        elif msg_type == "hitl_decision":
            logger.info(
                f"[{session_id}] Received hitl_decision: "
                f"call_id={message.call_id}, decision={message.decision}"
            )
        elif msg_type == "plan_decision":
            logger.info(
                f"[{session_id}] Received plan_decision: "
                f"approval_request_id={message.approval_request_id}, "
                f"decision={message.decision}"
            )
    
    async def _forward_to_agent(
        self,
        client: httpx.AsyncClient,
        websocket: WebSocket,
        session_id: str,
        message: WSMessage,
        raw_msg: str,
        is_temp_session: bool = False
    ) -> str | None:
        """
        Пересылает сообщение в Agent Runtime через HTTP streaming.
        
        Args:
            client: HTTP клиент
            websocket: WebSocket соединение
            session_id: ID сессии (может быть временным)
            message: Валидированное сообщение
            raw_msg: Сырое JSON сообщение (для отправки в Agent)
            is_temp_session: True если session_id временный
            
        Returns:
            Новый session_id если получен от Agent Runtime, иначе None
        """
        try:
            logger.debug(f"[{session_id}] Forwarding to Agent via HTTP streaming")
            
            # Парсим raw_msg обратно в dict для отправки
            import json
            ide_msg = json.loads(raw_msg)
            
            # Формируем payload для Agent Runtime
            # Для временных сессий НЕ передаем session_id
            if is_temp_session:
                payload = {"message": ide_msg}
                logger.info(
                    f"[{session_id}] Temporary session - NOT sending session_id to Agent Runtime"
                )
            else:
                payload = {"session_id": session_id, "message": ide_msg}
                logger.debug(f"[{session_id}] Sending session_id to Agent Runtime")
            
            async with client.stream(
                "POST",
                f"{self._agent_runtime_url}/agent/message/stream",
                json=payload,
                headers={"X-Internal-Auth": self._internal_api_key},
            ) as response:
                response.raise_for_status()
                logger.debug(
                    f"[{session_id}] Agent streaming started, "
                    f"status={response.status_code}"
                )
                
                # Читаем SSE stream от Agent и пересылаем в IDE
                # SSEStreamHandler вернет новый session_id если получит session_info
                new_session_id = await self._sse_handler.process_stream(
                    response,
                    websocket,
                    session_id
                )
                
                return new_session_id
        
        except httpx.HTTPStatusError as e:
            # Для streaming response нужно прочитать содержимое перед доступом к .text
            try:
                error_body = await e.response.aread()
                error_text = error_body.decode('utf-8')
                logger.error(
                    f"[{session_id}] Agent HTTP error: "
                    f"{e.response.status_code}, {error_text}"
                )
            except Exception as read_err:
                logger.error(
                    f"[{session_id}] Agent HTTP error: "
                    f"{e.response.status_code}, failed to read response: {read_err}"
                )
                error_text = "Unable to read error response"
            
            await self._send_error(
                websocket,
                f"Agent error: {e.response.status_code}"
            )
            return None
        
        except Exception as e:
            logger.error(
                f"[{session_id}] Error streaming from Agent: {e}",
                exc_info=True
            )
            await self._send_error(
                websocket,
                f"Streaming error: {str(e)}"
            )
            return None
    
    async def _send_error(self, websocket: WebSocket, message: str) -> None:
        """
        Отправляет сообщение об ошибке в WebSocket.
        
        Args:
            websocket: WebSocket соединение
            message: Текст ошибки
        """
        error = WSErrorResponse(type="error", content=message)
        await websocket.send_json(error.model_dump())
