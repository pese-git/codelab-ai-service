"""
Интерфейс для обработки стриминга LLM ответов.

Определяет контракт для обработчиков стриминга в соответствии с Clean Architecture.
Domain слой зависит только от интерфейса, а не от конкретной реализации.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any, Optional

from ...models.schemas import StreamChunk


class IStreamHandler(ABC):
    """
    Интерфейс для обработки стриминга LLM ответов.
    
    Определяет контракт для координации use case стриминга:
    - Фильтрация инструментов
    - Вызов LLM
    - Обработка ответа
    - Публикация событий
    - Сохранение результатов
    - Генерация стрима
    
    Реализации этого интерфейса находятся в Application слое,
    что позволяет Domain слою не зависеть от деталей реализации.
    
    Пример использования:
        >>> handler: IStreamHandler = get_stream_handler()
        >>> async for chunk in handler.handle(
        ...     session_id="session-1",
        ...     history=[{"role": "user", "content": "Hello"}],
        ...     model="gpt-4"
        ... ):
        ...     print(chunk)
    """
    
    @abstractmethod
    async def handle(
        self,
        session_id: str,
        history: List[Dict[str, Any]],
        model: str,
        allowed_tools: Optional[List[str]] = None,
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработать запрос на стриминг ответа от LLM.
        
        Координирует полный цикл обработки запроса:
        1. Фильтрация инструментов по разрешенным
        2. Публикация события начала запроса
        3. Вызов LLM через клиент
        4. Обработка ответа через доменные сервисы
        5. Обработка tool calls или обычного сообщения
        6. Публикация события завершения
        7. Генерация стрима для клиента
        
        Args:
            session_id: Уникальный идентификатор сессии
            history: История сообщений для контекста LLM
            model: Имя модели LLM для использования
            allowed_tools: Список разрешенных инструментов (None = все разрешены)
            correlation_id: Идентификатор для трассировки запроса (опционально)
            
        Yields:
            StreamChunk: Чанки данных для SSE стриминга к клиенту
            
        Raises:
            Exception: При ошибках вызова LLM или обработки ответа
            
        Пример:
            >>> async for chunk in handler.handle(
            ...     session_id="session-1",
            ...     history=[{"role": "user", "content": "Read file.txt"}],
            ...     model="gpt-4",
            ...     allowed_tools=["read_file", "write_file"]
            ... ):
            ...     if chunk.type == "tool_call":
            ...         print(f"Tool: {chunk.tool_name}")
            ...     elif chunk.type == "assistant_message":
            ...         print(f"Message: {chunk.content}")
            ...     elif chunk.type == "error":
            ...         print(f"Error: {chunk.error}")
        """
        pass
