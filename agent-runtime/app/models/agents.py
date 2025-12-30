from datetime import datetime
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, Field


class AskAgent(BaseModel):
    action: Literal["ask_agent"] = "ask_agent"
    target: Literal["planner", "coder", "tester", "reviewer"]
    message: str


class UseTool(BaseModel):
    action: Literal["use_tool"] = "use_tool"
    tool_id: str
    tool_name: str
    args: Dict[str, Any] = Field(default_factory=dict)


class Reply(BaseModel):
    action: Literal["reply"] = "reply"
    content: str


class Finish(BaseModel):
    action: Literal["finish"] = "finish"
    summary: str


class AgentStep(BaseModel):
    step: Union[AskAgent, UseTool, Reply, Finish]


class BusMeta(BaseModel):
    trace_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    # можно далее расширять


class BusMessage(BaseModel):
    sender: str
    recipient: str  # имя агента или "broadcast"
    content: str
    meta: Optional[BusMeta] = None
