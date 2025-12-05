import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Agent Runtime Service")


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


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", service="agent-runtime", version="0.1.0")


@app.post("/agent/message", response_model=MessageResponse)
async def process_message(message: Message):
    # Echo mode for now
    return MessageResponse(status="success", message=f"Echo from agent: {message.content}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
