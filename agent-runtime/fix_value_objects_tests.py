#!/usr/bin/env python3
"""
Скрипт для исправления вызовов Value Objects в тестах.
Заменяет позиционные аргументы на именованные параметры.
"""

import re
import sys
from pathlib import Path


def fix_value_object_calls(content: str) -> tuple[str, int]:
    """
    Исправить вызовы Value Objects.
    
    Заменяет:
    - AgentId(x) -> AgentId(value=x)
    - SubtaskId(x) -> SubtaskId(value=x)
    - PlanId(x) -> PlanId(value=x)
    - ConversationId(x) -> ConversationId(value=x)
    - ToolName(x) -> ToolName(value=x)
    
    Но НЕ заменяет, если уже есть value=
    """
    changes = 0
    
    # Паттерны для замены
    patterns = [
        (r'AgentId\((?!value=)([^)]+)\)', r'AgentId(value=\1)'),
        (r'SubtaskId\((?!value=)([^)]+)\)', r'SubtaskId(value=\1)'),
        (r'PlanId\((?!value=)([^)]+)\)', r'PlanId(value=\1)'),
        (r'ConversationId\((?!value=)([^)]+)\)', r'ConversationId(value=\1)'),
        (r'ToolName\((?!value=)([^)]+)\)', r'ToolName(value=\1)'),
    ]
    
    result = content
    for pattern, replacement in patterns:
        new_result, count = re.subn(pattern, replacement, result)
        changes += count
        result = new_result
    
    return result, changes


def process_file(file_path: Path) -> tuple[bool, int]:
    """Обработать один файл."""
    try:
        content = file_path.read_text(encoding='utf-8')
        new_content, changes = fix_value_object_calls(content)
        
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
        sys.exit(1)
    
    print("🔍 Поиск Python файлов в tests/...")
    py_files = list(tests_dir.rglob("*.py"))
    print(f"📁 Найдено {len(py_files)} файлов\n")
    
    total_files_changed = 0
    total_changes = 0
    
    for py_file in py_files:
        changed, count = process_file(py_file)
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
