from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

class Message(BaseModel):
    session_id: str
    type: str
    content: str

class MessageResponse(BaseModel):
    status: str
    message: str

class SSEToken(BaseModel):
    token: str
    is_final: bool
    type: str = "assistant_message"