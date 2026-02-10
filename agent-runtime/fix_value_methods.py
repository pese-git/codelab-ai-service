#!/usr/bin/env python3
"""
Скрипт для исправления методов value() в Value Objects.

Проблема:
После удаления @property декораторов остались методы value(),
которые вызывают сами себя, создавая бесконечную рекурсию.

Решение:
1. Удалить метод value() который вызывает self.value
2. Добавить поле value: str в начало класса
3. Исправить factory методы на использование именованных аргументов
"""

import re
from pathlib import Path


def fix_value_object_file(file_path: Path) -> bool:
    """Исправить один файл Value Object."""
    content = file_path.read_text(encoding='utf-8')
    original_content = content
    
    # Проверяем, есть ли проблемный метод value()
    if 'def value(self)' not in content:
        return False
    
    print(f"\n{'='*80}")
    print(f"Обработка: {file_path}")
    print(f"{'='*80}")
    
    changes_made = False
    
    # 1. Удаляем метод value() который вызывает self.value (рекурсия)
    pattern = r'\n    def value\(self\) -> str:\s*\n        """[^"]*"""\s*\n        return self\.value\s*\n'
    if re.search(pattern, content):
        content = re.sub(pattern, '\n', content)
        print("✓ Удален рекурсивный метод value()")
        changes_made = True
    
    # 2. Добавляем поле value: str после docstring класса, если его нет
    # Ищем класс и его docstring
    class_pattern = r'(class \w+\(ValueObject\):)\s*\n(\s*"""[\s\S]*?""")\s*\n'
    match = re.search(class_pattern, content)
    
    if match and 'value: str' not in content:
        class_def = match.group(1)
        docstring = match.group(2)
        
        # Вставляем поле value после docstring
        replacement = f"{class_def}\n{docstring}\n    value: str\n"
        content = content.replace(match.group(0), replacement)
        print("✓ Добавлено поле value: str")
        changes_made = True
    
    # 3. Исправляем factory методы - заменяем позиционные аргументы на именованные
    # Паттерн: return ClassName(value) -> return ClassName(value=value)
    class_name_match = re.search(r'class (\w+)\(ValueObject\):', content)
    if class_name_match:
        class_name = class_name_match.group(1)
        
        # Ищем return ClassName(что-то) где что-то не содержит =
        factory_pattern = rf'return {class_name}\(([^)=]+)\)'
        matches = list(re.finditer(factory_pattern, content))
        
        for match in reversed(matches):  # Обрабатываем с конца, чтобы не сбить позиции
            arg = match.group(1).strip()
            # Проверяем, что это не именованный аргумент
            if '=' not in arg:
                old_call = match.group(0)
                new_call = f'return {class_name}(value={arg})'
                content = content[:match.start()] + new_call + content[match.end():]
                print(f"✓ Исправлен factory метод: {old_call} -> {new_call}")
                changes_made = True
    
    if changes_made:
        file_path.write_text(content, encoding='utf-8')
        print(f"\n✅ Файл обновлен: {file_path}")
        return True
    else:
        print(f"\n⏭️  Изменения не требуются")
        return False


def main():
    """Основная функция."""
    print("🔧 Исправление методов value() в Value Objects")
    print("=" * 80)
    
    # Находим все файлы value objects
    base_path = Path("app/domain")
    value_object_files = []
    
    for context_dir in base_path.iterdir():
        if context_dir.is_dir() and context_dir.name.endswith('_context'):
            vo_dir = context_dir / "value_objects"
            if vo_dir.exists():
                value_object_files.extend(vo_dir.glob("*.py"))
    
    # Также проверяем shared
    shared_vo_dir = base_path / "shared"
    if shared_vo_dir.exists():
        value_object_files.extend(shared_vo_dir.glob("*_id.py"))
    
    print(f"\nНайдено файлов для проверки: {len(value_object_files)}")
    
    fixed_count = 0
    for file_path in sorted(value_object_files):
        if file_path.name == "__init__.py":
            continue
        
        if fix_value_object_file(file_path):
            fixed_count += 1
    
    print("\n" + "=" * 80)
    print(f"✅ Обработка завершена!")
    print(f"   Исправлено файлов: {fixed_count}")
    print(f"   Всего проверено: {len(value_object_files)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
