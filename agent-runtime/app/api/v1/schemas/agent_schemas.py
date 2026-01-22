"""
API схемы для операций с агентами.

Определяет структуру запросов и ответов для endpoints агентов.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from ....application.dto import AgentContextDTO


class SwitchAgentRequest(BaseModel):
    """
    Запрос на переключение агента.
    
    Атрибуты:
        target_agent: Целевой агент
        reason: Причина переключения
        confidence: Уверенность (опционально)
    
    Пример:
        {
            "target_agent": "coder",
            "reason": "User requested code changes",
            "confidence": "high"
        }
    """
    
    target_agent: str = Field(description="Целевой агент (orchestrator, coder, architect, debug, ask)")
    reason: str = Field(description="Причина переключения")
    confidence: Optional[str] = Field(default=None, description="Уверенность (low, medium, high)")


class GetAgentContextResponse(BaseModel):
    """
    Ответ на получение контекста агента.
    
    Атрибуты:
        context: Данные контекста агента
    """
    
    context: AgentContextDTO = Field(description="Данные контекста агента")


class AgentInfoItem(BaseModel):
    """
    Информация об агенте.
    
    Атрибуты:
        type: Тип агента
        name: Название агента
        description: Описание
        allowed_tools: Разрешенные инструменты
        has_file_restrictions: Есть ли ограничения на файлы
    """
    
    type: str = Field(description="Тип агента")
    name: str = Field(description="Название агента")
    description: str = Field(description="Описание агента")
    allowed_tools: List[str] = Field(description="Разрешенные инструменты")
    has_file_restrictions: bool = Field(description="Есть ли ограничения на редактирование файлов")


class ListAgentsResponse(BaseModel):
    """
    Ответ на получение списка агентов.
    
    Атрибуты:
        agents: Список агентов
        total: Общее количество
    """
    
    agents: List[AgentInfoItem] = Field(description="Список агентов")
    total: int = Field(description="Общее количество агентов")
