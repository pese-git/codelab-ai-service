"""
Unit тесты для snapshot механизма Session Entity.

Проверяет функциональность изоляции контекста между subtasks.
"""

import pytest
from datetime import datetime, timezone

from app.domain.entities.session import Session
from app.domain.entities.message import Message


class TestSessionSnapshot:
    """Тесты для snapshot механизма Session"""
    
    def test_create_snapshot(self):
        """Тест создания snapshot сессии"""
        # Arrange
        session = Session(id="test-session")
        session.add_message(Message(
            id="msg-1",
            role="user",
            content="Hello"
        ))
        session.add_message(Message(
            id="msg-2",
            role="assistant",
            content="Hi there"
        ))
        
        # Act
        snapshot = session.create_snapshot()
        
        # Assert
        assert snapshot is not None
        assert "messages" in snapshot
        assert "metadata" in snapshot
        assert "created_at" in snapshot
        assert snapshot["message_count"] == 2
        assert len(snapshot["messages"]) == 2
    
    def test_restore_from_snapshot(self):
        """Тест восстановления сессии из snapshot"""
        # Arrange
        session = Session(id="test-session")
        session.add_message(Message(
            id="msg-1",
            role="user",
            content="Original message"
        ))
        
        snapshot = session.create_snapshot()
        
        # Добавить новые сообщения
        session.add_message(Message(
            id="msg-2",
            role="assistant",
            content="New message"
        ))
        
        assert len(session.messages) == 2
        
        # Act
        session.restore_from_snapshot(snapshot)
        
        # Assert
        assert len(session.messages) == 1
        assert session.messages[0].content == "Original message"
    
    def test_clear_tool_messages(self):
        """Тест очистки tool-related messages"""
        # Arrange
        session = Session(id="test-session")
        
        # Добавить разные типы сообщений
        session.add_message(Message(
            id="msg-1",
            role="user",
            content="User message"
        ))
        session.add_message(Message(
            id="msg-2",
            role="system",
            content="System message"
        ))
        session.add_message(Message(
            id="msg-3",
            role="assistant",
            content="",
            tool_calls=[{"id": "call-1", "name": "test_tool"}]
        ))
        session.add_message(Message(
            id="msg-4",
            role="tool",
            content="Tool result",
            tool_call_id="call-1"
        ))
        session.add_message(Message(
            id="msg-5",
            role="assistant",
            content="Final response"
        ))
        
        assert len(session.messages) == 5
        
        # Act
        cleared_count = session.clear_tool_messages()
        
        # Assert
        assert cleared_count == 2  # assistant с tool_calls + tool result
        assert len(session.messages) == 3
        
        # Проверить, что остались правильные сообщения
        roles = [msg.role for msg in session.messages]
        assert "user" in roles
        assert "system" in roles
        assert "assistant" in roles
        assert "tool" not in roles
        
        # Проверить, что assistant с tool_calls удален
        for msg in session.messages:
            if msg.role == "assistant":
                assert not msg.tool_calls
    
    def test_get_last_assistant_message(self):
        """Тест получения последнего assistant message без tool_calls"""
        # Arrange
        session = Session(id="test-session")
        
        session.add_message(Message(
            id="msg-1",
            role="assistant",
            content="First response"
        ))
        session.add_message(Message(
            id="msg-2",
            role="assistant",
            content="",
            tool_calls=[{"id": "call-1"}]
        ))
        session.add_message(Message(
            id="msg-3",
            role="assistant",
            content="Last response"
        ))
        
        # Act
        last_msg = session.get_last_assistant_message()
        
        # Assert
        assert last_msg is not None
        assert last_msg.content == "Last response"
        assert not last_msg.tool_calls
    
    def test_get_last_assistant_message_none(self):
        """Тест когда нет assistant messages без tool_calls"""
        # Arrange
        session = Session(id="test-session")
        
        session.add_message(Message(
            id="msg-1",
            role="user",
            content="User message"
        ))
        session.add_message(Message(
            id="msg-2",
            role="assistant",
            content="",
            tool_calls=[{"id": "call-1"}]
        ))
        
        # Act
        last_msg = session.get_last_assistant_message()
        
        # Assert
        assert last_msg is None
    
    def test_snapshot_isolation_workflow(self):
        """
        Интеграционный тест: полный workflow изоляции subtask.
        
        Симулирует:
        1. Базовая история сессии
        2. Subtask 1 выполняется (tool_call + tool_result)
        3. Snapshot создается перед Subtask 2
        4. Tool messages очищаются
        5. Subtask 2 выполняется
        6. Восстановление из snapshot
        """
        # 1. Базовая история
        session = Session(id="test-session")
        session.add_message(Message(
            id="msg-1",
            role="user",
            content="Create TODO app"
        ))
        session.add_message(Message(
            id="msg-2",
            role="system",
            content="You are orchestrator agent"
        ))
        
        # 2. Subtask 1 выполняется
        session.add_message(Message(
            id="msg-3",
            role="assistant",
            content="",
            tool_calls=[{"id": "call-abc123", "name": "write_file"}]
        ))
        session.add_message(Message(
            id="msg-4",
            role="tool",
            content="File created",
            tool_call_id="call-abc123"
        ))
        session.add_message(Message(
            id="msg-5",
            role="assistant",
            content="Subtask 1 completed"
        ))
        
        assert len(session.messages) == 5
        
        # 3. Создать snapshot перед Subtask 2
        snapshot = session.create_snapshot()
        
        # 4. Очистить tool messages
        cleared = session.clear_tool_messages()
        assert cleared == 2  # tool_call + tool_result
        assert len(session.messages) == 3  # user + system + last assistant
        
        # 5. Добавить dependency context
        session.add_message(Message(
            id="msg-6",
            role="system",
            content="Previous subtask result: File created"
        ))
        
        # Subtask 2 выполняется (новый tool_call с другим ID)
        session.add_message(Message(
            id="msg-7",
            role="assistant",
            content="",
            tool_calls=[{"id": "call-xyz789", "name": "read_file"}]
        ))
        session.add_message(Message(
            id="msg-8",
            role="tool",
            content="File content",
            tool_call_id="call-xyz789"
        ))
        session.add_message(Message(
            id="msg-9",
            role="assistant",
            content="Subtask 2 completed"
        ))
        
        # 6. Восстановить из snapshot
        last_result = session.get_last_assistant_message()
        session.restore_from_snapshot(snapshot)
        
        # Добавить последний результат обратно
        if last_result:
            session.add_message(last_result)
        
        # Assert: Проверить финальное состояние
        assert len(session.messages) == 6  # 5 из snapshot + 1 last result
        
        # Проверить, что старый tool_call_id (call-abc123) присутствует
        tool_call_ids = []
        for msg in session.messages:
            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_call_ids.append(tc.get("id"))
            if msg.role == "tool" and msg.tool_call_id:
                tool_call_ids.append(msg.tool_call_id)
        
        # Должен быть только старый call-abc123, новый call-xyz789 удален
        assert "call-abc123" in tool_call_ids
        assert "call-xyz789" not in tool_call_ids
        
        # Последний assistant message сохранен
        assert session.messages[-1].content == "Subtask 2 completed"


class TestSessionSnapshotEdgeCases:
    """Тесты граничных случаев snapshot механизма"""
    
    def test_snapshot_empty_session(self):
        """Тест snapshot пустой сессии"""
        session = Session(id="empty-session")
        
        snapshot = session.create_snapshot()
        
        assert snapshot["message_count"] == 0
        assert len(snapshot["messages"]) == 0
    
    def test_restore_empty_snapshot(self):
        """Тест восстановления из пустого snapshot"""
        session = Session(id="test-session")
        session.add_message(Message(
            id="msg-1",
            role="user",
            content="Test"
        ))
        
        empty_snapshot = {
            "messages": [],
            "metadata": {},
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        session.restore_from_snapshot(empty_snapshot)
        
        assert len(session.messages) == 0
    
    def test_clear_tool_messages_no_tool_messages(self):
        """Тест очистки когда нет tool messages"""
        session = Session(id="test-session")
        session.add_message(Message(
            id="msg-1",
            role="user",
            content="User message"
        ))
        
        cleared = session.clear_tool_messages()
        
        assert cleared == 0
        assert len(session.messages) == 1
    
    def test_snapshot_preserves_metadata(self):
        """Тест сохранения metadata в snapshot"""
        session = Session(id="test-session")
        session.metadata["custom_key"] = "custom_value"
        session.metadata["plan_id"] = "plan-123"
        
        snapshot = session.create_snapshot()
        
        assert "metadata" in snapshot
        assert snapshot["metadata"]["custom_key"] == "custom_value"
        assert snapshot["metadata"]["plan_id"] == "plan-123"
    
    def test_restore_preserves_metadata(self):
        """Тест восстановления metadata из snapshot"""
        session = Session(id="test-session")
        session.metadata["original"] = "value"
        
        snapshot = session.create_snapshot()
        
        session.metadata["new"] = "data"
        session.restore_from_snapshot(snapshot)
        
        assert "original" in session.metadata
        assert "new" not in session.metadata
