#!/usr/bin/env python3
"""
Скрипт для исправления Execution Context - добавление валидации для ID Value Objects.
"""

from pathlib import Path

# Добавить валидацию для PlanId
plan_id_validation = '''
    @field_validator('value')
    @classmethod
    def validate_value(cls, v: str) -> str:
        """Валидация значения PlanId."""
        if not v or not v.strip():
            raise ValueError("PlanId value cannot be empty")
        return v
'''

# Добавить валидацию для SubtaskId  
subtask_id_validation = '''
    @field_validator('value')
    @classmethod
    def validate_value(cls, v: str) -> str:
        """Валидация значения SubtaskId."""
        if not v or not v.strip():
            raise ValueError("SubtaskId value cannot be empty")
        return v
'''

def add_validation_to_plan_id():
    """Добавить валидацию в PlanId."""
    file_path = Path(__file__).parent / "app/domain/execution_context/value_objects/plan_id.py"
    content = file_path.read_text(encoding='utf-8')
    
    # Добавить импорт field_validator если его нет
    if 'from pydantic import field_validator' not in content:
        content = content.replace(
            'from app.domain.shared.value_object import ValueObject',
            'from pydantic import field_validator\nfrom app.domain.shared.value_object import ValueObject'
        )
    
    # Добавить валидатор после объявления value: str
    if '@field_validator' not in content and 'value: str' in content:
        content = content.replace(
            '    value: str\n    \n    def __str__',
            f'    value: str\n{plan_id_validation}\n    def __str__'
        )
        file_path.write_text(content, encoding='utf-8')
        print("✅ PlanId: добавлена валидация")
        return True
    else:
        print("⏭️  PlanId: валидация уже существует или структура файла изменилась")
        return False

def add_validation_to_subtask_id():
    """Добавить валидацию в SubtaskId."""
    file_path = Path(__file__).parent / "app/domain/execution_context/value_objects/subtask_id.py"
    content = file_path.read_text(encoding='utf-8')
    
    # Добавить импорт field_validator если его нет
    if 'from pydantic import field_validator' not in content:
        content = content.replace(
            'from app.domain.shared.value_object import ValueObject',
            'from pydantic import field_validator\nfrom app.domain.shared.value_object import ValueObject'
        )
    
    # Добавить валидатор после объявления value: str
    if '@field_validator' not in content and 'value: str' in content:
        content = content.replace(
            '    value: str\n    \n    def __str__',
            f'    value: str\n{subtask_id_validation}\n    def __str__'
        )
        file_path.write_text(content, encoding='utf-8')
        print("✅ SubtaskId: добавлена валидация")
        return True
    else:
        print("⏭️  SubtaskId: валидация уже существует или структура файла изменилась")
        return False

def main():
    """Главная функция."""
    print("🔧 Исправление Execution Context - добавление валидации")
    print("=" * 70)
    
    changes = 0
    
    if add_validation_to_plan_id():
        changes += 1
    
    if add_validation_to_subtask_id():
        changes += 1
    
    print("\n" + "=" * 70)
    print(f"✅ Внесено изменений: {changes}")
    print("\n🎯 Следующий шаг: запустить тесты Execution Context")

if __name__ == "__main__":
    main()
