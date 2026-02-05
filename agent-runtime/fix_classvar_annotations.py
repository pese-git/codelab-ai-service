#!/usr/bin/env python3
"""
Скрипт для автоматического добавления ClassVar аннотаций к константам класса.

Исправляет ошибку Pydantic 2.x:
"A non-annotated attribute was detected"
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def find_value_object_files() -> List[Path]:
    """Найти все файлы Value Objects."""
    base_path = Path("app/domain")
    patterns = [
        "*/value_objects/*.py",
        "*/entities/*.py",
    ]
    
    files = []
    for pattern in patterns:
        files.extend(base_path.glob(pattern))
    
    return [f for f in files if f.name != "__init__.py"]


def needs_classvar_import(content: str) -> bool:
    """Проверить, нужен ли импорт ClassVar."""
    return "ClassVar" not in content and re.search(r'^\s+[A-Z_]+ = ', content, re.MULTILINE)


def add_classvar_import(content: str) -> str:
    """Добавить импорт ClassVar."""
    # Найти строку с импортом typing
    typing_import = re.search(r'^from typing import (.+)$', content, re.MULTILINE)
    
    if typing_import:
        imports = typing_import.group(1)
        if "ClassVar" not in imports:
            # Добавить ClassVar к существующим импортам
            new_imports = imports.rstrip() + ", ClassVar"
            content = content.replace(
                f"from typing import {imports}",
                f"from typing import {new_imports}"
            )
    else:
        # Добавить новый импорт после других импортов
        lines = content.split('\n')
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith('from ') or line.startswith('import '):
                insert_pos = i + 1
        
        lines.insert(insert_pos, "from typing import ClassVar")
        content = '\n'.join(lines)
    
    return content


def fix_constant_annotations(content: str) -> Tuple[str, int]:
    """Добавить ClassVar аннотации к константам класса."""
    changes = 0
    
    # Паттерны для поиска констант
    patterns = [
        # Простые константы: MAX_LENGTH = 100
        (r'^(\s+)([A-Z_]+) = (.+)$', r'\1\2: ClassVar = \3'),
        # Константы с типами: PATTERN = re.compile(...)
        (r'^(\s+)([A-Z_]+) = (re\.compile\(.+\))$', r'\1\2: ClassVar[re.Pattern] = \3'),
    ]
    
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        modified = False
        
        # Пропустить уже аннотированные
        if ': ClassVar' in line or ':ClassVar' in line:
            new_lines.append(line)
            continue
        
        # Пропустить строки вне классов
        if not line.startswith('    '):
            new_lines.append(line)
            continue
        
        # Применить паттерны
        for pattern, replacement in patterns:
            if re.match(pattern, line):
                new_line = re.sub(pattern, replacement, line)
                new_lines.append(new_line)
                changes += 1
                modified = True
                break
        
        if not modified:
            new_lines.append(line)
    
    return '\n'.join(new_lines), changes


def process_file(file_path: Path) -> Tuple[bool, int]:
    """Обработать один файл."""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        changes = 0
        
        # Добавить импорт ClassVar если нужно
        if needs_classvar_import(content):
            content = add_classvar_import(content)
        
        # Исправить аннотации
        content, file_changes = fix_constant_annotations(content)
        changes += file_changes
        
        # Сохранить если были изменения
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True, changes
        
        return False, 0
        
    except Exception as e:
        print(f"❌ Ошибка при обработке {file_path}: {e}")
        return False, 0


def main():
    """Главная функция."""
    print("🔍 Поиск файлов Value Objects...")
    files = find_value_object_files()
    print(f"📁 Найдено файлов: {len(files)}")
    
    total_changes = 0
    modified_files = 0
    
    for file_path in files:
        modified, changes = process_file(file_path)
        if modified:
            modified_files += 1
            total_changes += changes
            print(f"✅ {file_path.relative_to('app/domain')}: {changes} изменений")
    
    print(f"\n📊 Итого:")
    print(f"   Обработано файлов: {len(files)}")
    print(f"   Изменено файлов: {modified_files}")
    print(f"   Всего изменений: {total_changes}")
    
    return 0 if modified_files > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
