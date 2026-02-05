"""
Domain Service для валидации LLM ответов.

Инкапсулирует бизнес-правила валидации ответов от LLM.
"""

from typing import List, Tuple

from ...entities.llm_response import LLMResponse, ToolCall


class LLMResponseValidator:
    """
    Domain Service для валидации LLM ответов.
    
    Применяет бизнес-правила к ответам от LLM:
    - Валидация структуры ответа
    - Проверка tool calls
    - Валидация содержимого
    - Проверка использования токенов
    
    Examples:
        >>> validator = LLMResponseValidator()
        >>> response = LLMResponse(...)
        >>> is_valid, warnings = validator.validate_response(response)
        >>> if not is_valid:
        ...     print(f"Validation failed: {warnings}")
    """
    
    def validate_response(
        self,
        response: LLMResponse
    ) -> Tuple[bool, List[str]]:
        """
        Валидировать LLM ответ.
        
        Проверяет:
        - Наличие content или tool_calls
        - Корректность tool calls
        - Валидность finish_reason
        - Использование токенов
        
        Args:
            response: LLM ответ для валидации
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_warnings)
            
        Example:
            >>> validator = LLMResponseValidator()
            >>> response = LLMResponse(...)
            >>> is_valid, warnings = validator.validate_response(response)
        """
        warnings = []
        
        # Проверка 1: Должен быть либо content, либо tool_calls
        if not response.has_content() and not response.has_tool_calls():
            warnings.append("Response has neither content nor tool calls")
            return False, warnings
        
        # Проверка 2: Валидация tool calls если есть
        if response.has_tool_calls():
            tool_valid, tool_warnings = self.validate_tool_calls(response.tool_calls)
            if not tool_valid:
                warnings.extend(tool_warnings)
                return False, warnings
            warnings.extend(tool_warnings)
        
        # Проверка 3: Валидация finish_reason
        if response.finish_reason:
            reason_valid, reason_warning = self._validate_finish_reason(response)
            if not reason_valid:
                warnings.append(reason_warning)
        
        # Проверка 4: Проверка использования токенов
        token_valid, token_warning = self.check_token_usage(response)
        if not token_valid:
            warnings.append(token_warning)
        
        # Ответ валиден если нет критических ошибок
        return True, warnings
    
    def validate_tool_calls(
        self,
        tool_calls: List[ToolCall]
    ) -> Tuple[bool, List[str]]:
        """
        Валидировать список tool calls.
        
        Args:
            tool_calls: Список вызовов инструментов
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_warnings)
            
        Example:
            >>> validator = LLMResponseValidator()
            >>> tool_calls = [ToolCall(...)]
            >>> is_valid, warnings = validator.validate_tool_calls(tool_calls)
        """
        warnings = []
        
        if not tool_calls:
            return True, warnings
        
        # Бизнес-правило: Только один tool call за раз
        if len(tool_calls) > 1:
            warnings.append(
                f"Multiple tool calls detected ({len(tool_calls)}). "
                f"Only the first one should be executed."
            )
        
        # Валидация каждого tool call
        for i, tool_call in enumerate(tool_calls):
            valid, error = self._validate_single_tool_call(tool_call)
            if not valid:
                warnings.append(f"Tool call {i}: {error}")
                return False, warnings
        
        return True, warnings
    
    def _validate_single_tool_call(
        self,
        tool_call: ToolCall
    ) -> Tuple[bool, str]:
        """
        Валидировать отдельный tool call.
        
        Args:
            tool_call: Вызов инструмента
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        # Проверка ID
        if not tool_call.id:
            return False, "Tool call ID is required"
        
        # Проверка имени инструмента
        if not tool_call.tool_name:
            return False, "Tool name is required"
        
        # Проверка аргументов
        if not isinstance(tool_call.arguments, dict):
            return False, f"Tool arguments must be a dict, got {type(tool_call.arguments)}"
        
        return True, ""
    
    def validate_content(
        self,
        content: str
    ) -> Tuple[bool, str]:
        """
        Валидировать текстовое содержимое.
        
        Args:
            content: Текстовое содержимое для валидации
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
            
        Example:
            >>> validator = LLMResponseValidator()
            >>> is_valid, error = validator.validate_content("Hello")
            >>> is_valid
            True
        """
        # Проверка на пустоту
        if not content or not content.strip():
            return False, "Content is empty"
        
        # Проверка на разумную длину (не более 100KB)
        if len(content) > 100000:
            return False, f"Content too long: {len(content)} characters"
        
        return True, ""
    
    def check_token_usage(
        self,
        response: LLMResponse
    ) -> Tuple[bool, str]:
        """
        Проверить использование токенов.
        
        Args:
            response: LLM ответ
            
        Returns:
            Tuple[bool, str]: (is_valid, warning_message)
            
        Example:
            >>> validator = LLMResponseValidator()
            >>> response = LLMResponse(...)
            >>> is_valid, warning = validator.check_token_usage(response)
        """
        usage = response.usage
        
        # Проверка на нулевое использование
        if usage.total_tokens == 0:
            return True, "Warning: Zero tokens reported"
        
        # Проверка на аномально большое использование
        if usage.total_tokens > 100000:
            return True, f"Warning: Very high token usage: {usage.total_tokens}"
        
        # Проверка соответствия суммы
        expected_total = usage.prompt_tokens + usage.completion_tokens
        if usage.total_tokens != expected_total:
            return True, (
                f"Warning: Token sum mismatch. "
                f"Expected {expected_total}, got {usage.total_tokens}"
            )
        
        return True, ""
    
    def _validate_finish_reason(
        self,
        response: LLMResponse
    ) -> Tuple[bool, str]:
        """
        Валидировать finish_reason.
        
        Args:
            response: LLM ответ
            
        Returns:
            Tuple[bool, str]: (is_valid, warning_message)
        """
        reason = response.finish_reason
        
        # Известные причины
        valid_reasons = ["stop", "length", "tool_calls", "content_filter", "error"]
        
        if reason not in valid_reasons:
            return True, f"Warning: Unknown finish_reason '{reason}'"
        
        # Проверка соответствия finish_reason и содержимого
        if reason == "tool_calls" and not response.has_tool_calls():
            return False, "finish_reason is 'tool_calls' but no tool calls present"
        
        if reason == "length" and response.has_tool_calls():
            return True, "Warning: finish_reason is 'length' but tool calls present"
        
        return True, ""
