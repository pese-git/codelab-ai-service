import time
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # 'system', 'user', 'assistant', 'function', 'tool'
    content: Optional[str]
    name: Optional[str] = None
    function_call: Optional[dict] = None  # For function/tool replies


class FunctionCall(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: FunctionCall


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = 1
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    functions: Optional[List[dict]] = None
    tools: Optional[List[dict]] = None
    function_call: Optional[Union[str, dict]] = None
    tool_choice: Optional[Union[str, dict]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Say hello!"}],
                "stream": False,
                "temperature": 1.0,
            }
        }


class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChoiceMsg(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{int(time.time() * 1000)}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChoiceMsg]
    usage: Optional[UsageInfo] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "chatcmpl-abc123",
                "object": "chat.completion",
                "created": 1694083200,
                "model": "gpt-4",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello, how can I help you?"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 9, "completion_tokens": 6, "total_tokens": 15},
            }
        }


class DeltaMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    function_call: Optional[dict] = None
    tool_calls: Optional[List[ToolCall]] = None
    metadata: Optional[Dict[str, Any]] = None  # Raw provider data without interpretation


class ChoiceDelta(BaseModel):
    index: int
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChoiceDelta]

    class Config:
        json_schema_extra = {
            "example": {
                "id": "chatcmpl-abc123",
                "object": "chat.completion.chunk",
                "created": 1694083200,
                "model": "gpt-4",
                "choices": [{"index": 0, "delta": {"content": "Hello,"}, "finish_reason": None}],
            }
        }


class OpenAIError(BaseModel):
    object: str = "error"
    message: str
    type: str
    param: Optional[str] = None
    code: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "object": "error",
                "message": "The model `not-a-model` does not exist.",
                "type": "invalid_request_error",
                "param": "model",
                "code": "model_not_found",
            }
        }


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
