#!/usr/bin/env python3
"""
Скрипт для рефакторинга Value Objects на Pydantic поля.
Удаляет __init__ и @property, заменяя их на объявление поля.
"""

import re
from pathlib import Path


def refactor_value_object(content: str, value_type: str) -> tuple[str, int]:
    """
    Рефакторинг Value Object на Pydantic стиль.
    
    Удаляет:
    - def __init__(self, value: Type): ... self.value = value
    - @property def value(self) -> Type: return self.value
    
    Добавляет:
    - value: Type
    """
    changes = 0
    
    # Паттерн для поиска __init__ с присваиванием self.value
    init_pattern = r'    def __init__\(self, value: ' + value_type + r'\):.*?self\.value = value\s+'
    
    # Проверяем, есть ли __init__
    if re.search(init_pattern, content, re.DOTALL):
        # Удаляем __init__
        content = re.sub(init_pattern, '', content, flags=re.DOTALL)
        changes += 1
    
    # Удаляем @property для value
    property_pattern = r'    @property\s+def value\(self\) -> ' + value_type + r':.*?return self\.value\s+'
    if re.search(property_pattern, content, re.DOTALL):
        content = re.sub(property_pattern, '', content, flags=re.DOTALL)
        changes += 1
    
    # Добавляем объявление поля после docstring класса, если его еще нет
    if changes > 0 and f'value: {value_type}' not in content:
        # Находим конец docstring класса
        class_pattern = r'(class \w+\(ValueObject\):.*?""")\s+'
        match = re.search(class_pattern, content, re.DOTALL)
        if match:
            insert_pos = match.end()
            content = content[:insert_pos] + f'\n    value: {value_type}\n    ' + content[insert_pos:]
            changes += 1
    
    return content, changes


def process_file(file_path: Path) -> tuple[bool, int]:
    """Обработать один файл."""
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Определяем тип value из имени файла или содержимого
        if 'StatusEnum' in content:
            if 'PlanStatusEnum' in content:
                value_type = 'PlanStatusEnum'
            elif 'SubtaskStatusEnum' in content:
                value_type = 'SubtaskStatusEnum'
            elif 'ApprovalStatusEnum' in content:
                value_type = 'ApprovalStatusEnum'
            else:
                return False, 0
        elif 'TypeEnum' in content:
            value_type = 'ApprovalTypeEnum'
        elif 'ActionEnum' in content:
            value_type = 'PolicyActionEnum'
        elif 'str' in content and 'def __init__(self, value: str)' in content:
            value_type = 'str'
        else:
            return False, 0
        
        new_content, changes = refactor_value_object(content, value_type)
        
        if changes > 0:
            file_path.write_text(new_content, encoding='utf-8')
            print(f"✅ {file_path.name}: {changes} изменений (type: {value_type})")
            return True, changes
        
        return False, 0
    except Exception as e:
        print(f"❌ Ошибка в {file_path}: {e}")
        return False, 0


def main():
    """Главная функция."""
    domain_dir = Path("app/domain")
    
    if not domain_dir.exists():
        print("❌ Директория app/domain не найдена")
        return
    
    print("🔍 Поиск Value Objects с __init__...")
    
    # Ищем все файлы value_objects
    vo_files = list(domain_dir.rglob("value_objects/*.py"))
    
    # Фильтруем только те, что имеют __init__
    files_with_init = []
    for vo_file in vo_files:
        content = vo_file.read_text(encoding='utf-8')
        if 'def __init__(self, value:' in content:
            files_with_init.append(vo_file)
    
    print(f"📁 Найдено {len(files_with_init)} файлов с __init__\n")
    
    total_files_changed = 0
    total_changes = 0
    
    for vo_file in files_with_init:
        changed, count = process_file(vo_file)
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
