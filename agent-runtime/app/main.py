import logging
import os
from typing import List

import httpx
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

# Настройка логирования
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

app = FastAPI(title="Agent Runtime Service")

# Configuration
LLM_PROXY_URL = os.getenv('LLM_PROXY_URL', 'http://localhost:8002')


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
async def health_check() -> HealthResponse:
    return HealthResponse.model_construct(
        status="healthy", service="agent-runtime", version="0.1.0"
    )


@app.post("/agent/message", response_model=MessageResponse)
async def process_message(message: Message) -> MessageResponse:
    # Prepare message for LLM
    llm_request = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": message.content}
        ],
        "stream": False
    }
    
    # Send request to LLM Proxy
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{LLM_PROXY_URL}/llm/chat",
            json=llm_request
        )
        response.raise_for_status()
        llm_response = response.json()
        
        return MessageResponse.model_construct(
            status="success",
            message=llm_response["message"]
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
