"""
Базовые классы для команд (Commands).

Команда представляет намерение изменить состояние системы.
Command Handler обрабатывает команду и выполняет соответствующие действия.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from pydantic import BaseModel


# Тип переменная для результата команды
TResult = TypeVar('TResult')


class Command(BaseModel, ABC):
    """
    Базовый класс для команд.
    
    Команда - это объект, который представляет намерение
    изменить состояние системы. Команды всегда именуются
    в повелительном наклонении (CreateSession, AddMessage и т.д.).
    
    Команды должны быть:
    - Неизменяемыми (immutable)
    - Самодостаточными (содержать все необходимые данные)
    - Валидируемыми (через Pydantic)
    
    Пример:
        >>> class CreateUserCommand(Command):
        ...     user_id: str
        ...     name: str
        ...     email: str
        >>> 
        >>> command = CreateUserCommand(
        ...     user_id="user-1",
        ...     name="John",
        ...     email="john@example.com"
        ... )
    """
    
    class Config:
        """Конфигурация Pydantic модели"""
        # Команды неизменяемы
        frozen = True


class CommandHandler(ABC, Generic[TResult]):
    """
    Базовый класс для обработчиков команд.
    
    Command Handler отвечает за выполнение команды:
    - Валидация бизнес-правил
    - Вызов доменных сервисов
    - Публикация событий
    - Возврат результата
    
    Type Parameters:
        TResult: Тип результата выполнения команды
    
    Пример:
        >>> class CreateUserHandler(CommandHandler[User]):
        ...     async def handle(self, command: CreateUserCommand) -> User:
        ...         # Создать пользователя через доменный сервис
        ...         user = await self._service.create_user(...)
        ...         return user
    """
    
    @abstractmethod
    async def handle(self, command: Command) -> TResult:
        """
        Обработать команду.
        
        Args:
            command: Команда для обработки
            
        Returns:
            Результат выполнения команды
            
        Raises:
            DomainError: При нарушении бизнес-правил
            InfrastructureError: При ошибках инфраструктуры
        """
        pass
