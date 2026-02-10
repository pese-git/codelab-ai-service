#!/usr/bin/env python3
"""
Скрипт для исправления factory методов в Value Objects.
Заменяет позиционные аргументы на именованные параметры для Pydantic V2.
"""

import re
from pathlib import Path

# Файлы для исправления
FILES_TO_FIX = [
    "app/domain/execution_context/value_objects/plan_status.py",
    "app/domain/execution_context/value_objects/subtask_status.py",
]


def fix_factory_methods(content: str) -> tuple[str, int]:
    """
    Заменяет cls(EnumValue) на cls(value=EnumValue) в factory методах.
    
    Returns:
        Tuple из (исправленный контент, количество замен)
    """
    # Паттерн для поиска: return cls(SomeEnum.VALUE)
    pattern = r'return cls\(([A-Z][a-zA-Z]+Enum\.[A-Z_]+)\)'
    replacement = r'return cls(value=\1)'
    
    fixed_content, count = re.subn(pattern, replacement, content)
    return fixed_content, count


def main():
    """Основная функция."""
    total_files = 0
    total_replacements = 0
    
    print("🔧 Исправление factory методов в Value Objects\n")
    
    for file_path in FILES_TO_FIX:
        path = Path(file_path)
        
        if not path.exists():
            print(f"⚠️  Файл не найден: {file_path}")
            continue
        
        # Читаем файл
        content = path.read_text(encoding='utf-8')
        
        # Исправляем
        fixed_content, replacements = fix_factory_methods(content)
        
        if replacements > 0:
            # Записываем обратно
            path.write_text(fixed_content, encoding='utf-8')
            print(f"✅ {file_path}")
            print(f"   Исправлено factory методов: {replacements}")
            total_files += 1
            total_replacements += replacements
        else:
            print(f"⏭️  {file_path} - изменений не требуется")
    
    print(f"\n📊 Итого:")
    print(f"   Файлов обработано: {total_files}")
    print(f"   Исправлено factory методов: {total_replacements}")


if __name__ == "__main__":
    main()
