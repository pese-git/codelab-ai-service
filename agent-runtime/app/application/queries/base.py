"""
Базовые классы для запросов (Queries).

Запрос представляет намерение получить данные без изменения состояния.
Query Handler обрабатывает запрос и возвращает данные.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from pydantic import BaseModel


# Тип переменная для результата запроса
TResult = TypeVar('TResult')


class Query(BaseModel, ABC):
    """
    Базовый класс для запросов.
    
    Запрос - это объект, который представляет намерение
    получить данные без изменения состояния системы.
    
    Запросы должны быть:
    - Неизменяемыми (immutable)
    - Самодостаточными (содержать все параметры запроса)
    - Валидируемыми (через Pydantic)
    
    Важно: Запросы НЕ должны изменять состояние системы!
    
    Пример:
        >>> class GetUserQuery(Query):
        ...     user_id: str
        >>> 
        >>> query = GetUserQuery(user_id="user-1")
    """
    
    class Config:
        """Конфигурация Pydantic модели"""
        # Запросы неизменяемы
        frozen = True


class QueryHandler(ABC, Generic[TResult]):
    """
    Базовый класс для обработчиков запросов.
    
    Query Handler отвечает за выполнение запроса:
    - Получение данных из репозиториев
    - Преобразование в DTO
    - Возврат результата
    
    Важно: Query Handler НЕ должен изменять состояние системы!
    
    Type Parameters:
        TResult: Тип результата выполнения запроса
    
    Пример:
        >>> class GetUserHandler(QueryHandler[UserDTO]):
        ...     async def handle(self, query: GetUserQuery) -> UserDTO:
        ...         # Получить пользователя из репозитория
        ...         user = await self._repository.get(query.user_id)
        ...         # Преобразовать в DTO
        ...         return UserDTO.from_entity(user)
    """
    
    @abstractmethod
    async def handle(self, query: Query) -> TResult:
        """
        Обработать запрос.
        
        Args:
            query: Запрос для обработки
            
        Returns:
            Результат выполнения запроса
            
        Raises:
            DomainError: При ошибках бизнес-логики
            InfrastructureError: При ошибках инфраструктуры
        """
        pass
