"""
Доменный сервис обработки ответов LLM.

Применяет бизнес-правила к ответам от LLM:
- Валидация tool calls
- Проверка HITL политики
- Применение ограничений
"""

import logging
from typing import Tuple, Optional

from ..entities.llm_response import LLMResponse, ProcessedResponse, ToolCall
from .hitl_policy import HITLPolicyService

logger = logging.getLogger("agent-runtime.domain.llm_response_processor")


class LLMResponseProcessor:
    """
    Доменный сервис обработки ответов LLM.
    
    Инкапсулирует бизнес-правила обработки ответов от LLM:
    1. Валидация количества tool calls (только один за раз)
    2. Проверка HITL политики для инструментов
    3. Валидация содержимого ответа
    
    Атрибуты:
        _hitl_policy: Сервис HITL политики
    
    Пример:
        >>> processor = LLMResponseProcessor(hitl_policy_service)
        >>> response = LLMResponse(...)
        >>> processed = processor.process_response(response)
        >>> if processed.requires_approval:
        ...     print(f"Approval required: {processed.approval_reason}")
    """
    
    def __init__(self, hitl_policy: HITLPolicyService):
        """
        Инициализация процессора.
        
        Args:
            hitl_policy: Сервис HITL политики для проверки необходимости одобрения
        """
        self._hitl_policy = hitl_policy
    
    def process_response(self, response: LLMResponse) -> ProcessedResponse:
        """
        Обработать ответ LLM согласно бизнес-правилам.
        
        Применяет следующие бизнес-правила:
        1. Агент может вызвать только ОДИН инструмент за раз
        2. Некоторые инструменты требуют одобрения пользователя (HITL)
        3. Пустой content допустим только при наличии tool_calls
        
        Args:
            response: Сырой ответ от LLM
            
        Returns:
            ProcessedResponse с примененными бизнес-правилами
            
        Пример:
            >>> response = LLMResponse(
            ...     content="",
            ...     tool_calls=[tool_call1, tool_call2],
            ...     usage=usage,
            ...     model="gpt-4"
            ... )
            >>> processed = processor.process_response(response)
            >>> len(processed.tool_calls)  # Только первый tool call
            1
            >>> len(processed.validation_warnings)  # Есть предупреждение
            1
        """
        validation_warnings = []
        tool_calls = response.tool_calls
        
        # Бизнес-правило 1: Только один tool call за раз
        if len(response.tool_calls) > 1:
            warning = (
                f"LLM attempted to call {len(response.tool_calls)} tools simultaneously. "
                f"Only the first tool will be executed. "
                f"Tools: {[tc.tool_name for tc in response.tool_calls]}"
            )
            logger.warning(warning)
            validation_warnings.append(warning)
            
            # Берем только первый tool call
            tool_calls = [response.tool_calls[0]]
        
        # Бизнес-правило 2: Проверка HITL политики
        requires_approval = False
        approval_reason = None
        
        if tool_calls:
            tool_call = tool_calls[0]
            requires_approval, approval_reason = self._hitl_policy.requires_approval(
                tool_call.tool_name
            )
            
            logger.debug(
                f"Tool '{tool_call.tool_name}' requires_approval={requires_approval}"
                f"{f', reason={approval_reason}' if approval_reason else ''}"
            )
        
        # Бизнес-правило 3: Валидация содержимого
        content = response.content
        if not content.strip() and not tool_calls:
            warning = "LLM returned empty content without tool calls"
            logger.warning(warning)
            validation_warnings.append(warning)
        
        # Создание ProcessedResponse
        return ProcessedResponse(
            content=content,
            tool_calls=tool_calls,
            usage=response.usage,
            model=response.model,
            requires_approval=requires_approval,
            approval_reason=approval_reason,
            validation_warnings=validation_warnings
        )
    
    def validate_tool_call(self, tool_call: ToolCall) -> Tuple[bool, Optional[str]]:
        """
        Валидировать отдельный tool call.
        
        Проверяет:
        1. Наличие обязательных полей
        2. Корректность аргументов
        
        Args:
            tool_call: Вызов инструмента для валидации
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
            
        Пример:
            >>> is_valid, error = processor.validate_tool_call(tool_call)
            >>> if not is_valid:
            ...     print(f"Invalid tool call: {error}")
        """
        # Проверка наличия ID
        if not tool_call.id:
            return False, "Tool call ID is required"
        
        # Проверка наличия имени инструмента
        if not tool_call.tool_name:
            return False, "Tool name is required"
        
        # Проверка аргументов (должен быть dict)
        if not isinstance(tool_call.arguments, dict):
            return False, f"Tool arguments must be a dict, got {type(tool_call.arguments)}"
        
        return True, None
