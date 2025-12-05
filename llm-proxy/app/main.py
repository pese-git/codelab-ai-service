from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import uvicorn

app = FastAPI(title="LLM Proxy Service")

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

class LLMModel(BaseModel):
    id: str
    name: str
    provider: str
    context_length: int
    is_available: bool

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        service="llm-proxy",
        version="0.1.0"
    )

@app.get("/llm/models", response_model=List[LLMModel])
async def list_models():
    # Mock data for now
    return [
        LLMModel(
            id="gpt-4",
            name="GPT-4",
            provider="OpenAI",
            context_length=8192,
            is_available=True
        ),
        LLMModel(
            id="claude-2",
            name="Claude 2",
            provider="Anthropic",
            context_length=100000,
            is_available=True
        )
    ]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
