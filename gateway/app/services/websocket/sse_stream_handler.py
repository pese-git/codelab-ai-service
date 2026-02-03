"""
Обработчик SSE stream от Agent Runtime.

Читает Server-Sent Events от Agent Runtime и пересылает их в WebSocket.
"""

import json
import logging

import httpx
from fastapi import WebSocket

logger = logging.getLogger("gateway.websocket.sse")


class SSEStreamHandler:
    """Обработчик SSE stream от Agent Runtime."""
    
    async def process_stream(
        self,
        response: httpx.Response,
        websocket: WebSocket,
        session_id: str
    ) -> None:
        """
        Читает SSE stream и пересылает события в WebSocket.
        
        SSE формат:
        event: message
        data: {"type": "assistant_message", ...}
        
        event: done
        data: {"status": "completed"}
        
        Args:
            response: HTTP streaming response от Agent Runtime
            websocket: WebSocket соединение с IDE
            session_id: ID сессии (для логирования)
        """
        current_event_type = None
        
        async for line in response.aiter_lines():
            # Пустая строка - разделитель SSE событий
            if not line:
                current_event_type = None
                continue
            
            # Обрабатываем строку с типом события
            if line.startswith("event: "):
                current_event_type = line[7:].strip()
                logger.debug(f"[{session_id}] SSE event type: {current_event_type}")
                
                # Если получили event: done - завершаем обработку stream
                if current_event_type == "done":
                    logger.info(f"[{session_id}] Received 'done' event, completing stream")
                    break
                
                continue
            
            # Обрабатываем строку с данными
            if line.startswith("data: "):
                data_str = line[6:]
                
                # Проверяем на специальный маркер [DONE]
                if data_str == "[DONE]":
                    logger.info(f"[{session_id}] Received [DONE] marker, completing stream")
                    break
                
                # Парсим и пересылаем JSON данные
                await self._forward_data(
                    data_str,
                    current_event_type,
                    websocket,
                    session_id
                )
                continue
            
            # SSE комментарий (heartbeat), игнорируем
            if line.startswith(":"):
                logger.debug(f"[{session_id}] SSE heartbeat received")
                continue
            
            # Неизвестный формат строки
            logger.debug(f"[{session_id}] Ignoring unknown SSE line: {line}")
        
        logger.info(f"[{session_id}] Agent streaming completed successfully")
    
    async def _forward_data(
        self,
        data_str: str,
        event_type: str,
        websocket: WebSocket,
        session_id: str
    ) -> None:
        """
        Парсит и пересылает данные в WebSocket.
        
        Args:
            data_str: JSON строка с данными
            event_type: Тип SSE события
            websocket: WebSocket соединение
            session_id: ID сессии (для логирования)
        """
        try:
            data = json.loads(data_str)
            msg_type = data.get('type')
            
            # Фильтруем null значения, чтобы не отправлять лишние поля
            filtered_data = {k: v for k, v in data.items() if v is not None}
            
            # Логируем plan_approval_required для отладки
            if msg_type == "plan_approval_required":
                logger.info(
                    f"[{session_id}] plan_approval_required BEFORE filter: "
                    f"{json.dumps(data)}"
                )
                logger.info(
                    f"[{session_id}] plan_approval_required AFTER filter: "
                    f"{json.dumps(filtered_data)}"
                )
            
            logger.debug(
                f"[{session_id}] Received SSE data (event={event_type}): "
                f"type={msg_type}"
            )
            
            # Пересылаем событие в IDE через WebSocket
            await websocket.send_json(filtered_data)
            
        except json.JSONDecodeError as e:
            logger.warning(
                f"[{session_id}] Failed to parse SSE data for event "
                f"'{event_type}': {e}"
            )
