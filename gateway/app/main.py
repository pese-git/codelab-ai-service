import json
import logging
import os
from typing import Dict, Any

import httpx
import uvicorn
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

# Настройка логирования
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

app = FastAPI(title="Gateway Service")

# Configuration
AGENT_URL = os.getenv('AGENT_URL', 'http://localhost:8001')
REQUEST_TIMEOUT = 30.0  # seconds


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse.model_construct(status="healthy", service="gateway", version="0.1.0")


async def forward_to_agent(client: httpx.AsyncClient, session_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Forward message to Agent Runtime service."""
    try:
        agent_request = {
            "session_id": session_id,
            "type": message_data.get("type", "user_message"),
            "content": message_data.get("content", "")
        }
        
        logger.info(f"Forwarding request to Agent Runtime for session {session_id}: {agent_request}")
        
        response = await client.post(
            f"{AGENT_URL}/agent/message",
            json=agent_request,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
        
    except httpx.TimeoutException:
        logger.error(f"Timeout while connecting to Agent Runtime for session {session_id}")
        raise Exception("Request to Agent Runtime timed out")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from Agent Runtime: {e.response.status_code} - {e.response.text}")
        raise Exception(f"Agent Runtime returned error: {e.response.status_code}")
        
    except httpx.RequestError as e:
        logger.error(f"Network error while connecting to Agent Runtime: {str(e)}")
        raise Exception("Failed to connect to Agent Runtime")


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logger.info(f"WebSocket connection opened for session: {session_id}")
    
    try:
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    # Receive message from WebSocket
                    data = await websocket.receive_text()
                    logger.info(f"Received message in session {session_id}: {data}")
                    
                    # Parse the incoming message
                    message_data = json.loads(data)
                    
                    # Forward to Agent Runtime
                    agent_response = await forward_to_agent(client, session_id, message_data)
                    
                    # Send response back through WebSocket
                    response = {
                        "type": "assistant_message",
                        "content": agent_response["message"]
                    }
                    logger.info(f"Sending response in session {session_id}: {response}")
                    await websocket.send_json(response)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in session {session_id}: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "content": "Invalid message format"
                    })
                except Exception as e:
                    logger.error(f"Error processing message in session {session_id}: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Error processing message: {str(e)}"
                    })
            
    except WebSocketDisconnect as disconnect:
        logger.info(f"WebSocket disconnected normally for session: {session_id}, code: {disconnect.code}")
        
    except Exception as e:
        logger.error(f"Error in WebSocket connection for session {session_id}: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
