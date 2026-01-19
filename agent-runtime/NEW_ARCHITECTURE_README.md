# Новая архитектура Agent Runtime - Руководство

**Версия:** 1.0  
**Дата:** 18 января 2026

---

## 📚 Обзор

Agent Runtime был отрефакторен с использованием современных архитектурных паттернов:
- **Clean Architecture** - четкое разделение слоев
- **Domain-Driven Design** - богатая доменная модель
- **CQRS** - разделение команд и запросов
- **Event-Driven** - слабая связанность через события
- **Resilience Patterns** - защитные механизмы

---

## 🏗️ Структура проекта

```
app/
├── domain/                    # Бизнес-логика (независима от инфраструктуры)
│   ├── entities/             # Доменные сущности
│   │   ├── message.py        # Сообщение
│   │   ├── session.py        # Сессия диалога
│   │   └── agent_context.py  # Контекст агента
│   ├── events/               # Доменные события
│   │   ├── session_events.py # События сессий
│   │   └── agent_events.py   # События агентов
│   ├── repositories/         # Интерфейсы репозиториев
│   │   ├── session_repository.py
│   │   └── agent_context_repository.py
│   └── services/             # Доменные сервисы
│       ├── session_management.py
│       └── agent_orchestration.py
│
├── application/              # Сценарии использования (Use Cases)
│   ├── commands/            # Команды (изменение состояния)
│   │   ├── create_session.py
│   │   ├── add_message.py
│   │   └── switch_agent.py
│   ├── queries/             # Запросы (чтение данных)
│   │   ├── get_session.py
│   │   ├── list_sessions.py
│   │   └── get_agent_context.py
│   └── dto/                 # Data Transfer Objects
│       ├── session_dto.py
│       ├── message_dto.py
│       └── agent_context_dto.py
│
├── infrastructure/           # Технические детали
│   ├── persistence/         # База данных
│   │   ├── models/          # SQLAlchemy модели
│   │   ├── mappers/         # Entity ↔ Model преобразования
│   │   └── repositories/    # Реализации репозиториев
│   ├── concurrency/         # Управление конкурентностью
│   │   └── session_lock.py  # Session-level locks
│   ├── resilience/          # Защитные механизмы
│   │   ├── circuit_breaker.py
│   │   └── retry_handler.py
│   ├── cleanup/             # Автоматическая очистка
│   │   └── session_cleanup.py
│   └── adapters/            # Адаптеры интеграции
│       └── event_publisher_adapter.py
│
├── api/                     # Presentation Layer
│   └── v1/
│       ├── routers/         # API роутеры
│       │   ├── health_router.py
│       │   ├── sessions_router.py
│       │   ├── messages_router.py
│       │   └── agents_router.py
│       └── schemas/         # API схемы
│           ├── session_schemas.py
│           ├── message_schemas.py
│           └── agent_schemas.py
│
└── core/                    # Общие компоненты
    ├── errors/              # Система исключений
    ├── config.py            # Конфигурация
    └── dependencies_new.py  # Dependency Injection
```

---

## 🚀 Быстрый старт

### 1. Создание сессии

```python
from app.application.commands import CreateSessionCommand, CreateSessionHandler
from app.core.dependencies_new import get_session_management_service

# Получить сервис через DI
service = await get_session_management_service()

# Создать handler
handler = CreateSessionHandler(service)

# Создать команду
command = CreateSessionCommand(session_id="session-123")

# Выполнить
session_dto = await handler.handle(command)

print(f"Created session: {session_dto.id}")
```

### 2. Добавление сообщения

```python
from app.application.commands import AddMessageCommand, AddMessageHandler

# Создать команду
command = AddMessageCommand(
    session_id="session-123",
    role="user",
    content="Создай новый файл"
)

# Выполнить
message_dto = await handler.handle(command)

print(f"Added message: {message_dto.id}")
```

### 3. Получение сессии

```python
from app.application.queries import GetSessionQuery, GetSessionHandler

# Создать запрос
query = GetSessionQuery(
    session_id="session-123",
    include_messages=True
)

# Выполнить
session_dto = await handler.handle(query)

if session_dto:
    print(f"Session: {session_dto.title}")
    print(f"Messages: {session_dto.message_count}")
```

### 4. Переключение агента

```python
from app.application.commands import SwitchAgentCommand, SwitchAgentHandler

# Создать команду
command = SwitchAgentCommand(
    session_id="session-123",
    target_agent="coder",
    reason="User requested code changes"
)

# Выполнить
context_dto = await handler.handle(command)

print(f"Switched to: {context_dto.current_agent}")
```

---

## 🔧 Использование защитных механизмов

### Session Locks (предотвращение race conditions)

```python
from app.infrastructure.concurrency import session_lock_manager

async def process_message_safely(session_id: str, message: str):
    async with session_lock_manager.lock(session_id):
        # Только один запрос может выполнять этот код одновременно
        # для данной сессии
        context = await get_context(session_id)
        context.switch_to(...)
        await save_context(context)
```

### Rate Limiting

```python
# В main.py
from app.api.middleware import RateLimitMiddleware

app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=60  # 60 запросов в минуту per-client
)
```

### Circuit Breaker

```python
from app.infrastructure.resilience import CircuitBreaker

# Создать circuit breaker для LLM Proxy
llm_circuit = CircuitBreaker(
    failure_threshold=5,      # Открыть после 5 ошибок
    recovery_timeout=60       # Попытка восстановления через 60 секунд
)

# Использовать
async def call_llm_safely(*args, **kwargs):
    try:
        return await llm_circuit.call(call_llm_proxy, *args, **kwargs)
    except Exception as e:
        if "Circuit breaker is OPEN" in str(e):
            # Сервис недоступен, использовать fallback
            return fallback_response()
        raise
```

### Retry Handler

```python
from app.infrastructure.resilience.retry_handler import with_retry

# Декоратор для автоматических повторов
@with_retry(max_retries=3, base_delay=1.0)
async def save_to_database(data):
    # Будет автоматически повторено при ошибке
    # с задержками: 1s, 2s, 4s
    await db.save(data)
```

---

## 📊 Работа с репозиториями

### Прямое использование репозитория

```python
from app.infrastructure.persistence.repositories import SessionRepositoryImpl
from app.services.database import get_db

# Получить сессию БД
async for db in get_db():
    # Создать репозиторий
    repository = SessionRepositoryImpl(db)
    
    # Найти сессию
    session = await repository.find_by_id("session-123")
    
    if session:
        # Изменить сущность
        session.add_message(Message(...))
        
        # Сохранить
        await repository.save(session)
    
    break
```

### Через доменный сервис (рекомендуется)

```python
from app.domain.services import SessionManagementService

# Сервис инкапсулирует бизнес-логику
service = SessionManagementService(repository, event_publisher)

# Добавить сообщение (с валидацией и событиями)
message = await service.add_message(
    session_id="session-123",
    role="user",
    content="Привет!"
)
```

---

## 🎯 Dependency Injection

### Использование в роутерах

```python
from fastapi import APIRouter, Depends
from app.core.dependencies_new import get_create_session_handler

router = APIRouter()

@router.post("/sessions")
async def create_session(
    request: CreateSessionRequest,
    handler: CreateSessionHandler = Depends(get_create_session_handler)
):
    command = CreateSessionCommand(session_id=request.session_id)
    dto = await handler.handle(command)
    return dto
```

### Доступные провайдеры

**Repositories:**
- `get_session_repository()` - SessionRepositoryImpl
- `get_agent_context_repository()` - AgentContextRepositoryImpl

**Services:**
- `get_session_management_service()` - SessionManagementService
- `get_agent_orchestration_service()` - AgentOrchestrationService

**Command Handlers:**
- `get_create_session_handler()` - CreateSessionHandler
- `get_add_message_handler()` - AddMessageHandler
- `get_switch_agent_handler()` - SwitchAgentHandler

**Query Handlers:**
- `get_get_session_handler()` - GetSessionHandler
- `get_list_sessions_handler()` - ListSessionsHandler
- `get_get_agent_context_handler()` - GetAgentContextHandler

---

## 🔄 Публикация доменных событий

### В доменных сервисах

```python
from app.domain.events import SessionCreated

class SessionManagementService:
    def __init__(self, repository, event_publisher):
        self._repository = repository
        self._event_publisher = event_publisher
    
    async def create_session(self, session_id: str):
        session = Session(id=session_id)
        await self._repository.save(session)
        
        # Опубликовать доменное событие
        if self._event_publisher:
            await self._event_publisher(
                SessionCreated(
                    aggregate_id=session_id,
                    session_id=session_id
                )
            )
        
        return session
```

---

## 🧪 Тестирование

### Unit тесты (доменный слой)

```python
import pytest
from app.domain.entities import Session, Message

def test_add_message_to_session():
    session = Session(id="session-1")
    message = Message(id="msg-1", role="user", content="Hi")
    
    session.add_message(message)
    
    assert session.get_message_count() == 1
```

### Integration тесты (с БД)

```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # ... setup
    yield session

@pytest.mark.asyncio
async def test_repository_save(db_session):
    repository = SessionRepositoryImpl(db_session)
    session = Session(id="session-1")
    
    await repository.save(session)
    found = await repository.find_by_id("session-1")
    
    assert found is not None
```

---

## 📖 Примеры использования

### Пример 1: Создание и работа с сессией

```python
# 1. Создать сессию
command = CreateSessionCommand()
session_dto = await create_handler.handle(command)

# 2. Добавить сообщение пользователя
command = AddMessageCommand(
    session_id=session_dto.id,
    role="user",
    content="Создай новый Flutter виджет"
)
await add_message_handler.handle(command)

# 3. Переключить на Coder агента
command = SwitchAgentCommand(
    session_id=session_dto.id,
    target_agent="coder",
    reason="Coding task detected"
)
await switch_agent_handler.handle(command)

# 4. Получить историю
query = GetSessionQuery(
    session_id=session_dto.id,
    include_messages=True
)
session = await get_session_handler.handle(query)

print(f"Session has {len(session.messages)} messages")
```

### Пример 2: Работа с репозиториями

```python
# Получить активные сессии
sessions = await repository.find_active(limit=10)

# Найти сессии по диапазону времени
from datetime import datetime, timedelta

now = datetime.now(timezone.utc)
yesterday = now - timedelta(days=1)

recent_sessions = await repository.find_by_activity_range(
    start_time=yesterday,
    end_time=now
)

# Очистить старые сессии
count = await repository.cleanup_old(max_age_hours=24)
print(f"Cleaned {count} old sessions")
```

### Пример 3: Использование защитных механизмов

```python
# Session Lock
async with session_lock_manager.lock(session_id):
    # Безопасная работа с сессией
    pass

# Circuit Breaker
circuit = CircuitBreaker(failure_threshold=5)
result = await circuit.call(external_service_call, ...)

# Retry
@with_retry(max_retries=3)
async def critical_operation():
    # Будет повторено при ошибке
    pass
```

---

## 🔄 Миграция с старого кода

### Было (старый код):

```python
from app.services.session_manager_async import session_manager

session = await session_manager.get_or_create(session_id)
await session_manager.append_message(session_id, "user", "Hello")
```

### Стало (новый код):

```python
from app.application.commands import CreateSessionCommand, AddMessageCommand

# Создать сессию
command = CreateSessionCommand(session_id=session_id)
session_dto = await create_handler.handle(command)

# Добавить сообщение
command = AddMessageCommand(
    session_id=session_id,
    role="user",
    content="Hello"
)
await add_message_handler.handle(command)
```

---

## ⚠️ Важные замечания

### Обратная совместимость

**Существующий код продолжает работать!**

Новая архитектура создана параллельно со старой.
Протоколы общения не изменены:
- Gateway ↔ Agent Runtime ✅
- Agent Runtime ↔ LLM Proxy ✅

### Постепенная миграция

Рекомендуется мигрировать код постепенно:
1. Новые фичи - используйте новую архитектуру
2. Существующий код - оставьте как есть
3. При рефакторинге - переводите на новую архитектуру

---

## 📝 Best Practices

### 1. Используйте Command/Query handlers

**Хорошо:**
```python
command = CreateSessionCommand(...)
dto = await handler.handle(command)
```

**Плохо:**
```python
session = Session(...)
await repository.save(session)  # Пропускаем валидацию и события
```

### 2. Публикуйте доменные события

**Хорошо:**
```python
await event_publisher(SessionCreated(...))
```

**Плохо:**
```python
# Изменение без событий - подписчики не узнают
```

### 3. Используйте DTO для API

**Хорошо:**
```python
return SessionDTO.from_entity(session)
```

**Плохо:**
```python
return session  # Утечка доменной модели в API
```

### 4. Обрабатывайте ошибки правильно

**Хорошо:**
```python
try:
    await handler.handle(command)
except SessionNotFoundError as e:
    raise HTTPException(status_code=404, detail=e.message)
```

**Плохо:**
```python
await handler.handle(command)  # Необработанные исключения
```

---

## 🎓 Дополнительные ресурсы

### Документация по этапам:
- [Этап 1: Подготовка](REFACTORING_STAGE_1_COMPLETE.md)
- [Этап 2: Domain Layer](REFACTORING_STAGE_2_COMPLETE.md)
- [Этап 3: Application Layer](REFACTORING_STAGE_3_COMPLETE.md)
- [Этап 4: Infrastructure Layer](REFACTORING_STAGE_4_COMPLETE.md)
- [Этап 5: API Layer](REFACTORING_STAGE_5_COMPLETE.md)
- [Этап 6: Resilience](REFACTORING_STAGE_6_COMPLETE.md)

### Анализ и планирование:
- [Анализ архитектуры](../../AGENT_RUNTIME_ARCHITECTURE_ANALYSIS.md)
- [План рефакторинга](../../AGENT_RUNTIME_REFACTORING_PLAN.md)
- [Event-Driven интеграция](../../EVENT_DRIVEN_ARCHITECTURE_INTEGRATION.md)

---

**Автор:** AI Assistant  
**Дата:** 18 января 2026
