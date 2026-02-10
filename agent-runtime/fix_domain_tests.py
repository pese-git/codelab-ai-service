#!/usr/bin/env python3
"""
Скрипт для автоматического исправления Domain тестов.

Исправляет:
1. Позиционные аргументы Value Objects на именованные
2. Обновляет вызовы конструкторов для Pydantic V2
"""

import re
from pathlib import Path
from typing import List, Tuple


# Паттерны для замены Value Objects
VALUE_OBJECT_PATTERNS = [
    # ApprovalStatus с Enum
    (r'ApprovalStatus\(ApprovalStatusEnum\.(\w+)\)', r'ApprovalStatus(value=ApprovalStatusEnum.\1)'),
    
    # ApprovalType с Enum
    (r'ApprovalType\(ApprovalTypeEnum\.(\w+)\)', r'ApprovalType(value=ApprovalTypeEnum.\1)'),
    
    # PolicyAction с Enum
    (r'PolicyAction\(PolicyActionEnum\.(\w+)\)', r'PolicyAction(value=PolicyActionEnum.\1)'),
    
    # SubtaskStatus с Enum
    (r'SubtaskStatus\(SubtaskStatusEnum\.(\w+)\)', r'SubtaskStatus(value=SubtaskStatusEnum.\1)'),
    
    # PlanStatus с Enum
    (r'PlanStatus\(PlanStatusEnum\.(\w+)\)', r'PlanStatus(value=PlanStatusEnum.\1)'),
    
    # AgentType с Enum
    (r'AgentType\(AgentTypeEnum\.(\w+)\)', r'AgentType(value=AgentTypeEnum.\1)'),
    
    # ApprovalId
    (r'ApprovalId\("([^"]+)"\)', r'ApprovalId(value="\1")'),
    (r"ApprovalId\('([^']+)'\)", r"ApprovalId(value='\1')"),
    
    # ApprovalStatus
    (r'ApprovalStatus\("([^"]+)"\)', r'ApprovalStatus(value="\1")'),
    (r"ApprovalStatus\('([^']+)'\)", r"ApprovalStatus(value='\1')"),
    
    # ApprovalType
    (r'ApprovalType\("([^"]+)"\)', r'ApprovalType(value="\1")'),
    (r"ApprovalType\('([^']+)'\)", r"ApprovalType(value='\1')"),
    
    # PolicyAction
    (r'PolicyAction\("([^"]+)"\)', r'PolicyAction(value="\1")'),
    (r"PolicyAction\('([^']+)'\)", r"PolicyAction(value='\1')"),
    
    # PlanId
    (r'PlanId\("([^"]+)"\)', r'PlanId(value="\1")'),
    (r"PlanId\('([^']+)'\)", r"PlanId(value='\1')"),
    
    # SubtaskId
    (r'SubtaskId\("([^"]+)"\)', r'SubtaskId(value="\1")'),
    (r"SubtaskId\('([^']+)'\)", r"SubtaskId(value='\1')"),
    
    # AgentId
    (r'AgentId\("([^"]+)"\)', r'AgentId(value="\1")'),
    (r"AgentId\('([^']+)'\)", r"AgentId(value='\1')"),
    
    # AgentType
    (r'AgentType\("([^"]+)"\)', r'AgentType(value="\1")'),
    (r"AgentType\('([^']+)'\)", r"AgentType(value='\1')"),
    
    # SessionId
    (r'SessionId\("([^"]+)"\)', r'SessionId(value="\1")'),
    (r"SessionId\('([^']+)'\)", r"SessionId(value='\1')"),
]


def fix_file(file_path: Path) -> Tuple[bool, int]:
    """
    Исправить один файл.
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        Tuple[bool, int]: (был ли изменен файл, количество замен)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        total_replacements = 0
        
        # Применить все паттерны
        for pattern, replacement in VALUE_OBJECT_PATTERNS:
            content, count = re.subn(pattern, replacement, content)
            total_replacements += count
        
        # Сохранить только если были изменения
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True, total_replacements
        
        return False, 0
        
    except Exception as e:
        print(f"❌ Ошибка при обработке {file_path}: {e}")
        return False, 0


def process_directory(directory: Path) -> None:
    """
    Обработать все тестовые файлы в директории.
    
    Args:
        directory: Путь к директории с тестами
    """
    test_files = list(directory.rglob("test_*.py"))
    
    print(f"🔍 Найдено {len(test_files)} тестовых файлов")
    print()
    
    modified_files = 0
    total_replacements = 0
    
    for file_path in test_files:
        was_modified, replacements = fix_file(file_path)
        
        if was_modified:
            modified_files += 1
            total_replacements += replacements
            relative_path = file_path.relative_to(directory.parent.parent)
            print(f"✅ {relative_path}: {replacements} замен")
    
    print()
    print("=" * 60)
    print(f"📊 Итого:")
    print(f"   - Обработано файлов: {len(test_files)}")
    print(f"   - Изменено файлов: {modified_files}")
    print(f"   - Всего замен: {total_replacements}")
    print("=" * 60)


def main():
    """Главная функция."""
    print("=" * 60)
    print("🔧 Исправление Domain тестов")
    print("=" * 60)
    print()
    
    # Определить путь к тестам
    script_dir = Path(__file__).parent
    tests_dir = script_dir / "tests" / "unit" / "domain"
    
    if not tests_dir.exists():
        print(f"❌ Директория не найдена: {tests_dir}")
        return
    
    # Обработать все тесты
    process_directory(tests_dir)
    
    print()
    print("✅ Готово!")
    print()
    print("📝 Следующие шаги:")
    print("   1. Запустить тесты: pytest tests/unit/domain/ -v")
    print("   2. Проверить результаты")
    print("   3. Исправить оставшиеся ошибки вручную")


if __name__ == "__main__":
    main()
