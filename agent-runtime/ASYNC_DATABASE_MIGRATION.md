# Миграция на асинхронную работу с базой данных

## Обзор изменений

Модуль работы с базой данных в `agent-runtime` был переработан для использования асинхронного подхода, аналогичного `auth-service`. Это обеспечивает лучшую производительность, масштабируемость и согласованность архитектуры между сервисами.

## Ключевые улучшения

### 1. Асинхронный SQLAlchemy
- **Было**: Синхронный `create_engine` и `sessionmaker`
- **Стало**: Асинхронный `create_async_engine` и `async_sessionmaker`
- **Преимущества**: 
  - Неблокирующие операции с БД
  - Лучшая производительность при высокой нагрузке
  - Совместимость с async/await паттерном FastAPI

### 2. Поддержка timezone-aware datetime
- **Было**: `DateTime` без timezone
- **Стало**: `DateTime(timezone=True)`
- **Преимущества**: Корректная работа с временными зонами, предотвращение проблем с UTC

### 3. Автоматическая конвертация URL для async драйверов
```python
# SQLite: sqlite:/// -> sqlite+aiosqlite:///
# PostgreSQL: postgresql:// -> postgresql+asyncpg://
```

### 4. Оптимизация SQLite для конкурентного доступа
```python
PRAGMA journal_mode=WAL      # Write-Ahead Logging
PRAGMA synchronous=NORMAL    # Баланс производительности/надежности
PRAGMA cache_size=-64000     # 64MB кэш
PRAGMA temp_store=MEMORY     # Временные данные в памяти
PRAGMA busy_timeout=30000    # 30 секунд таймаут
```

### 5. Dependency Injection паттерн
- Создан модуль [`app/core/dependencies.py`](app/core/dependencies.py)
- Типизированные зависимости: `DBSession`, `DBService`
- Упрощенное использование в эндпоинтах

### 6. Lifecycle management
- Инициализация БД при старте приложения
- Корректное закрытие соединений при остановке
- Использование `lifespan` context manager в FastAPI

## Структура изменений

### Измененные файлы

1. **`app/services/database.py`** (полная переработка)
   - Асинхронные методы для всех операций
   - `DatabaseService` класс с async методами
   - Функции `init_database()`, `init_db()`, `close_db()`
   - Dependency injection функции

2. **`app/main.py`**
   - Добавлен `lifespan` context manager
   - Инициализация БД при старте
   - Закрытие соединений при остановке

3. **`pyproject.toml`**
   - Добавлены зависимости: `aiosqlite>=0.19.0`, `asyncpg>=0.29.0`

4. **`app/core/dependencies.py`** (новый файл)
   - Типизированные зависимости для FastAPI

## Миграция существующего кода

### Старый синхронный подход

```python
from app.services.database import Database

db = Database()
with db.session_scope() as session:
    session_data = db.load_session(session_id)
```

### Новый асинхронный подход

```python
from app.core.dependencies import DBSession, DBService

async def my_endpoint(
    db: DBSession,
    db_service: DBService
):
    session_data = await db_service.load_session(db, session_id)
```

### Пример использования в эндпоинте

```python
from fastapi import APIRouter, Depends
from app.core.dependencies import DBSession, DBService

router = APIRouter()

@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: DBSession,
    db_service: DBService
):
    """Получить данные сессии"""
    session_data = await db_service.load_session(db, session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_data

@router.post("/sessions/{session_id}")
async def save_session(
    session_id: str,
    messages: List[Dict[str, Any]],
    db: DBSession,
    db_service: DBService
):
    """Сохранить данные сессии"""
    await db_service.save_session(
        db=db,
        session_id=session_id,
        messages=messages,
        last_activity=datetime.now(timezone.utc)
    )
    return {"status": "saved"}
```

## Изменения в API методов

Все методы `DatabaseService` теперь асинхронные:

| Метод | Сигнатура |
|-------|-----------|
| `save_session` | `async def save_session(db: AsyncSession, ...)` |
| `load_session` | `async def load_session(db: AsyncSession, ...)` |
| `delete_session` | `async def delete_session(db: AsyncSession, ...)` |
| `list_all_sessions` | `async def list_all_sessions(db: AsyncSession, ...)` |
| `save_agent_context` | `async def save_agent_context(db: AsyncSession, ...)` |
| `load_agent_context` | `async def load_agent_context(db: AsyncSession, ...)` |
| `save_pending_approval` | `async def save_pending_approval(db: AsyncSession, ...)` |
| `get_pending_approvals` | `async def get_pending_approvals(db: AsyncSession, ...)` |
| `delete_pending_approval` | `async def delete_pending_approval(db: AsyncSession, ...)` |

## Конфигурация базы данных

### SQLite (по умолчанию)
```bash
AGENT_RUNTIME__DB_URL=sqlite:///data/agent_runtime.db
```

### PostgreSQL
```bash
AGENT_RUNTIME__DB_URL=postgresql://user:password@localhost:5432/agent_runtime
```

## Установка зависимостей

```bash
# Для SQLite (async)
pip install aiosqlite

# Для PostgreSQL (async)
pip install asyncpg

# Или через uv
uv pip install aiosqlite asyncpg
```

## Тестирование

После миграции необходимо:

1. Установить новые зависимости
2. Обновить все вызовы методов БД на async
3. Добавить `await` перед всеми операциями с БД
4. Использовать `DBSession` и `DBService` через dependency injection
5. Протестировать все эндпоинты, работающие с БД

## Обратная совместимость

⚠️ **Внимание**: Эти изменения **не обратно совместимы** с синхронным кодом.

Все места, где используется база данных, должны быть обновлены для использования async/await.

## Преимущества новой архитектуры

1. **Производительность**: Неблокирующие операции с БД
2. **Масштабируемость**: Лучшая обработка конкурентных запросов
3. **Согласованность**: Единый подход с `auth-service`
4. **Типобезопасность**: Использование `Annotated` типов для DI
5. **Поддержка timezone**: Корректная работа с временными зонами
6. **Оптимизация SQLite**: WAL mode для лучшей конкурентности

## Дополнительные ресурсы

- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [aiosqlite Documentation](https://aiosqlite.omnilib.dev/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
