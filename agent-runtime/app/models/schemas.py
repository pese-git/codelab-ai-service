"""
Common schemas for agent runtime.

DEPRECATED: This module is kept for backward compatibility.
New code should use:
- API schemas: app.api.v1.schemas.common
- Domain entities: app.domain.entities

This file re-exports everything from the new location.
"""
import logging

logger = logging.getLogger("agent-runtime.models.schemas")

# Re-export Message from domain entities (full domain model)
from ..domain.entities.message import Message

# Re-export from API schemas
from ..api.v1.schemas.common import (
    ToolCall,
    StreamChunk,
    SessionState,
    AgentInfo
)

# Re-export HealthResponse from health_schemas
from ..api.v1.schemas.health_schemas import HealthResponse

# Re-export AgentStreamRequest from message_schemas (if exists)
try:
    from ..api.v1.schemas.message_schemas import MessageStreamRequest as AgentStreamRequest
except ImportError:
    # Fallback definition if not in message_schemas
    from pydantic import BaseModel, Field
    from typing import Dict, Any
    
    class AgentStreamRequest(BaseModel):
        """Request model for streaming endpoint - accepts either user message or tool result"""
        session_id: str = Field(description="Session identifier")
        message: Dict[str, Any] = Field(description="Message content - can be user_message or tool_result")

__all__ = [
    "HealthResponse",
    "Message",  # From domain.entities
    "ToolCall",
    "SessionState",
    "AgentStreamRequest",
    "StreamChunk",
    "AgentInfo",
]

logger.warning(
    "app.models.schemas is deprecated. "
    "Use app.api.v1.schemas.common for API schemas or app.domain.entities for domain models."
)
