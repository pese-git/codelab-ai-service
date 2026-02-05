"""
Базовые классы для Use Cases.

Определяют контракты для всех Use Cases в приложении.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, AsyncGenerator

# Type variables для generic типов
TRequest = TypeVar('TRequest')
TResponse = TypeVar('TResponse')


class UseCase(ABC, Generic[TRequest, TResponse]):
    """
    Базовый класс для Use Case с единичным результатом.
    
    Use Case инкапсулирует один сценарий использования приложения.
    Координирует работу доменных сервисов для выполнения задачи.
    
    Type Parameters:
        TRequest: Тип входного запроса
        TResponse: Тип результата
    
    Принципы:
        - Одна ответственность (Single Responsibility)
        - Координация, а не бизнес-логика
        - Бизнес-логика остается в Domain Layer
        - Легко тестируется через моки зависимостей
    
    Пример:
        >>> class CreateSessionUseCase(UseCase[CreateSessionRequest, Session]):
        ...     def __init__(self, session_service: SessionService):
        ...         self._session_service = session_service
        ...     
        ...     async def execute(self, request: CreateSessionRequest) -> Session:
        ...         return await self._session_service.create(request.session_id)
    """
    
    @abstractmethod
    async def execute(self, request: TRequest) -> TResponse:
        """
        Выполнить Use Case.
        
        Args:
            request: Входной запрос с параметрами
            
        Returns:
            Результат выполнения Use Case
            
        Raises:
            Специфичные для Use Case исключения
        """
        pass


class StreamingUseCase(ABC, Generic[TRequest, TResponse]):
    """
    Базовый класс для Use Case с потоковым результатом.
    
    Используется для Use Cases, которые возвращают результат
    в виде асинхронного потока (например, SSE streaming).
    
    Type Parameters:
        TRequest: Тип входного запроса
        TResponse: Тип элементов потока
    
    Принципы:
        - Те же что и для UseCase
        - Поддержка streaming для real-time ответов
        - Обработка ошибок в потоке
    
    Пример:
        >>> class ProcessMessageUseCase(StreamingUseCase[ProcessMessageRequest, StreamChunk]):
        ...     def __init__(self, message_processor: MessageProcessor):
        ...         self._message_processor = message_processor
        ...     
        ...     async def execute(self, request: ProcessMessageRequest) -> AsyncGenerator[StreamChunk, None]:
        ...         async for chunk in self._message_processor.process(request.session_id, request.message):
        ...             yield chunk
    """
    
    @abstractmethod
    async def execute(self, request: TRequest) -> AsyncGenerator[TResponse, None]:
        """
        Выполнить Use Case с потоковым результатом.
        
        Args:
            request: Входной запрос с параметрами
            
        Yields:
            Элементы результата в виде потока
            
        Raises:
            Специфичные для Use Case исключения
        """
        pass
        # Нужен yield для корректной сигнатуры generator
        yield  # type: ignore
