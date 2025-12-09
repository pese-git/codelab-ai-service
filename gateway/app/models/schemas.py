from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class WSUserMessage(BaseModel):
    type: Literal["user_message"]
    content: str


class AgentRequest(BaseModel):
    session_id: str
    type: str
    content: str


class AgentResponse(BaseModel):
    type: Literal["assistant_message"]
    token: str
    is_final: bool


class WSErrorResponse(BaseModel):
    type: Literal["error"]
    content: str
