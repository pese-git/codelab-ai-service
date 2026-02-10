"""
Тесты для ConversationManagementService.

Проверяет функциональность нового сервиса управления conversations.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from app.domain.session_context.services import ConversationManagementService
from app.domain.session_context.entities import Conversation
from app.domain.session_context.value_objects import ConversationId
from app.domain.entities.message import Message
from app.core.errors import SessionNotFoundError, SessionAlreadyExistsError


@pytest.fixture
def mock_repository():
    """Mock repository для тестов."""
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    repo.find_active = AsyncMock(return_value=[])
    repo.cleanup_old = AsyncMock(return_value=0)
    repo.save_snapshot = AsyncMock()
    repo.get_snapshot = AsyncMock(return_value=None)
    repo.delete_snapshot = AsyncMock()
    return repo


@pytest.fixture
def service(mock_repository):
    """Сервис для тестов."""
    return ConversationManagementService(repository=mock_repository)


@pytest.mark.asyncio
class TestConversationManagementService:
    """Тесты для ConversationManagementService."""
    
    async def test_create_conversation_generates_id_if_not_provided(
        self,
        service,
        mock_repository
    ):
        """Тест: создание conversation с автогенерацией ID."""
        # Act
        conversation = await service.create_conversation()
        
        # Assert
        assert conversation is not None
        assert conversation.conversation_id is not None
        assert conversation.is_active is True
        mock_repository.save.assert_called_once()
    
    async def test_create_conversation_with_provided_id(
        self,
        service,
        mock_repository
    ):
        """Тест: создание conversation с указанным ID."""
        # Arrange
        conv_id = "test-conv-123"
        
        # Act
        conversation = await service.create_conversation(conversation_id=conv_id)
        
        # Assert
        assert conversation.conversation_id.value == conv_id
        mock_repository.save.assert_called_once()
    
    async def test_create_conversation_raises_if_exists(
        self,
        service,
        mock_repository
    ):
        """Тест: ошибка при создании существующей conversation."""
        # Arrange
        conv_id = "existing-conv"
        existing = Conversation.create(ConversationId(value=conv_id))
        mock_repository.find_by_id.return_value = existing
        
        # Act & Assert
        with pytest.raises(SessionAlreadyExistsError):
            await service.create_conversation(conversation_id=conv_id)
    
    async def test_get_conversation_returns_existing(
        self,
        service,
        mock_repository
    ):
        """Тест: получение существующей conversation."""
        # Arrange
        conv_id = "test-conv"
        expected = Conversation.create(ConversationId(value=conv_id))
        mock_repository.find_by_id.return_value = expected
        
        # Act
        result = await service.get_conversation(conv_id)
        
        # Assert
        assert result == expected
        mock_repository.find_by_id.assert_called_once()
    
    async def test_get_conversation_raises_if_not_found(
        self,
        service,
        mock_repository
    ):
        """Тест: ошибка при получении несуществующей conversation."""
        # Arrange
        mock_repository.find_by_id.return_value = None
        
        # Act & Assert
        with pytest.raises(SessionNotFoundError):
            await service.get_conversation("non-existent")
    
    async def test_get_or_create_conversation_returns_existing(
        self,
        service,
        mock_repository
    ):
        """Тест: get_or_create возвращает существующую conversation."""
        # Arrange
        conv_id = "test-conv"
        existing = Conversation.create(ConversationId(value=conv_id))
        mock_repository.find_by_id.return_value = existing
        
        # Act
        result = await service.get_or_create_conversation(conv_id)
        
        # Assert
        assert result == existing
        mock_repository.save.assert_not_called()
    
    async def test_get_or_create_conversation_creates_new(
        self,
        service,
        mock_repository
    ):
        """Тест: get_or_create создает новую conversation."""
        # Arrange
        conv_id = "new-conv"
        mock_repository.find_by_id.return_value = None
        
        # Act
        result = await service.get_or_create_conversation(conv_id)
        
        # Assert
        assert result.conversation_id.value == conv_id
        mock_repository.save.assert_called_once()
    
    async def test_add_message_to_conversation(
        self,
        service,
        mock_repository
    ):
        """Тест: добавление сообщения в conversation."""
        # Arrange
        conv_id = "test-conv"
        conversation = Conversation.create(ConversationId(value=conv_id))
        mock_repository.find_by_id.return_value = conversation
        
        # Act
        message = await service.add_message(
            conversation_id=conv_id,
            role="user",
            content="Hello!"
        )
        
        # Assert
        assert message.role == "user"
        assert message.content == "Hello!"
        assert conversation.messages.count() == 1
        mock_repository.save.assert_called_once()
    
    async def test_add_tool_result_with_success(
        self,
        service,
        mock_repository
    ):
        """Тест: добавление успешного результата инструмента."""
        # Arrange
        conv_id = "test-conv"
        conversation = Conversation.create(ConversationId(value=conv_id))
        mock_repository.find_by_id.return_value = conversation
        
        # Act
        message = await service.add_tool_result(
            conversation_id=conv_id,
            call_id="call-123",
            result="Success"
        )
        
        # Assert
        assert message.role == "tool"
        assert message.content == "Success"
        assert message.tool_call_id == "call-123"
    
    async def test_add_tool_result_with_error(
        self,
        service,
        mock_repository
    ):
        """Тест: добавление результата инструмента с ошибкой."""
        # Arrange
        conv_id = "test-conv"
        conversation = Conversation.create(ConversationId(value=conv_id))
        mock_repository.find_by_id.return_value = conversation
        
        # Act
        message = await service.add_tool_result(
            conversation_id=conv_id,
            call_id="call-123",
            error="File not found"
        )
        
        # Assert
        assert message.role == "tool"
        assert "Error: File not found" in message.content
    
    async def test_deactivate_conversation(
        self,
        service,
        mock_repository
    ):
        """Тест: деактивация conversation."""
        # Arrange
        conv_id = "test-conv"
        conversation = Conversation.create(ConversationId(value=conv_id))
        mock_repository.find_by_id.return_value = conversation
        
        # Act
        result = await service.deactivate_conversation(
            conversation_id=conv_id,
            reason="Test deactivation"
        )
        
        # Assert
        assert result.is_active is False
        mock_repository.save.assert_called_once()
    
    async def test_list_active_conversations(
        self,
        service,
        mock_repository
    ):
        """Тест: получение списка активных conversations."""
        # Arrange
        conversations = [
            Conversation.create(ConversationId(value="conv-1")),
            Conversation.create(ConversationId(value="conv-2"))
        ]
        mock_repository.find_active.return_value = conversations
        
        # Act
        result = await service.list_active_conversations(limit=10)
        
        # Assert
        assert len(result) == 2
        mock_repository.find_active.assert_called_once_with(limit=10, offset=0)
    
    async def test_cleanup_old_conversations(
        self,
        service,
        mock_repository
    ):
        """Тест: очистка старых conversations."""
        # Arrange
        mock_repository.cleanup_old.return_value = 5
        
        # Act
        count = await service.cleanup_old_conversations(max_age_hours=24)
        
        # Assert
        assert count == 5
        mock_repository.cleanup_old.assert_called_once_with(max_age_hours=24)
    
    async def test_create_subtask_context(
        self,
        service,
        mock_repository
    ):
        """Тест: создание контекста для subtask."""
        # Arrange
        conv_id = "test-conv"
        conversation = Conversation.create(ConversationId(value=conv_id))
        # Добавить несколько сообщений
        conversation.add_message(Message(id="1", role="user", content="Test"))
        conversation.add_message(Message(id="2", role="assistant", content="Response"))
        mock_repository.find_by_id.return_value = conversation
        
        # Act
        snapshot_id = await service.create_subtask_context(
            conversation_id=conv_id,
            subtask_id="subtask-1",
            dependency_results={"dep-1": {"result": "Done"}}
        )
        
        # Assert
        assert snapshot_id == f"{conv_id}_snapshot_subtask-1"
        mock_repository.save_snapshot.assert_called_once()
        mock_repository.save.assert_called()
    
    async def test_restore_from_snapshot(
        self,
        service,
        mock_repository
    ):
        """Тест: восстановление из snapshot."""
        # Arrange
        conv_id = "test-conv"
        conversation = Conversation.create(ConversationId(value=conv_id))
        conversation.add_message(Message(id="1", role="user", content="Test"))
        mock_repository.find_by_id.return_value = conversation
        
        snapshot = {
            "conversation_id": conv_id,
            "messages": [],
            "metadata": {},
            "message_count": 0
        }
        mock_repository.get_snapshot.return_value = snapshot
        
        # Act
        await service.restore_from_snapshot(
            conversation_id=conv_id,
            snapshot_id="snapshot-1",
            preserve_last_result=False
        )
        
        # Assert
        mock_repository.get_snapshot.assert_called_once()
        mock_repository.save.assert_called_once()
        mock_repository.delete_snapshot.assert_called_once()
    
    async def test_prepare_agent_switch_context(
        self,
        service,
        mock_repository
    ):
        """Тест: подготовка контекста для переключения агента."""
        # Arrange
        conv_id = "test-conv"
        conversation = Conversation.create(ConversationId(value=conv_id))
        conversation.add_message(Message(id="1", role="user", content="Test"))
        mock_repository.find_by_id.return_value = conversation
        
        # Act
        info = await service.prepare_agent_switch_context(
            conversation_id=conv_id,
            from_agent="orchestrator",
            to_agent="coder"
        )
        
        # Assert
        assert "removed_count" in info
        assert "final_message_count" in info
        mock_repository.save.assert_called_once()
    
    async def test_format_dependency_context(self, service):
        """Тест: форматирование контекста зависимостей."""
        # Arrange
        dependency_results = {
            "subtask-1": {
                "description": "Create file",
                "agent": "coder",
                "result": "File created"
            }
        }
        
        # Act
        context = service._format_dependency_context(dependency_results)
        
        # Assert
        assert "Previous subtask results:" in context
        assert "Create file" in context
        assert "coder" in context
        assert "File created" in context
