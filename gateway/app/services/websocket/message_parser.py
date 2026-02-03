"""
Парсер WebSocket сообщений с валидацией.

Обеспечивает строгую типизацию и валидацию входящих сообщений от IDE.
"""

import json
import logging
from typing import Union

from pydantic import ValidationError

from app.models.websocket import (
    WSUserMessage,
    WSToolResult,
    WSSwitchAgent,
    WSHITLDecision,
    WSPlanDecision
)

logger = logging.getLogger("gateway.websocket.parser")

# Union type для всех возможных WebSocket сообщений
WSMessage = Union[
    WSUserMessage,
    WSToolResult,
    WSSwitchAgent,
    WSHITLDecision,
    WSPlanDecision
]


class WebSocketMessageParser:
    """Парсер WebSocket сообщений с валидацией."""
    
    def parse(self, raw_message: str) -> WSMessage:
        """
        Парсит и валидирует WebSocket сообщение от IDE.
        
        Args:
            raw_message: Сырое JSON сообщение
            
        Returns:
            Валидированное сообщение соответствующего типа
            
        Raises:
            ValueError: Если сообщение невалидно или неизвестного типа
        """
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        
        msg_type = data.get("type")
        if not msg_type:
            raise ValueError("Message type is required")
        
        try:
            if msg_type == "user_message":
                return WSUserMessage.model_validate(data)
            elif msg_type == "tool_result":
                return WSToolResult.model_validate(data)
            elif msg_type == "switch_agent":
                return WSSwitchAgent.model_validate(data)
            elif msg_type == "hitl_decision":
                return WSHITLDecision.model_validate(data)
            elif msg_type == "plan_decision":
                return WSPlanDecision.model_validate(data)
            else:
                raise ValueError(f"Unknown message type: {msg_type}")
        except ValidationError as e:
            # Специальная обработка для распространенной ошибки с plan_decision
            error_msg = str(e)
            if "call_id" in error_msg and "Input should be a valid string" in error_msg:
                raise ValueError(
                    f"Invalid message format: plan_decision requires "
                    f"'approval_request_id' and 'decision' fields, not 'call_id'. "
                    f"Error: {error_msg}"
                )
            raise ValueError(f"Validation error: {e}")
