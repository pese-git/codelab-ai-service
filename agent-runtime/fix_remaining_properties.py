#!/usr/bin/env python3
"""
Скрипт для удаления оставшихся @property декораторов из Value Objects.
Исправляет синтаксические ошибки после миграции на Pydantic V2.
"""

import re
from pathlib import Path

# Файлы для исправления
FILES_TO_FIX = [
    "app/domain/execution_context/value_objects/plan_id.py",
    "app/domain/execution_context/value_objects/subtask_id.py",
    "app/domain/execution_context/value_objects/subtask_status.py",
    "app/domain/approval_context/value_objects/approval_type.py",
    "app/domain/approval_context/value_objects/policy_action.py",
    "app/domain/approval_context/value_objects/approval_id.py",
    "app/domain/approval_context/value_objects/approval_status.py",
]


def fix_property_decorator(content: str) -> tuple[str, int]:
    """
    Удаляет строки с @property декоратором.
    
    Returns:
        Tuple из (исправленный контент, количество замен)
    """
    lines = content.split('\n')
    fixed_lines = []
    removed_count = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Проверяем, является ли строка @property декоратором
        if line.strip() == '@property':
            # Пропускаем эту строку
            removed_count += 1
            i += 1
            continue
        
        fixed_lines.append(line)
        i += 1
    
    return '\n'.join(fixed_lines), removed_count


def main():
    """Основная функция."""
    total_files = 0
    total_removals = 0
    
    print("🔧 Удаление оставшихся @property декораторов из Value Objects\n")
    
    for file_path in FILES_TO_FIX:
        path = Path(file_path)
        
        if not path.exists():
            print(f"⚠️  Файл не найден: {file_path}")
            continue
        
        # Читаем файл
        content = path.read_text(encoding='utf-8')
        
        # Исправляем
        fixed_content, removals = fix_property_decorator(content)
        
        if removals > 0:
            # Записываем обратно
            path.write_text(fixed_content, encoding='utf-8')
            print(f"✅ {file_path}")
            print(f"   Удалено @property: {removals}")
            total_files += 1
            total_removals += removals
        else:
            print(f"⏭️  {file_path} - изменений не требуется")
    
    print(f"\n📊 Итого:")
    print(f"   Файлов обработано: {total_files}")
    print(f"   Удалено @property: {total_removals}")


if __name__ == "__main__":
    main()
