#!/usr/bin/env python3
"""
Тестовый скрипт для проверки сериализации Pydantic StreamChunk
"""
import json
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


class StreamChunk(BaseModel):
    """SSE event chunk for streaming responses"""
    
    type: Literal["assistant_message", "tool_call", "error", "done"] = Field(
        description="Type of the stream chunk"
    )
    content: Optional[str] = Field(default=None, description="Text content for assistant messages")
    token: Optional[str] = Field(default=None, description="Single token for streaming")
    is_final: bool = Field(default=False, description="Whether this is the final chunk")
    
    # For tool_call type
    call_id: Optional[str] = Field(default=None, description="Tool call identifier")
    tool_name: Optional[str] = Field(default=None, description="Name of the tool to call")
    arguments: Optional[Dict[str, Any]] = Field(default=None, description="Tool arguments")
    
    # For error type
    error: Optional[str] = Field(default=None, description="Error message if any")
    
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


def test_tool_call_serialization():
    """Тест сериализации tool_call"""
    print("=" * 80)
    print("TEST: StreamChunk tool_call serialization")
    print("=" * 80)
    
    # Создаем chunk как в llm_stream_service.py
    chunk = StreamChunk(
        type="tool_call",
        call_id="call_123",
        tool_name="read_file",
        arguments={"path": "lib/test_lsp.dart"},
        is_final=True
    )
    
    print("\n1. Chunk object:")
    print(f"   chunk.type = {chunk.type!r}")
    print(f"   chunk.call_id = {chunk.call_id!r}")
    print(f"   chunk.tool_name = {chunk.tool_name!r}")
    print(f"   chunk.arguments = {chunk.arguments!r}")
    print(f"   chunk.is_final = {chunk.is_final!r}")
    
    print("\n2. model_dump():")
    chunk_dict = chunk.model_dump()
    print(json.dumps(chunk_dict, indent=2))
    print(f"   'type' in dict: {'type' in chunk_dict}")
    print(f"   dict['type'] = {chunk_dict.get('type')!r}")
    
    print("\n3. model_dump_json():")
    chunk_json = chunk.model_dump_json()
    print(chunk_json)
    
    print("\n4. Parse back from JSON:")
    parsed = json.loads(chunk_json)
    print(json.dumps(parsed, indent=2))
    print(f"   'type' in parsed: {'type' in parsed}")
    print(f"   parsed['type'] = {parsed.get('type')!r}")
    
    print("\n5. model_dump(exclude_none=True):")
    chunk_dict_no_none = chunk.model_dump(exclude_none=True)
    print(json.dumps(chunk_dict_no_none, indent=2))
    print(f"   'type' in dict: {'type' in chunk_dict_no_none}")
    print(f"   dict['type'] = {chunk_dict_no_none.get('type')!r}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    test_tool_call_serialization()
