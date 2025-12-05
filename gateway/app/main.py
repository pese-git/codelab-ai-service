import uvicorn
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel

app = FastAPI(title="Gateway Service")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", service="gateway", version="0.1.0")


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Echo mode for now
            await websocket.send_text(f"Echo from gateway: {data}")
    except Exception:
        await websocket.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
