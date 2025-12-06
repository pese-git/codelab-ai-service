import uvicorn
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

app = FastAPI(title="Gateway Service")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse.model_construct(status="healthy", service="gateway", version="0.1.0")


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    print(f"WebSocket connection opened for session: {session_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received message in session {session_id}: {data}")
            await websocket.send_text(f"Echo from gateway: {data}")
            
    except WebSocketDisconnect as disconnect:
        print(f"WebSocket disconnected normally for session: {session_id}, code: {disconnect.code}")
        
    except Exception as e:
        print(f"Error in WebSocket connection for session {session_id}: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
