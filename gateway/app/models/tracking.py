from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

class ToolCallTracking(BaseModel):
    """Tracks tool calls being routed through Gateway"""

    call_id: str
    session_id: str
    tool_name: str
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "pending"  # pending, sent_to_ide, completed, failed, timeout
    ide_websocket_id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None
