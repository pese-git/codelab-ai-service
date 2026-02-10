#!/usr/bin/env python3
"""
Скрипт для исправления Approval Context - замена позиционных аргументов на именованные.
"""

import re
from pathlib import Path

def fix_approval_status_calls(content: str) -> tuple[str, int]:
    """Исправить вызовы ApprovalStatus с позиционными аргументами."""
    count = 0
    
    # ApprovalStatus(ApprovalStatusEnum.XXX) -> ApprovalStatus(value=ApprovalStatusEnum.XXX)
    pattern = r'ApprovalStatus\((ApprovalStatusEnum\.[A-Z_]+)\)'
    
    def replace_func(match):
        nonlocal count
        enum_value = match.group(1)
        count += 1
        return f'ApprovalStatus(value={enum_value})'
    
    content = re.sub(pattern, replace_func, content)
    return content, count

def fix_approval_type_calls(content: str) -> tuple[str, int]:
    """Исправить вызовы ApprovalType с позиционными аргументами."""
    count = 0
    
    # ApprovalType(ApprovalTypeEnum.XXX) -> ApprovalType(value=ApprovalTypeEnum.XXX)
    pattern = r'ApprovalType\((ApprovalTypeEnum\.[A-Z_]+)\)'
    
    def replace_func(match):
        nonlocal count
        enum_value = match.group(1)
        count += 1
        return f'ApprovalType(value={enum_value})'
    
    content = re.sub(pattern, replace_func, content)
    return content, count

def fix_policy_action_calls(content: str) -> tuple[str, int]:
    """Исправить вызовы PolicyAction с позиционными аргументами."""
    count = 0
    
    # PolicyAction(PolicyActionEnum.XXX) -> PolicyAction(value=PolicyActionEnum.XXX)
    pattern = r'PolicyAction\((PolicyActionEnum\.[A-Z_]+)\)'
    
    def replace_func(match):
        nonlocal count
        enum_value = match.group(1)
        count += 1
        return f'PolicyAction(value={enum_value})'
    
    content = re.sub(pattern, replace_func, content)
    return content, count

def fix_approval_id_calls(content: str) -> tuple[str, int]:
    """Исправить вызовы ApprovalId с позиционными аргументами."""
    count = 0
    
    # ApprovalId(value) -> ApprovalId(value=value)
    # Но пропускаем ApprovalId.generate()
    pattern = r'ApprovalId\((["\'][^"\']+["\']|[a-zA-Z_][a-zA-Z0-9_\.]*)\)(?!\s*\.)'
    
    def replace_func(match):
        nonlocal count
        var_name = match.group(1)
        # Пропускаем если уже именованный аргумент
        if '=' in var_name:
            return match.group(0)
        count += 1
        return f'ApprovalId(value={var_name})'
    
    content = re.sub(pattern, replace_func, content)
    return content, count

def process_file(file_path: Path) -> int:
    """Обработать один файл."""
    print(f"\n📄 Обработка: {file_path}")
    
    content = file_path.read_text(encoding='utf-8')
    original_content = content
    total_replacements = 0
    
    # Применить все исправления
    content, count = fix_approval_status_calls(content)
    if count > 0:
        print(f"  ✓ ApprovalStatus: {count} замен")
        total_replacements += count
    
    content, count = fix_approval_type_calls(content)
    if count > 0:
        print(f"  ✓ ApprovalType: {count} замен")
        total_replacements += count
    
    content, count = fix_policy_action_calls(content)
    if count > 0:
        print(f"  ✓ PolicyAction: {count} замен")
        total_replacements += count
    
    content, count = fix_approval_id_calls(content)
    if count > 0:
        print(f"  ✓ ApprovalId: {count} замен")
        total_replacements += count
    
    # Сохранить если были изменения
    if content != original_content:
        file_path.write_text(content, encoding='utf-8')
        print(f"  💾 Сохранено: {total_replacements} замен")
    else:
        print(f"  ⏭️  Изменений не требуется")
    
    return total_replacements

def main():
    """Главная функция."""
    print("🔧 Исправление Approval Context - замена позиционных аргументов")
    print("=" * 70)
    
    base_path = Path(__file__).parent
    
    # Файлы для обработки
    files_to_process = [
        # Entities
        base_path / "app/domain/approval_context/entities/approval_request.py",
        base_path / "app/domain/approval_context/entities/hitl_policy.py",
        
        # Services
        base_path / "app/domain/approval_context/services/approval_service.py",
        
        # Tests
        base_path / "tests/unit/domain/approval_context/test_entities.py",
        base_path / "tests/unit/domain/approval_context/test_value_objects.py",
    ]
    
    total_replacements = 0
    processed_files = 0
    
    for file_path in files_to_process:
        if file_path.exists():
            replacements = process_file(file_path)
            total_replacements += replacements
            processed_files += 1
        else:
            print(f"\n⚠️  Файл не найден: {file_path}")
    
    print("\n" + "=" * 70)
    print(f"✅ Обработано файлов: {processed_files}")
    print(f"✅ Всего замен: {total_replacements}")
    print("\n🎯 Следующий шаг: запустить тесты Approval Context")

if __name__ == "__main__":
    main()
