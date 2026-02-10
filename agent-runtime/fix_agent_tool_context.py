#!/usr/bin/env python3
"""
Скрипт для исправления оставшихся 7 failed тестов в Agent Context и Tool Context.

Проблемы:
1. test_create_agent_generates_id_from_session - ID без префикса "agent-"
2. test_create_with_invalid_capabilities_raises_error - валидация capabilities
3. test_switch_history_is_immutable - immutability истории
4. test_metadata_property_returns_copy - metadata не копируется
5. test_create_with_invalid_agent_type_raises_error - валидация AgentType
6. test_repr_shows_class_and_value - отсутствует __repr__ в AgentId
7. test_repr (ToolName) - отсутствует __repr__ в ToolName

Решения:
1. Изменить генерацию ID с префиксом "agent-"
2. Добавить валидацию capabilities
3. Добавить property для switch_history с копированием
4. Добавить property для metadata с копированием
5. Добавить валидацию AgentType
6. Исправить __repr__ в AgentId
7. Исправить __repr__ в ToolName
"""

import sys
from pathlib import Path

def fix_agent_id_generation():
    """Исправить генерацию ID с префиксом agent-."""
    file_path = Path("app/domain/agent_context/value_objects/agent_id.py")
    content = file_path.read_text()
    
    # Изменить метод from_session_id для генерации ID с префиксом
    old_code = '''    @staticmethod
    def from_session_id(session_id: str) -> "AgentId":
        """
        Создать AgentId из session ID (генерирует новый UUID).
        
        ВАЖНО: Теперь генерирует новый UUID вместо использования session_id,
        чтобы соответствовать ограничению БД VARCHAR(36).
        
        Args:
            session_id: ID сессии (используется только для валидации)
            
        Returns:
            AgentId с новым UUID
            
        Пример:
            >>> agent_id = AgentId.from_session_id("session-123")
            >>> len(agent_id.value)
            36
        """
        if not session_id:
            raise ValueError("Session ID не может быть пустым")
        
        # Генерируем новый UUID вместо использования session_id
        return AgentId.generate()'''
    
    new_code = '''    @staticmethod
    def from_session_id(session_id: str) -> "AgentId":
        """
        Создать AgentId из session ID (генерирует ID с префиксом agent-).
        
        Args:
            session_id: ID сессии (используется для валидации)
            
        Returns:
            AgentId с префиксом "agent-" и UUID
            
        Пример:
            >>> agent_id = AgentId.from_session_id("session-123")
            >>> agent_id.value.startswith("agent-")
            True
        """
        if not session_id:
            raise ValueError("Session ID не может быть пустым")
        
        # Генерируем ID с префиксом "agent-"
        unique_id = f"agent-{uuid.uuid4()}"
        return AgentId(value=unique_id)'''
    
    content = content.replace(old_code, new_code)
    
    # Исправить __repr__
    old_repr = '''    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"AgentId('{self.value}')"'''
    
    new_repr = '''    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"AgentId(value='{self.value}')"'''
    
    content = content.replace(old_repr, new_repr)
    
    file_path.write_text(content)
    print("✅ Исправлен AgentId: генерация ID с префиксом и __repr__")


def fix_agent_immutability():
    """Добавить immutability для switch_history и metadata."""
    file_path = Path("app/domain/agent_context/entities/agent.py")
    content = file_path.read_text()
    
    # Добавить property для switch_history после определения поля
    old_field = '''    switch_history: List[AgentSwitchRecord] = Field(
        default_factory=list,
        description="История переключений"
    )'''
    
    new_field = '''    _switch_history: List[AgentSwitchRecord] = Field(
        default_factory=list,
        description="История переключений",
        alias="switch_history"
    )'''
    
    content = content.replace(old_field, new_field)
    
    # Добавить property для metadata
    old_metadata = '''    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные"
    )'''
    
    new_metadata = '''    _metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные",
        alias="metadata"
    )'''
    
    content = content.replace(old_metadata, new_metadata)
    
    # Добавить properties после валидаторов
    properties_code = '''    
    @property
    def switch_history(self) -> List[AgentSwitchRecord]:
        """Получить копию истории переключений (immutable)."""
        return self._switch_history.copy()
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Получить копию метаданных (immutable)."""
        return self._metadata.copy()
'''
    
    # Вставить после валидаторов, перед @property current_type
    insert_pos = content.find('    @property\n    def current_type(self) -> AgentType:')
    if insert_pos != -1:
        content = content[:insert_pos] + properties_code + content[insert_pos:]
    
    # Обновить использование полей в методах
    content = content.replace('self.switch_history.append(record)', 'self._switch_history.append(record)')
    content = content.replace('self.switch_history[-1]', 'self._switch_history[-1]')
    content = content.replace('self.switch_history else None', 'self._switch_history else None')
    content = content.replace('[record.to_dict() for record in self.switch_history]', '[record.to_dict() for record in self._switch_history]')
    content = content.replace('self.metadata[key] = value', 'self._metadata[key] = value')
    content = content.replace('return self.metadata.get(key, default)', 'return self._metadata.get(key, default)')
    
    file_path.write_text(content)
    print("✅ Добавлена immutability для switch_history и metadata в Agent")


def fix_agent_capabilities_validation():
    """Добавить валидацию AgentType в AgentCapabilities."""
    file_path = Path("app/domain/agent_context/value_objects/agent_capabilities.py")
    content = file_path.read_text()
    
    # Найти класс AgentCapabilities и добавить валидатор
    validator_code = '''    
    @field_validator('agent_type')
    @classmethod
    def validate_agent_type(cls, v: Any) -> AgentType:
        """Валидация agent_type."""
        if not isinstance(v, AgentType):
            raise ValueError(f"agent_type должен быть AgentType, получен {type(v).__name__}")
        return v
'''
    
    # Вставить после импортов и перед первым методом
    insert_marker = '    agent_type: AgentType = Field('
    insert_pos = content.find(insert_marker)
    if insert_pos != -1:
        # Найти конец определения полей (перед первым @staticmethod или @field_validator)
        next_decorator = content.find('\n    @', insert_pos + len(insert_marker))
        if next_decorator != -1:
            content = content[:next_decorator] + validator_code + content[next_decorator:]
    
    file_path.write_text(content)
    print("✅ Добавлена валидация AgentType в AgentCapabilities")


def fix_tool_name_repr():
    """Исправить __repr__ в ToolName."""
    file_path = Path("app/domain/tool_context/value_objects/tool_name.py")
    content = file_path.read_text()
    
    old_repr = '''    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"ToolName('{self.value}')"'''
    
    new_repr = '''    def __repr__(self) -> str:
        """Отладочное представление."""
        return f"ToolName(value='{self.value}')"'''
    
    content = content.replace(old_repr, new_repr)
    
    file_path.write_text(content)
    print("✅ Исправлен __repr__ в ToolName")


def main():
    """Главная функция."""
    print("🔧 Исправление Agent Context и Tool Context...")
    print()
    
    try:
        # 1. Исправить AgentId (генерация и __repr__)
        fix_agent_id_generation()
        
        # 2. Добавить immutability в Agent
        fix_agent_immutability()
        
        # 3. Добавить валидацию в AgentCapabilities
        fix_agent_capabilities_validation()
        
        # 4. Исправить ToolName __repr__
        fix_tool_name_repr()
        
        print()
        print("✅ Все исправления применены!")
        print()
        print("Запустите тесты:")
        print("  uv run pytest tests/unit/domain/agent_context/ -v")
        print("  uv run pytest tests/unit/domain/tool_context/test_value_objects.py::TestToolName::test_repr -v")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
