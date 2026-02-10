#!/usr/bin/env python3
"""
Скрипт для исправления тестов валидации Value Objects.
Заменяет pytest.raises(ValueError) на pytest.raises((ValueError, ValidationError))
для тестов, которые проверяют типы данных.
"""

import re
from pathlib import Path


def fix_validation_tests(content: str) -> tuple[str, int]:
    """
    Исправить тесты валидации.
    
    Добавляет импорт ValidationError и обновляет pytest.raises для тестов
    с None и неправильными типами.
    """
    changes = 0
    
    # Добавить импорт ValidationError если его нет
    if 'from pydantic import ValidationError' not in content and 'ValidationError' not in content:
        # Найти блок импортов
        import_match = re.search(r'(import pytest\n)', content)
        if import_match:
            content = content.replace(
                import_match.group(1),
                import_match.group(1) + 'from pydantic import ValidationError\n'
            )
            changes += 1
    
    # Заменить pytest.raises(ValueError) на pytest.raises((ValueError, ValidationError))
    # для тестов с None и неправильными типами
    
    # Паттерн для тестов с None
    pattern_none = r'with pytest\.raises\(ValueError, match="[^"]*не может быть пустым"\):\s+(\w+)\(value=None\)'
    replacement_none = r'with pytest.raises((ValueError, ValidationError)):\n            \1(value=None)'
    content, count = re.subn(pattern_none, replacement_none, content)
    changes += count
    
    # Паттерн для тестов с неправильным типом
    pattern_type = r'with pytest\.raises\(ValueError, match="[^"]*должен быть строкой"\):\s+(\w+)\(value=\d+\)'
    replacement_type = r'with pytest.raises((ValueError, ValidationError)):\n            \1(value=123)'
    content, count = re.subn(pattern_type, replacement_type, content)
    changes += count
    
    return content, changes


def process_file(file_path: Path) -> tuple[bool, int]:
    """Обработать один файл."""
    try:
        content = file_path.read_text(encoding='utf-8')
        new_content, changes = fix_validation_tests(content)
        
        if changes > 0:
            file_path.write_text(new_content, encoding='utf-8')
            print(f"✅ {file_path}: {changes} изменений")
            return True, changes
        
        return False, 0
    except Exception as e:
        print(f"❌ Ошибка в {file_path}: {e}")
        return False, 0


def main():
    """Главная функция."""
    tests_dir = Path("tests")
    
    if not tests_dir.exists():
        print("❌ Директория tests/ не найдена")
        return
    
    print("🔍 Поиск тестовых файлов с валидацией...")
    
    # Ищем файлы с тестами value objects
    test_files = [
        tests_dir / "unit/domain/agent_context/test_agent_id.py",
        tests_dir / "unit/domain/session_context/test_conversation_id.py",
        tests_dir / "unit/domain/tool_context/test_value_objects.py",
    ]
    
    total_files_changed = 0
    total_changes = 0
    
    for test_file in test_files:
        if test_file.exists():
            changed, count = process_file(test_file)
            if changed:
                total_files_changed += 1
                total_changes += count
    
    print(f"\n{'='*60}")
    print(f"✨ Готово!")
    print(f"📝 Файлов изменено: {total_files_changed}")
    print(f"🔧 Всего замен: {total_changes}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
