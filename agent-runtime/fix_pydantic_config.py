#!/usr/bin/env python3
"""
Скрипт для автоматической замены class Config на model_config = ConfigDict.
"""

import re
from pathlib import Path


def fix_pydantic_config(file_path: Path) -> bool:
    """
    Исправляет Pydantic Config в файле.
    
    Returns:
        True если файл был изменен
    """
    content = file_path.read_text()
    original_content = content
    
    # Проверяем, есть ли class Config
    if 'class Config:' not in content:
        return False
    
    # Добавляем импорт ConfigDict если его нет
    if 'from pydantic import' in content and 'ConfigDict' not in content:
        content = re.sub(
            r'from pydantic import ([^\n]+)',
            lambda m: f'from pydantic import {m.group(1).rstrip()}, ConfigDict' if 'ConfigDict' not in m.group(1) else m.group(0),
            content
        )
    
    # Заменяем class Config на model_config
    # Паттерн для поиска class Config блока
    config_pattern = r'(\s+)class Config:\s*\n(?:\s+"""[^"]*"""\s*\n)?(\s+)(.*?)(?=\n\s{0,4}\S|\n\s*$)'
    
    def replace_config(match):
        indent = match.group(1)
        config_indent = match.group(2)
        config_body = match.group(3)
        
        # Парсим настройки
        settings = []
        for line in config_body.split('\n'):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('"""'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                settings.append(f'{key}={value}')
            elif ':' in line:
                # json_encoders и подобные
                continue
        
        # Формируем новый код
        if settings:
            settings_str = ',\n        '.join(settings)
            return f'{indent}model_config = ConfigDict(\n        {settings_str}\n    )'
        else:
            return f'{indent}model_config = ConfigDict()'
    
    # Простая замена для стандартных случаев
    replacements = [
        # arbitrary_types_allowed = True
        (
            r'(\s+)class Config:\s*\n\s+"""[^"]*"""\s*\n\s+arbitrary_types_allowed = True',
            r'\1model_config = ConfigDict(\n\1    arbitrary_types_allowed=True,\n\1)'
        ),
        (
            r'(\s+)class Config:\s*\n\s+arbitrary_types_allowed = True',
            r'\1model_config = ConfigDict(\n\1    arbitrary_types_allowed=True,\n\1)'
        ),
        # json_encoders (удаляем, так как deprecated)
        (
            r'(\s+)class Config:\s*\n\s+"""[^"]*"""\s*\n\s+arbitrary_types_allowed = True\s*\n\s+json_encoders = \{[^}]+\}',
            r'\1model_config = ConfigDict(\n\1    arbitrary_types_allowed=True,\n\1)'
        ),
        # Простой Config без параметров
        (
            r'(\s+)class Config:\s*\n\s+pass',
            r'\1model_config = ConfigDict()'
        ),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    if content != original_content:
        file_path.write_text(content)
        print(f"✅ Fixed: {file_path}")
        return True
    
    return False


def main():
    """Главная функция."""
    app_dir = Path('app')
    
    files_to_fix = [
        'api/v1/schemas/session_schemas.py',
        'api/v1/schemas/common.py',
        'application/queries/base.py',
        'application/commands/base.py',
        'events/base_event.py',
        'domain/events/base.py',
        'domain/entities/hitl.py',
        'domain/entities/approval.py',
        'domain/entities/base.py',
    ]
    
    fixed_count = 0
    for file_path in files_to_fix:
        full_path = app_dir / file_path
        if full_path.exists():
            if fix_pydantic_config(full_path):
                fixed_count += 1
        else:
            print(f"⚠️  Not found: {full_path}")
    
    print(f"\n✨ Fixed {fixed_count} files")


if __name__ == '__main__':
    main()
