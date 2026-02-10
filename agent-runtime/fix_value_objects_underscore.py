#!/usr/bin/env python3
"""
Скрипт для замены self._value на self.value в Value Objects.
"""

import re
from pathlib import Path


def fix_value_attribute(content: str) -> tuple[str, int]:
    """
    Заменить self._value на self.value.
    Также заменить other._value на other.value.
    Также заменить target._value на target.value.
    """
    changes = 0
    
    # Замена self._value на self.value
    new_content, count = re.subn(r'\bself\._value\b', 'self.value', content)
    changes += count
    
    # Замена other._value на other.value
    new_content, count = re.subn(r'\bother\._value\b', 'other.value', new_content)
    changes += count
    
    # Замена target._value на target.value
    new_content, count = re.subn(r'\btarget\._value\b', 'target.value', new_content)
    changes += count
    
    return new_content, changes


def process_file(file_path: Path) -> tuple[bool, int]:
    """Обработать один файл."""
    try:
        content = file_path.read_text(encoding='utf-8')
        new_content, changes = fix_value_attribute(content)
        
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
    domain_dir = Path("app/domain")
    
    if not domain_dir.exists():
        print("❌ Директория app/domain не найдена")
        return
    
    print("🔍 Поиск Value Objects...")
    
    # Ищем все файлы value_objects
    vo_files = list(domain_dir.rglob("value_objects/*.py"))
    print(f"📁 Найдено {len(vo_files)} файлов\n")
    
    total_files_changed = 0
    total_changes = 0
    
    for vo_file in vo_files:
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
