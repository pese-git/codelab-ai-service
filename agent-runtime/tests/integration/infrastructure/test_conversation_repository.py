"""
Integration тесты для ConversationRepositoryImpl.

Тестирует взаимодействие с реальной БД через SQLAlchemy.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.persistence.models.base import Base
from app.infrastructure.persistence.repositories import ConversationRepositoryImpl
from app.domain.session_context.entities import Conversation
from app.domain.session_context.value_objects import ConversationId, MessageCollection
from app.domain.entities.message import Message


@pytest_asyncio.fixture
async def db_engine():
    """Создать in-memory SQLite engine для тестов."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Создать таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Создать сессию БД для тестов."""
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
def conversation_repository(db_session):
    """Создать ConversationRepositoryImpl."""
    return ConversationRepositoryImpl(db_session)


@pytest.fixture
def sample_conversation():
    """Создать тестовый conversation."""
    conv_id = ConversationId.generate()
    
    # Создаем напрямую без events для упрощения тестов
    conversation = Conversation(
        id=conv_id.value,
        conversation_id=conv_id,
        messages=MessageCollection.empty(),
        title="Test Conversation",
        description="Test description",
        is_active=True
    )
    
    # Добавить несколько сообщений
    msg1 = Message(
        id="msg-1",
        role="user",
        content="Hello",
        created_at=datetime.now(timezone.utc)
    )
    msg2 = Message(
        id="msg-2",
        role="assistant",
        content="Hi there!",
        created_at=datetime.now(timezone.utc)
    )
    
    # Добавляем напрямую в коллекцию
    conversation.messages = conversation.messages.add(msg1)
    conversation.messages = conversation.messages.add(msg2)
    
    return conversation


class TestConversationRepositoryImpl:
    """Тесты для ConversationRepositoryImpl."""
    
    @pytest.mark.asyncio
    async def test_save_and_find_by_id(
        self,
        conversation_repository,
        sample_conversation,
        db_session
    ):
        """Тест сохранения и поиска conversation по ID."""
        # Arrange
        conv_id = sample_conversation.conversation_id
        
        # Act - Save
        await conversation_repository.save(sample_conversation)
        await db_session.commit()
        
        # Act - Find
        found = await conversation_repository.find_by_id(conv_id)
        
        # Assert
        assert found is not None
        assert found.conversation_id.value == conv_id.value
        assert found.title == "Test Conversation"
        assert found.description == "Test description"
        assert found.messages.count() == 2
        assert found.is_active is True
    
    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, conversation_repository):
        """Тест поиска несуществующего conversation."""
        # Arrange
        non_existent_id = ConversationId.generate()
        
        # Act
        found = await conversation_repository.find_by_id(non_existent_id)
        
        # Assert
        assert found is None
    
    @pytest.mark.asyncio
    async def test_save_updates_existing(
        self,
        conversation_repository,
        sample_conversation,
        db_session
    ):
        """Тест обновления существующего conversation."""
        # Arrange
        conv_id = sample_conversation.conversation_id
        await conversation_repository.save(sample_conversation)
        await db_session.commit()
        
        # Act - Update
        found = await conversation_repository.find_by_id(conv_id)
        found.title = "Updated Title"
        msg3 = Message(
            id="msg-3",
            role="user",
            content="New message",
            created_at=datetime.now(timezone.utc)
        )
        found.add_message(msg3)
        
        await conversation_repository.save(found)
        await db_session.commit()
        
        # Assert
        updated = await conversation_repository.find_by_id(conv_id)
        assert updated.title == "Updated Title"
        assert updated.messages.count() == 3
    
    @pytest.mark.asyncio
    async def test_delete(
        self,
        conversation_repository,
        sample_conversation,
        db_session
    ):
        """Тест удаления conversation."""
        # Arrange
        conv_id = sample_conversation.conversation_id
        await conversation_repository.save(sample_conversation)
        await db_session.commit()
        
        # Act
        deleted = await conversation_repository.delete(conv_id)
        await db_session.commit()
        
        # Assert
        assert deleted is True
        found = await conversation_repository.find_by_id(conv_id)
        assert found is None
    
    @pytest.mark.asyncio
    async def test_delete_not_found(self, conversation_repository):
        """Тест удаления несуществующего conversation."""
        # Arrange
        non_existent_id = ConversationId.generate()
        
        # Act
        deleted = await conversation_repository.delete(non_existent_id)
        
        # Assert
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_exists(
        self,
        conversation_repository,
        sample_conversation,
        db_session
    ):
        """Тест проверки существования conversation."""
        # Arrange
        conv_id = sample_conversation.conversation_id
        
        # Act - Before save
        exists_before = await conversation_repository.exists(conv_id)
        
        # Save
        await conversation_repository.save(sample_conversation)
        await db_session.commit()
        
        # Act - After save
        exists_after = await conversation_repository.exists(conv_id)
        
        # Assert
        assert exists_before is False
        assert exists_after is True
    
    @pytest.mark.asyncio
    async def test_find_active_by_user_id(
        self,
        conversation_repository,
        db_session
    ):
        """Тест поиска активных conversations."""
        # Arrange - Create active and inactive conversations
        active_conv = Conversation.create(
            conversation_id=ConversationId.generate(),
            title="Active"
        )
        inactive_conv = Conversation.create(
            conversation_id=ConversationId.generate(),
            title="Inactive"
        )
        inactive_conv.deactivate("Test")
        
        await conversation_repository.save(active_conv)
        await conversation_repository.save(inactive_conv)
        await db_session.commit()
        
        # Act
        active_conversations = await conversation_repository.find_active_by_user_id(
            "user-123",
            limit=10
        )
        
        # Assert
        assert len(active_conversations) == 1
        assert active_conversations[0].title == "Active"
        assert active_conversations[0].is_active is True
    
    @pytest.mark.asyncio
    async def test_find_inactive_since(
        self,
        conversation_repository,
        db_session
    ):
        """Тест поиска неактивных conversations."""
        # Arrange
        old_conv = Conversation.create(
            conversation_id=ConversationId.generate(),
            title="Old Inactive"
        )
        old_conv.deactivate("Old")
        old_conv.last_activity = datetime.now(timezone.utc) - timedelta(days=10)
        
        recent_conv = Conversation.create(
            conversation_id=ConversationId.generate(),
            title="Recent Inactive"
        )
        recent_conv.deactivate("Recent")
        
        await conversation_repository.save(old_conv)
        await conversation_repository.save(recent_conv)
        await db_session.commit()
        
        # Act
        since = datetime.now(timezone.utc) - timedelta(days=5)
        inactive = await conversation_repository.find_inactive_since(since, limit=10)
        
        # Assert
        assert len(inactive) == 1
        assert inactive[0].title == "Old Inactive"
    
    @pytest.mark.asyncio
    async def test_count_by_user_id(
        self,
        conversation_repository,
        sample_conversation,
        db_session
    ):
        """Тест подсчета conversations."""
        # Arrange
        await conversation_repository.save(sample_conversation)
        
        conv2 = Conversation.create(
            conversation_id=ConversationId.generate(),
            title="Second"
        )
        await conversation_repository.save(conv2)
        await db_session.commit()
        
        # Act
        count = await conversation_repository.count_by_user_id("user-123")
        
        # Assert
        assert count == 2
    
    @pytest.mark.asyncio
    async def test_find_by_id_without_messages(
        self,
        conversation_repository,
        sample_conversation,
        db_session
    ):
        """Тест поиска conversation без загрузки сообщений."""
        # Arrange
        conv_id = sample_conversation.conversation_id
        await conversation_repository.save(sample_conversation)
        await db_session.commit()
        
        # Act
        found = await conversation_repository.find_by_id(conv_id, load_messages=False)
        
        # Assert
        assert found is not None
        assert found.conversation_id == conv_id
        assert found.messages.count() == 0  # Сообщения не загружены
