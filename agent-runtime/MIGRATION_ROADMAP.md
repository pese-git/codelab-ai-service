# Roadmap миграции на async database

## Статус миграции

### ✅ Завершено

1. **Базовая инфраструктура**
   - ✅ Переработан [`app/services/database.py`](app/services/database.py) на async SQLAlchemy
   - ✅ Добавлены async драйверы: `aiosqlite`, `asyncpg`
   - ✅ Создан [`app/core/dependencies.py`](app/core/dependencies.py) с DI паттерном
   - ✅ Обновлен [`app/main.py`](app/main.py) с lifecycle management
   - ✅ Timezone-aware datetime для всех моделей

2. **API эндпоинты**
   - ✅ [`/sessions`](app/api/v1/endpoints.py#L458) - список сессий (async)
   - ✅ [`/sessions` POST](app/api/v1/endpoints.py#L512) - создание сессии (async)

3. **Документация**
   - ✅ [ASYNC_DATABASE_MIGRATION.md](ASYNC_DATABASE_MIGRATION.md) - руководство по миграции
   - ✅ [DATABASE_ARCHITECTURE_COMPARISON.md](../DATABASE_ARCHITECTURE_COMPARISON.md) - сравнение подходов
   - ✅ [test_database_migration.py](test_database_migration.py) - тестовый скрипт

### 🔄 В процессе

4. **Сервисы с гибридным подходом**
   - 🔄 [`app/services/session_manager.py`](app/services/session_manager.py) - использует старый `Database`
   - 🔄 [`app/services/agent_context.py`](app/services/agent_context.py) - использует старый `Database`
   - 🔄 [`app/services/hitl_manager.py`](app/services/hitl_manager.py) - нужно проверить

### ⏳ Запланировано

5. **Полная миграция сервисов**
   - ⏳ Переработать `SessionManager` на async
   - ⏳ Переработать `AgentContextManager` на async
   - ⏳ Обновить `HITLManager` если использует БД
   - ⏳ Обновить все вызовы в эндпоинтах

6. **Тестирование**
   - ⏳ Unit тесты для async database operations
   - ⏳ Integration тесты для эндпоинтов
   - ⏳ Performance тесты (sync vs async)

## Стратегия миграции

### Фаза 1: Гибридный подход (ТЕКУЩАЯ)

**Цель**: Обеспечить работоспособность с минимальными изменениями

**Подход**:
- Новые эндпоинты используют async DB через DI
- Существующие сервисы продолжают работать с синхронным кодом
- Постепенная миграция по мере необходимости

**Преимущества**:
- ✅ Минимальный риск поломки существующего функционала
- ✅ Возможность тестировать async код параллельно
- ✅ Постепенное обучение команды async паттернам

**Недостатки**:
- ⚠️ Два способа работы с БД в кодовой базе
- ⚠️ Потенциальные проблемы с синхронизацией
- ⚠️ Технический долг

### Фаза 2: Полная миграция (ПЛАНИРУЕТСЯ)

**Цель**: Полностью перейти на async архитектуру

**План действий**:

#### 2.1. Переработка SessionManager

**Текущая архитектура**:
```python
class SessionManager:
    def __init__(self, db: Database):
        self._db = db  # Синхронный Database
        self._sessions: Dict[str, SessionState] = {}
        self._load_all_sessions()  # Синхронная загрузка
    
    def _persist_session(self, session_id: str):
        self._db.save_session(...)  # Синхронный вызов
```

**Целевая архитектура**:
```python
class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
    
    async def initialize(self, db_service: DatabaseService):
        """Async инициализация"""
        async for db in get_db():
            sessions = await db_service.list_all_sessions(db)
            for session_id in sessions:
                data = await db_service.load_session(db, session_id)
                # ...
            break
    
    async def _persist_session(self, session_id: str):
        """Async персистенция через background task"""
        # Использовать FastAPI background tasks или asyncio.create_task
```

**Изменения**:
1. Убрать синхронную инициализацию из `__init__`
2. Добавить async метод `initialize()`
3. Использовать background tasks для персистенции
4. Обновить все методы на async где нужно

#### 2.2. Переработка AgentContextManager

**Аналогично SessionManager**:
- Async инициализация
- Background tasks для персистенции
- Dependency injection для DatabaseService

#### 2.3. Обновление эндпоинтов

**Текущий код**:
```python
@router.post("/agent/message/stream")
async def message_stream_sse(request: AgentStreamRequest):
    session = session_manager.get_or_create(...)  # Синхронный
```

**Целевой код**:
```python
@router.post("/agent/message/stream")
async def message_stream_sse(
    request: AgentStreamRequest,
    db: DBSession,
    db_service: DBService
):
    session = await session_manager.get_or_create(
        db, db_service, ...
    )  # Async
```

### Фаза 3: Оптимизация (БУДУЩЕЕ)

**Цели**:
- Оптимизация запросов к БД
- Кэширование с Redis
- Connection pooling tuning
- Мониторинг производительности

## Технические детали

### Background Tasks для персистенции

**Проблема**: Частые синхронные вызовы БД блокируют event loop

**Решение**: Использовать background tasks

```python
from fastapi import BackgroundTasks

class SessionManager:
    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        background_tasks: BackgroundTasks,
        db_service: DatabaseService
    ):
        # Обновить in-memory state
        state = self.get(session_id)
        state.messages.append(...)
        
        # Запланировать персистенцию в фоне
        background_tasks.add_task(
            self._persist_session_async,
            session_id,
            db_service
        )
    
    async def _persist_session_async(
        self,
        session_id: str,
        db_service: DatabaseService
    ):
        async for db in get_db():
            await db_service.save_session(db, session_id, ...)
            break
```

### Batch операции

**Оптимизация**: Группировать операции записи

```python
class SessionManager:
    def __init__(self):
        self._pending_writes: Set[str] = set()
        self._write_lock = asyncio.Lock()
    
    async def _batch_persist(self, db_service: DatabaseService):
        """Периодическая пакетная запись"""
        while True:
            await asyncio.sleep(5)  # Каждые 5 секунд
            
            async with self._write_lock:
                if not self._pending_writes:
                    continue
                
                session_ids = list(self._pending_writes)
                self._pending_writes.clear()
            
            # Записать все сессии одной транзакцией
            async for db in get_db():
                for session_id in session_ids:
                    await db_service.save_session(db, session_id, ...)
                break
```

## Риски и митигация

### Риск 1: Потеря данных при миграции

**Митигация**:
- ✅ Создать backup БД перед миграцией
- ✅ Тестировать на копии production данных
- ✅ Использовать транзакции для атомарности

### Риск 2: Проблемы с производительностью

**Митигация**:
- ✅ Benchmark sync vs async
- ✅ Мониторинг метрик после деплоя
- ✅ Возможность rollback

### Риск 3: Сложность отладки async кода

**Митигация**:
- ✅ Подробное логирование
- ✅ Использование async-aware debugger
- ✅ Документация async паттернов

## Метрики успеха

### Производительность
- [ ] Latency эндпоинтов < 100ms (p95)
- [ ] Throughput > 100 req/s
- [ ] DB connection pool utilization < 80%

### Качество кода
- [ ] Test coverage > 80%
- [ ] Нет синхронных вызовов БД в async контексте
- [ ] Все эндпоинты используют DI

### Стабильность
- [ ] Нет data loss
- [ ] Нет deadlocks
- [ ] Graceful shutdown работает корректно

## Следующие шаги

1. **Немедленно**:
   - ✅ Завершить миграцию базовой инфраструктуры
   - ✅ Обновить документацию
   - ✅ Создать тестовый скрипт

2. **Краткосрочно (1-2 недели)**:
   - [ ] Переработать SessionManager на async
   - [ ] Переработать AgentContextManager на async
   - [ ] Обновить все эндпоинты

3. **Среднесрочно (1 месяц)**:
   - [ ] Полное покрытие тестами
   - [ ] Performance benchmarks
   - [ ] Production deployment

4. **Долгосрочно (3 месяца)**:
   - [ ] Оптимизация производительности
   - [ ] Redis кэширование
   - [ ] Мониторинг и алерты

## Ресурсы

### Документация
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [asyncio Best Practices](https://docs.python.org/3/library/asyncio-task.html)

### Примеры кода
- [auth-service](../auth-service/) - reference implementation
- [test_database_migration.py](test_database_migration.py) - тестовые примеры

### Инструменты
- `pytest-asyncio` - тестирование async кода
- `aiosqlite` - async SQLite драйвер
- `asyncpg` - async PostgreSQL драйвер
- `aiodebugger` - отладка async кода

## Заключение

Миграция на async database - это важный шаг к современной, масштабируемой архитектуре. Гибридный подход позволяет минимизировать риски и постепенно переходить на новую архитектуру.

Текущий статус: **Фаза 1 (Гибридный подход) - 60% завершено**

Следующий milestone: **Полная миграция SessionManager и AgentContextManager**
