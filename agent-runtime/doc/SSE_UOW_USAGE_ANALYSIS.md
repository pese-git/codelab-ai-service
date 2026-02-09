# Анализ использования SSEUnitOfWork

**Дата**: 2026-02-08  
**Статус**: ⚠️ UoW создан, но НЕ используется

## Проблема

`SSEUnitOfWork` создается в API handlers, но **нигде не используется**:

```python
# messages_router.py:136
async with SSEUnitOfWork(existing_session=db) as uow:
    # ↓ uow создан, но не используется!
    async for chunk in process_message_use_case.execute(use_case_request):
        yield f"data: {chunk_json}\n\n"
```

## Где делаются commit'ы (12 мест)

### 1. Domain Services (4 места)

#### [`MessageProcessor:119`](../app/domain/services/message_processor.py:119)
```python
await self._db.commit()  # ❌ Должно быть: await uow.commit("create_session")
```

#### [`MessageProcessor:143`](../app/domain/services/message_processor.py:143)
```python
await self._db.commit()  # ❌ Должно быть: await uow.commit("create_agent")
```

#### [`ApprovalManager:485`](../app/domain/services/approval_management.py:485)
```python
await db.commit()  # ❌ Должно быть: await uow.commit("save_approval")
```

#### [`ApprovalManager:501`](../app/domain/services/approval_management.py:501)
```python
await db.commit()  # ❌ Должно быть: await uow.commit("update_approval")
```

### 2. Application Handlers (2 места)

#### [`StreamLLMResponseHandler:335`](../app/application/handlers/stream_llm_response_handler.py:335)
```python
await self._db.commit()  # ❌ Должно быть: await uow.commit("save_messages")
```

#### [`StreamLLMResponseHandler:401`](../app/application/handlers/stream_llm_response_handler.py:401)
```python
await self._db.commit()  # ❌ Должно быть: await uow.commit("save_assistant_message")
```

### 3. Infrastructure (6 мест)

#### [`database.py:250, 319, 428`](../app/infrastructure/persistence/database.py)
```python
await db.commit()  # ❌ Utility functions
```

#### [`database.py:531, 587`](../app/infrastructure/persistence/database.py)
```python
await db.commit()  # ❌ Approval operations
```

## Почему UoW не работает

### Текущая архитектура

```
API Handler (messages_router.py)
  ├─ async with SSEUnitOfWork(existing_session=db) as uow:  # ← UoW создан
  │   └─ process_message_use_case.execute()  # ← uow НЕ передан
  │       └─ MessageProcessor.process()  # ← uow НЕ известен
  │           ├─ await self._db.commit()  # ← Прямой commit
  │           └─ StreamLLMResponseHandler.handle_stream()
  │               └─ await self._db.commit()  # ← Прямой commit
```

### Проблемы

1. **UoW не передается в use cases**
   ```python
   # Текущий код
   async for chunk in process_message_use_case.execute(request):
       yield chunk
   
   # Нужно
   async for chunk in process_message_use_case.execute(request, uow=uow):
       yield chunk
   ```

2. **Use cases не знают о UoW**
   ```python
   # ProcessMessageUseCase
   def __init__(self, message_processor, lock_manager):
       # ↑ Нет параметра uow
   ```

3. **Domain services используют db напрямую**
   ```python
   # MessageProcessor
   def __init__(self, ..., db: AsyncSession):
       self._db = db  # ← Прямой доступ к db
   ```

## Правильная архитектура

### Вариант A: Передать UoW через use cases

```python
# API Handler
async with SSEUnitOfWork(existing_session=db) as uow:
    async for chunk in process_message_use_case.execute(request, uow=uow):
        yield chunk

# ProcessMessageUseCase
async def execute(self, request, uow: Optional[SSEUnitOfWork] = None):
    async with self._lock_manager.lock(request.session_id):
        async for chunk in self._message_processor.process(..., uow=uow):
            yield chunk

# MessageProcessor
async def process(self, ..., uow: Optional[SSEUnitOfWork] = None):
    # Создать session
    await self._session_service.get_or_create_conversation(session_id)
    if uow:
        await uow.commit(operation="create_session")
    else:
        await self._db.commit()
```

**Плюсы**:
- Явное управление транзакциями
- Метрики для каждой операции
- Обратная совместимость (uow опциональный)

**Минусы**:
- Нужно обновить все use cases и services
- Много изменений в коде

### Вариант B: UoW как контекстная переменная

```python
from contextvars import ContextVar

# unit_of_work.py
current_uow: ContextVar[Optional[SSEUnitOfWork]] = ContextVar('current_uow', default=None)

class SSEUnitOfWork:
    async def __aenter__(self):
        current_uow.set(self)
        return self
    
    async def __aexit__(self, ...):
        current_uow.set(None)
        ...

# MessageProcessor
async def process(self, ...):
    uow = current_uow.get()
    if uow:
        await uow.commit(operation="create_session")
    else:
        await self._db.commit()
```

**Плюсы**:
- Минимальные изменения в коде
- Автоматическое распространение UoW

**Минусы**:
- Неявная зависимость
- Сложнее тестировать

### Вариант C: Заменить db.commit() на uow.commit() (ТЕКУЩИЙ)

```python
# API Handler
async with SSEUnitOfWork(existing_session=db) as uow:
    # ← uow создан, но не используется
    async for chunk in process_message_use_case.execute(request):
        yield chunk
```

**Статус**: ❌ **НЕ РАБОТАЕТ**

**Проблема**: UoW создан, но никто его не использует. Все commit'ы идут через `db.commit()`.

## Почему сообщения не сохраняются

### Root Cause

**FastAPI закрывает сессию ДО начала работы генератора**:

```python
@router.post("/stream")
async def message_stream_sse(
    db: AsyncSession = Depends(get_db),  # ← Сессия создана
    ...
):
    async def generate():
        async with SSEUnitOfWork(existing_session=db) as uow:
            ...
    
    return StreamingResponse(generate())  # ← Endpoint завершен
    # FastAPI: await db.commit() + await db.close()  # ← ЗДЕСЬ!
    # Генератор начинает работу ПОСЛЕ закрытия сессии
```

### Порядок выполнения

```
1. FastAPI: db = Depends(get_db)  # Создана сессия
2. Endpoint: return StreamingResponse(generate())  # Завершен
3. FastAPI: await db.commit()  # ❌ COMMIT БЕЗ ДАННЫХ
4. FastAPI: await db.close()  # ❌ СЕССИЯ ЗАКРЫТА
5. Генератор: async with SSEUnitOfWork(existing_session=db):  # ❌ ЗАКРЫТАЯ СЕССИЯ
6. MessageProcessor: await self._db.commit()  # ❌ НА ЗАКРЫТОЙ СЕССИИ
```

## Решение

### Шаг 1: Создать сессию внутри генератора

```python
@router.post("/stream")
async def message_stream_sse(
    request: MessageStreamRequest,
    # ❌ Убрать db из параметров
    # db: AsyncSession = Depends(get_db),
):
    async def generate():
        # ✅ Создать сессию ВНУТРИ генератора
        from app.infrastructure.persistence.database import async_session_maker
        
        async with async_session_maker() as db:
            # Пересоздать use case с новой сессией
            container = get_container()
            use_case = container.get_process_message_use_case(db)
            
            async with SSEUnitOfWork(existing_session=db) as uow:
                try:
                    async for chunk in use_case.execute(request):
                        yield f"data: {chunk.model_dump_json()}\n\n"
                except Exception as e:
                    yield f"data: {error_chunk.model_dump_json()}\n\n"
            
            # ✅ Финальный commit
            await db.commit()
    
    return StreamingResponse(generate(), ...)
```

### Шаг 2: Передать UoW в use cases (опционально)

```python
# Если хотим использовать uow.commit() с метриками
async with SSEUnitOfWork(existing_session=db) as uow:
    async for chunk in use_case.execute(request, uow=uow):
        yield chunk
```

### Шаг 3: Обновить domain services (опционально)

```python
# MessageProcessor
async def process(self, ..., uow: Optional[SSEUnitOfWork] = None):
    if uow:
        await uow.commit(operation="create_session")
    else:
        await self._db.commit()
```

## Приоритеты

### 🔴 Критично (СЕЙЧАС)

1. **Создать сессию внутри генератора** - исправит проблему с сохранением
2. **Убрать `db` из параметров endpoint** - предотвратит раннее закрытие

### 🟡 Важно (СЛЕДУЮЩАЯ НЕДЕЛЯ)

3. **Передать UoW в use cases** - для метрик и явного управления
4. **Заменить `db.commit()` на `uow.commit()`** - для сбора метрик

### 🟢 Желательно (ПОТОМ)

5. **Использовать ContextVar** - для автоматического распространения UoW
6. **Написать интеграционные тесты** - проверить работу UoW

## Вывод

**SSEUnitOfWork создан правильно, но:**
1. ❌ Не используется (никто не вызывает `uow.commit()`)
2. ❌ Не передается в use cases
3. ❌ Работает на закрытой сессии (из-за FastAPI DI)

**Решение**: Создавать сессию внутри генератора, а не через `Depends(get_db)`.

---

**Подготовлено**: CodeLab Team  
**Источник**: Code analysis + production logs
