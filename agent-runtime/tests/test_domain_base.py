"""
Тесты для базовых классов доменного слоя.

Проверяет корректность работы Entity, Repository и DomainEvent.
"""

import pytest
from datetime import datetime, timezone
from typing import Optional, List

from app.domain.entities.base import Entity
from app.domain.repositories.base import Repository
from app.domain.events.base import DomainEvent


# ==================== Тестовые классы ====================

class TestUser(Entity):
    """Тестовая сущность пользователя"""
    name: str
    email: str


class TestUserCreated(DomainEvent):
    """Тестовое доменное событие"""
    user_id: str
    email: str


class TestUserRepository(Repository[TestUser]):
    """Тестовая реализация репозитория"""
    
    def __init__(self):
        self._storage: dict[str, TestUser] = {}
    
    async def get(self, id: str) -> Optional[TestUser]:
        return self._storage.get(id)
    
    async def save(self, entity: TestUser) -> None:
        self._storage[entity.id] = entity
    
    async def delete(self, id: str) -> bool:
        if id in self._storage:
            del self._storage[id]
            return True
        return False
    
    async def list(self, limit: int = 100, offset: int = 0) -> List[TestUser]:
        users = list(self._storage.values())
        return users[offset:offset + limit]
    
    async def exists(self, id: str) -> bool:
        return id in self._storage
    
    async def count(self) -> int:
        return len(self._storage)


# ==================== Тесты Entity ====================

class TestEntity:
    """Тесты для базового класса Entity"""
    
    def test_entity_creation(self):
        """Тест создания сущности"""
        user = TestUser(
            id="user-1",
            name="John Doe",
            email="john@example.com"
        )
        
        assert user.id == "user-1"
        assert user.name == "John Doe"
        assert user.email == "john@example.com"
        assert isinstance(user.created_at, datetime)
        assert user.updated_at is None
    
    def test_entity_mark_updated(self):
        """Тест отметки обновления сущности"""
        user = TestUser(
            id="user-1",
            name="John Doe",
            email="john@example.com"
        )
        
        assert user.updated_at is None
        
        user.mark_updated()
        
        assert user.updated_at is not None
        assert isinstance(user.updated_at, datetime)
    
    def test_entity_equality(self):
        """Тест сравнения сущностей по ID"""
        user1 = TestUser(
            id="user-1",
            name="John Doe",
            email="john@example.com"
        )
        
        user2 = TestUser(
            id="user-1",
            name="Jane Doe",  # Другое имя
            email="jane@example.com"  # Другой email
        )
        
        user3 = TestUser(
            id="user-2",
            name="John Doe",
            email="john@example.com"
        )
        
        # Сущности с одинаковым ID равны
        assert user1 == user2
        
        # Сущности с разным ID не равны
        assert user1 != user3
    
    def test_entity_hash(self):
        """Тест хеширования сущностей"""
        user1 = TestUser(
            id="user-1",
            name="John Doe",
            email="john@example.com"
        )
        
        user2 = TestUser(
            id="user-1",
            name="Jane Doe",
            email="jane@example.com"
        )
        
        # Сущности с одинаковым ID имеют одинаковый хеш
        assert hash(user1) == hash(user2)
        
        # Можно использовать в множествах
        users_set = {user1, user2}
        assert len(users_set) == 1  # Только одна уникальная сущность
    
    def test_entity_repr(self):
        """Тест строкового представления сущности"""
        user = TestUser(
            id="user-1",
            name="John Doe",
            email="john@example.com"
        )
        
        repr_str = repr(user)
        assert "TestUser" in repr_str
        assert "user-1" in repr_str


# ==================== Тесты Repository ====================

class TestRepository:
    """Тесты для базового интерфейса Repository"""
    
    @pytest.mark.asyncio
    async def test_repository_save_and_get(self):
        """Тест сохранения и получения сущности"""
        repo = TestUserRepository()
        
        user = TestUser(
            id="user-1",
            name="John Doe",
            email="john@example.com"
        )
        
        await repo.save(user)
        
        retrieved = await repo.get("user-1")
        assert retrieved is not None
        assert retrieved.id == "user-1"
        assert retrieved.name == "John Doe"
    
    @pytest.mark.asyncio
    async def test_repository_get_nonexistent(self):
        """Тест получения несуществующей сущности"""
        repo = TestUserRepository()
        
        result = await repo.get("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_repository_delete(self):
        """Тест удаления сущности"""
        repo = TestUserRepository()
        
        user = TestUser(
            id="user-1",
            name="John Doe",
            email="john@example.com"
        )
        
        await repo.save(user)
        assert await repo.exists("user-1")
        
        deleted = await repo.delete("user-1")
        assert deleted is True
        assert not await repo.exists("user-1")
    
    @pytest.mark.asyncio
    async def test_repository_delete_nonexistent(self):
        """Тест удаления несуществующей сущности"""
        repo = TestUserRepository()
        
        deleted = await repo.delete("nonexistent")
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_repository_list(self):
        """Тест получения списка сущностей"""
        repo = TestUserRepository()
        
        # Создаем несколько пользователей
        for i in range(5):
            user = TestUser(
                id=f"user-{i}",
                name=f"User {i}",
                email=f"user{i}@example.com"
            )
            await repo.save(user)
        
        # Получаем всех
        users = await repo.list()
        assert len(users) == 5
        
        # Получаем с пагинацией
        users_page1 = await repo.list(limit=2, offset=0)
        assert len(users_page1) == 2
        
        users_page2 = await repo.list(limit=2, offset=2)
        assert len(users_page2) == 2
    
    @pytest.mark.asyncio
    async def test_repository_exists(self):
        """Тест проверки существования сущности"""
        repo = TestUserRepository()
        
        user = TestUser(
            id="user-1",
            name="John Doe",
            email="john@example.com"
        )
        
        assert not await repo.exists("user-1")
        
        await repo.save(user)
        
        assert await repo.exists("user-1")
    
    @pytest.mark.asyncio
    async def test_repository_count(self):
        """Тест подсчета сущностей"""
        repo = TestUserRepository()
        
        assert await repo.count() == 0
        
        for i in range(3):
            user = TestUser(
                id=f"user-{i}",
                name=f"User {i}",
                email=f"user{i}@example.com"
            )
            await repo.save(user)
        
        assert await repo.count() == 3


# ==================== Тесты DomainEvent ====================

class TestDomainEvent:
    """Тесты для базового класса DomainEvent"""
    
    def test_event_creation(self):
        """Тест создания доменного события"""
        event = TestUserCreated(
            aggregate_id="user-1",
            user_id="user-1",
            email="john@example.com"
        )
        
        assert event.aggregate_id == "user-1"
        assert event.user_id == "user-1"
        assert event.email == "john@example.com"
        assert isinstance(event.event_id, str)
        assert isinstance(event.occurred_at, datetime)
        assert event.event_version == 1
    
    def test_event_immutability(self):
        """Тест неизменяемости события"""
        event = TestUserCreated(
            aggregate_id="user-1",
            user_id="user-1",
            email="john@example.com"
        )
        
        # Попытка изменить поле должна вызвать ошибку
        with pytest.raises(Exception):  # Pydantic ValidationError
            event.user_id = "user-2"
    
    def test_event_to_dict(self):
        """Тест преобразования события в словарь"""
        event = TestUserCreated(
            aggregate_id="user-1",
            user_id="user-1",
            email="john@example.com"
        )
        
        event_dict = event.to_dict()
        
        assert isinstance(event_dict, dict)
        assert event_dict["aggregate_id"] == "user-1"
        assert event_dict["user_id"] == "user-1"
        assert event_dict["email"] == "john@example.com"
        assert "event_id" in event_dict
        assert "occurred_at" in event_dict
    
    def test_event_get_event_name(self):
        """Тест получения имени события"""
        event = TestUserCreated(
            aggregate_id="user-1",
            user_id="user-1",
            email="john@example.com"
        )
        
        assert event.get_event_name() == "TestUserCreated"
    
    def test_event_repr(self):
        """Тест строкового представления события"""
        event = TestUserCreated(
            aggregate_id="user-1",
            user_id="user-1",
            email="john@example.com"
        )
        
        repr_str = repr(event)
        assert "TestUserCreated" in repr_str
        assert "user-1" in repr_str
        assert event.event_id in repr_str
