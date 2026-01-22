"""
Базовый интерфейс репозитория.

Репозиторий (Repository) - это паттерн, который инкапсулирует логику
доступа к данным и предоставляет коллекционно-подобный интерфейс
для работы с доменными сущностями.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List

from ..entities.base import Entity

# Тип переменная для сущности
T = TypeVar('T', bound=Entity)


class Repository(ABC, Generic[T]):
    """
    Базовый интерфейс репозитория.
    
    Определяет стандартные операции CRUD для работы с сущностями.
    Конкретные репозитории должны наследоваться от этого класса
    и реализовывать все абстрактные методы.
    
    Type Parameters:
        T: Тип доменной сущности, с которой работает репозиторий
    
    Пример:
        >>> class UserRepository(Repository[User]):
        ...     async def get(self, id: str) -> Optional[User]:
        ...         # Реализация получения пользователя
        ...         pass
    """
    
    @abstractmethod
    async def get(self, id: str) -> Optional[T]:
        """
        Получить сущность по ID.
        
        Args:
            id: Уникальный идентификатор сущности
            
        Returns:
            Сущность если найдена, None иначе
            
        Пример:
            >>> user = await repository.get("user-123")
            >>> if user:
            ...     print(f"Found user: {user.name}")
        """
        pass
    
    @abstractmethod
    async def save(self, entity: T) -> None:
        """
        Сохранить сущность.
        
        Создает новую сущность или обновляет существующую.
        Операция должна быть идемпотентной.
        
        Args:
            entity: Сущность для сохранения
            
        Raises:
            RepositoryError: При ошибке сохранения
            
        Пример:
            >>> user = User(id="user-123", name="John")
            >>> await repository.save(user)
        """
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """
        Удалить сущность по ID.
        
        Args:
            id: Уникальный идентификатор сущности
            
        Returns:
            True если сущность была удалена, False если не найдена
            
        Пример:
            >>> deleted = await repository.delete("user-123")
            >>> if deleted:
            ...     print("User deleted successfully")
        """
        pass
    
    @abstractmethod
    async def list(
        self, 
        limit: int = 100, 
        offset: int = 0
    ) -> List[T]:
        """
        Получить список сущностей с пагинацией.
        
        Args:
            limit: Максимальное количество сущностей для возврата
            offset: Смещение от начала списка
            
        Returns:
            Список сущностей
            
        Пример:
            >>> # Получить первые 10 пользователей
            >>> users = await repository.list(limit=10, offset=0)
            >>> 
            >>> # Получить следующие 10 пользователей
            >>> next_users = await repository.list(limit=10, offset=10)
        """
        pass
    
    @abstractmethod
    async def exists(self, id: str) -> bool:
        """
        Проверить существование сущности.
        
        Args:
            id: Уникальный идентификатор сущности
            
        Returns:
            True если сущность существует, False иначе
            
        Пример:
            >>> if await repository.exists("user-123"):
            ...     print("User exists")
        """
        pass
    
    @abstractmethod
    async def count(self) -> int:
        """
        Получить общее количество сущностей.
        
        Returns:
            Количество сущностей в репозитории
            
        Пример:
            >>> total = await repository.count()
            >>> print(f"Total users: {total}")
        """
        pass
