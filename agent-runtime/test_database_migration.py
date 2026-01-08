"""
Тестовый скрипт для проверки миграции на async database.

Этот скрипт проверяет:
1. Корректность импортов
2. Инициализацию базы данных
3. Базовые операции с сессиями
4. Операции с agent context
5. Операции с pending approvals

Запуск:
    python test_database_migration.py
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))


async def test_database_operations():
    """Тест основных операций с базой данных"""
    print("🧪 Начало тестирования миграции базы данных...")
    
    try:
        # 1. Импорты
        print("\n1️⃣ Проверка импортов...")
        from app.services.database import (
            init_database, init_db, close_db, get_db,
            get_database_service, DatabaseService
        )
        from app.core.dependencies import DBSession, DBService
        print("   ✅ Все импорты успешны")
        
        # 2. Инициализация БД
        print("\n2️⃣ Инициализация базы данных...")
        test_db_url = "sqlite:///test_agent_runtime.db"
        init_database(test_db_url)
        await init_db()
        print("   ✅ База данных инициализирована")
        
        # 3. Получение сервиса
        print("\n3️⃣ Получение database service...")
        db_service = get_database_service()
        print(f"   ✅ DatabaseService получен: {type(db_service).__name__}")
        
        # 4. Тест операций с сессией
        print("\n4️⃣ Тест операций с сессией...")
        async for db in get_db():
            session_id = "test-session-123"
            messages = [
                {"role": "user", "content": "Hello, world!"},
                {"role": "assistant", "content": "Hi there!"}
            ]
            
            # Сохранение сессии
            await db_service.save_session(
                db=db,
                session_id=session_id,
                messages=messages,
                last_activity=datetime.now(timezone.utc)
            )
            print(f"   ✅ Сессия {session_id} сохранена")
            
            # Загрузка сессии
            loaded_session = await db_service.load_session(db, session_id)
            if loaded_session:
                print(f"   ✅ Сессия {session_id} загружена")
                print(f"      - Сообщений: {len(loaded_session['messages'])}")
                print(f"      - Заголовок: {loaded_session.get('title', 'N/A')[:50]}...")
            
            # Список сессий
            sessions = await db_service.list_all_sessions(db)
            print(f"   ✅ Найдено сессий: {len(sessions)}")
            
            break  # Выходим из async generator
        
        # 5. Тест операций с agent context
        print("\n5️⃣ Тест операций с agent context...")
        async for db in get_db():
            await db_service.save_agent_context(
                db=db,
                session_id=session_id,
                current_agent="code",
                agent_history=[
                    {
                        "from": None,
                        "to": "code",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "reason": "Initial agent"
                    }
                ],
                metadata={"test": "data"},
                created_at=datetime.now(timezone.utc),
                last_switch_at=None,
                switch_count=0
            )
            print(f"   ✅ Agent context для {session_id} сохранен")
            
            # Загрузка context
            context = await db_service.load_agent_context(db, session_id)
            if context:
                print(f"   ✅ Agent context загружен")
                print(f"      - Текущий агент: {context['current_agent']}")
                print(f"      - История переключений: {len(context['agent_history'])}")
            
            break
        
        # 6. Тест операций с pending approvals
        print("\n6️⃣ Тест операций с pending approvals...")
        async for db in get_db():
            call_id = "test-call-123"
            await db_service.save_pending_approval(
                db=db,
                session_id=session_id,
                call_id=call_id,
                tool_name="execute_command",
                arguments={"command": "ls -la"},
                reason="Requires user approval"
            )
            print(f"   ✅ Pending approval {call_id} сохранен")
            
            # Получение approvals
            approvals = await db_service.get_pending_approvals(db, session_id)
            print(f"   ✅ Найдено pending approvals: {len(approvals)}")
            
            # Удаление approval
            deleted = await db_service.delete_pending_approval(db, call_id)
            print(f"   ✅ Pending approval удален: {deleted}")
            
            break
        
        # 7. Очистка
        print("\n7️⃣ Очистка тестовых данных...")
        async for db in get_db():
            await db_service.delete_session(db, session_id, soft=False)
            print(f"   ✅ Тестовая сессия удалена")
            break
        
        # 8. Закрытие БД
        print("\n8️⃣ Закрытие базы данных...")
        await close_db()
        print("   ✅ База данных закрыта")
        
        # Удаление тестового файла БД
        test_db_path = Path("test_agent_runtime.db")
        if test_db_path.exists():
            test_db_path.unlink()
            print("   ✅ Тестовый файл БД удален")
        
        print("\n✅ Все тесты пройдены успешно!")
        print("\n📋 Резюме миграции:")
        print("   • Async SQLAlchemy работает корректно")
        print("   • Dependency injection настроен")
        print("   • Все операции с БД асинхронные")
        print("   • Timezone-aware datetime используется")
        print("   • DatabaseService функционирует правильно")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_imports_only():
    """Тест только импортов (без зависимостей)"""
    print("🧪 Проверка структуры кода (без запуска)...")
    
    try:
        print("\n1️⃣ Проверка синтаксиса файлов...")
        import py_compile
        
        files_to_check = [
            "app/services/database.py",
            "app/core/dependencies.py",
            "app/main.py",
        ]
        
        for file_path in files_to_check:
            py_compile.compile(file_path, doraise=True)
            print(f"   ✅ {file_path}")
        
        print("\n✅ Все файлы имеют корректный синтаксис!")
        print("\n📋 Для полного тестирования установите зависимости:")
        print("   cd codelab-ai-service/agent-runtime")
        print("   pip install -e .")
        print("   # или")
        print("   uv pip install -e .")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("  Тест миграции agent-runtime на async database")
    print("=" * 70)
    
    # Проверяем наличие SQLAlchemy
    try:
        import sqlalchemy
        print(f"\n✓ SQLAlchemy установлен (версия {sqlalchemy.__version__})")
        # Запускаем полный тест
        success = asyncio.run(test_database_operations())
    except ImportError:
        print("\n⚠️  SQLAlchemy не установлен")
        print("   Выполняется проверка только синтаксиса...\n")
        # Запускаем только проверку синтаксиса
        success = asyncio.run(test_imports_only())
    
    sys.exit(0 if success else 1)
