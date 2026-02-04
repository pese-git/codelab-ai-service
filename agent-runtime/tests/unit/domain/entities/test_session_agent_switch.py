"""
Unit tests для селективной очистки при переключении агентов.

Тестирует метод clear_tool_messages_with_context в Session entity.
"""

import pytest
from datetime import datetime, timezone

from app.domain.entities.session import Session
from app.domain.entities.message import Message


class TestSessionAgentSwitch:
    """Тесты для селективной очистки при переключении агентов"""
    
    def test_clear_tool_messages_with_context_basic(self):
        """Тест базовой очистки tool messages с контекстом"""
        session = Session(id="session-1")
        
        # Добавить user message
        session.add_message(Message(
            id="msg-1",
            role="user",
            content="Create a file"
        ))
        
        # Добавить assistant message с tool_calls
        session.add_message(Message(
            id="msg-2",
            role="assistant",
            content="I'll create the file",
            tool_calls=[{
                "id": "call-1",
                "type": "function",
                "function": {"name": "write_file", "arguments": "{}"}
            }]
        ))
        
        # Добавить tool result
        session.add_message(Message(
            id="msg-3",
            role="tool",
            content="File created",
            tool_call_id="call-1"
        ))
        
        # Добавить assistant message с результатом
        session.add_message(Message(
            id="msg-4",
            role="assistant",
            content="File created successfully"
        ))
        
        assert len(session.messages) == 4
        
        # Выполнить селективную очистку
        info = session.clear_tool_messages_with_context(
            from_agent="orchestrator",
            to_agent="coder"
        )
        
        # Проверить результаты
        assert info["removed_count"] == 2  # tool_call и tool_result
        assert info["preserved_result"] == "File created successfully"
        assert "orchestrator → coder" in info["context_message"]
        
        # Проверить структуру сообщений после очистки
        # Должно быть: user, assistant (preserved), system (context)
        assert len(session.messages) == 3
        assert session.messages[0].role == "user"
        assert session.messages[1].role == "assistant"
        assert session.messages[1].content == "File created successfully"
        assert session.messages[2].role == "system"
        assert "Agent switched" in session.messages[2].content
    
    def test_clear_tool_messages_with_context_no_result(self):
        """Тест очистки когда нет результата для сохранения"""
        session = Session(id="session-1")
        
        # Добавить только tool messages без финального результата
        session.add_message(Message(
            id="msg-1",
            role="assistant",
            content="Processing",
            tool_calls=[{
                "id": "call-1",
                "type": "function",
                "function": {"name": "write_file", "arguments": "{}"}
            }]
        ))
        
        session.add_message(Message(
            id="msg-2",
            role="tool",
            content="File created",
            tool_call_id="call-1"
        ))
        
        assert len(session.messages) == 2
        
        # Выполнить очистку
        info = session.clear_tool_messages_with_context(
            from_agent="coder",
            to_agent="debug"
        )
        
        # Проверить что tool messages удалены
        assert info["removed_count"] == 2
        assert info["preserved_result"] is None
        
        # Должно остаться только system message
        assert len(session.messages) == 1
        assert session.messages[0].role == "system"
        assert "coder → debug" in session.messages[0].content
    
    def test_clear_tool_messages_with_context_multiple_tool_calls(self):
        """Тест очистки с множественными tool calls"""
        session = Session(id="session-1")
        
        # Добавить несколько tool calls
        session.add_message(Message(
            id="msg-1",
            role="assistant",
            content="Processing multiple tools",
            tool_calls=[
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": "{}"}
                },
                {
                    "id": "call-2",
                    "type": "function",
                    "function": {"name": "write_file", "arguments": "{}"}
                }
            ]
        ))
        
        # Добавить tool results
        session.add_message(Message(
            id="msg-2",
            role="tool",
            content="File read",
            tool_call_id="call-1"
        ))
        
        session.add_message(Message(
            id="msg-3",
            role="tool",
            content="File written",
            tool_call_id="call-2"
        ))
        
        # Добавить финальный результат
        session.add_message(Message(
            id="msg-4",
            role="assistant",
            content="All operations completed"
        ))
        
        assert len(session.messages) == 4
        
        # Выполнить очистку
        info = session.clear_tool_messages_with_context(
            from_agent="coder",
            to_agent="architect"
        )
        
        # Все tool messages должны быть удалены
        assert info["removed_count"] == 3  # 1 assistant с tool_calls + 2 tool results
        assert info["preserved_result"] == "All operations completed"
        
        # Проверить финальную структуру
        # Должно быть: assistant (preserved), system (context)
        assert len(session.messages) == 2
        assert session.messages[0].role == "assistant"
        assert session.messages[0].content == "All operations completed"
        assert session.messages[1].role == "system"
        assert "Agent switched" in session.messages[1].content
    
    def test_clear_tool_messages_with_context_preserves_user_messages(self):
        """Тест что user и system messages сохраняются"""
        session = Session(id="session-1")
        
        # Добавить разные типы сообщений
        session.add_message(Message(
            id="msg-1",
            role="user",
            content="User request"
        ))
        
        session.add_message(Message(
            id="msg-2",
            role="system",
            content="System context"
        ))
        
        session.add_message(Message(
            id="msg-3",
            role="assistant",
            content="Processing",
            tool_calls=[{
                "id": "call-1",
                "type": "function",
                "function": {"name": "test", "arguments": "{}"}
            }]
        ))
        
        session.add_message(Message(
            id="msg-4",
            role="tool",
            content="Result",
            tool_call_id="call-1"
        ))
        
        session.add_message(Message(
            id="msg-5",
            role="assistant",
            content="Done"
        ))
        
        assert len(session.messages) == 5
        
        # Выполнить очистку
        info = session.clear_tool_messages_with_context(
            from_agent="orchestrator",
            to_agent="ask"
        )
        
        # Проверить что user и system messages сохранены
        assert info["removed_count"] == 2
        
        # Должно быть: user, system (old), assistant (preserved), system (context)
        assert len(session.messages) == 4
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "User request"
        assert session.messages[1].role == "system"
        assert session.messages[1].content == "System context"
        assert session.messages[2].role == "assistant"
        assert session.messages[2].content == "Done"
        assert session.messages[3].role == "system"
        assert "Agent switched" in session.messages[3].content
    
    def test_clear_tool_messages_with_context_empty_session(self):
        """Тест очистки пустой сессии"""
        session = Session(id="session-1")
        
        assert len(session.messages) == 0
        
        # Выполнить очистку на пустой сессии
        info = session.clear_tool_messages_with_context(
            from_agent="orchestrator",
            to_agent="coder"
        )
        
        # Ничего не удалено, но context message добавлен
        assert info["removed_count"] == 0
        assert info["preserved_result"] is None
        assert len(session.messages) == 1
        assert session.messages[0].role == "system"
    
    def test_clear_tool_messages_with_context_marks_updated(self):
        """Тест что сессия помечается как обновленная"""
        session = Session(id="session-1")
        
        # Добавить tool messages
        session.add_message(Message(
            id="msg-1",
            role="assistant",
            content="Test",
            tool_calls=[{
                "id": "call-1",
                "type": "function",
                "function": {"name": "test", "arguments": "{}"}
            }]
        ))
        
        # Сбросить флаг обновления
        original_updated = session.updated_at
        
        # Выполнить очистку
        session.clear_tool_messages_with_context(
            from_agent="test1",
            to_agent="test2"
        )
        
        # Проверить что updated_at изменился
        assert session.updated_at >= original_updated
    
    def test_clear_tool_messages_with_context_return_structure(self):
        """Тест структуры возвращаемого словаря"""
        session = Session(id="session-1")
        
        session.add_message(Message(
            id="msg-1",
            role="assistant",
            content="Test",
            tool_calls=[{
                "id": "call-1",
                "type": "function",
                "function": {"name": "test", "arguments": "{}"}
            }]
        ))
        
        info = session.clear_tool_messages_with_context(
            from_agent="agent1",
            to_agent="agent2"
        )
        
        # Проверить все ключи в результате
        assert "removed_count" in info
        assert "preserved_result" in info
        assert "context_message" in info
        assert "final_message_count" in info
        
        assert isinstance(info["removed_count"], int)
        assert isinstance(info["context_message"], str)
        assert isinstance(info["final_message_count"], int)
        assert info["final_message_count"] == len(session.messages)
