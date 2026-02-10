#!/usr/bin/env python3
"""
Скрипт для исправления Session Context - замена позиционных аргументов на именованные.
"""

import re
from pathlib import Path

def fix_conversation_id_calls(content: str) -> tuple[str, int]:
    """Исправить вызовы ConversationId с позиционными аргументами."""
    count = 0
    
    # ConversationId(value) -> ConversationId(value=value)
    pattern = r'ConversationId\(([a-zA-Z_][a-zA-Z0-9_\.]*)\)'
    
    def replace_func(match):
        nonlocal count
        var_name = match.group(1)
        # Пропускаем если уже именованный аргумент
        if '=' in var_name:
            return match.group(0)
        count += 1
        return f'ConversationId(value={var_name})'
    
    content = re.sub(pattern, replace_func, content)
    return content, count

def fix_message_id_calls(content: str) -> tuple[str, int]:
    """Исправить вызовы MessageId с позиционными аргументами."""
    count = 0
    
    # MessageId(value) -> MessageId(value=value)
    pattern = r'MessageId\(([a-zA-Z_][a-zA-Z0-9_\.]*)\)'
    
    def replace_func(match):
        nonlocal count
        var_name = match.group(1)
        # Пропускаем если уже именованный аргумент
        if '=' in var_name:
            return match.group(0)
        count += 1
        return f'MessageId(value={var_name})'
    
    content = re.sub(pattern, replace_func, content)
    return content, count

def process_file(file_path: Path) -> int:
    """Обработать один файл."""
    print(f"\n📄 Обработка: {file_path}")
    
    content = file_path.read_text(encoding='utf-8')
    original_content = content
    total_replacements = 0
    
    # Применить все исправления
    content, count = fix_conversation_id_calls(content)
    if count > 0:
        print(f"  ✓ ConversationId: {count} замен")
        total_replacements += count
    
    content, count = fix_message_id_calls(content)
    if count > 0:
        print(f"  ✓ MessageId: {count} замен")
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
    print("🔧 Исправление Session Context - замена позиционных аргументов")
    print("=" * 70)
    
    base_path = Path(__file__).parent
    
    # Файлы для обработки
    files_to_process = [
        # Services
        base_path / "app/domain/session_context/services/conversation_management_service.py",
        
        # Tests
        base_path / "tests/unit/domain/session_context/services/test_conversation_management_service.py",
        base_path / "tests/unit/domain/session_context/test_conversation.py",
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
    print("\n🎯 Следующий шаг: запустить тесты Session Context")

if __name__ == "__main__":
    main()
