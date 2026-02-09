# Root Cause: Сообщения не сохраняются в БД

**Дата**: 2026-02-08  
**Статус**: 🔴 КРИТИЧЕСКАЯ ПРОБЛЕМА

## Проблема

**0 сообщений в таблице `messages`**, несмотря на логи о сохранении.

```sql
SELECT COUNT(*) FROM messages;
-- Результат: 0

SELECT COUNT(*) FROM sessions;
-- Результат: 1 (сессия создана!)
```

## Root Cause Analysis

### Порядок выполнения (НЕПРАВИЛЬНЫЙ)

```
1. FastAPI endpoint вызван
   ├─ db = Depends(get_db)  # Создана сессия
   │
2. async def generate():  # SSE-генератор создан
   │
3. return StreamingResponse(generate())  # Endpoint ЗАВЕРШЕН
   │
4. FastAPI: await db.commit()  # ❌ COMMIT ВЫПОЛНЕН РАНО!
   │
5. FastAPI: await db.close()  # ❌ СЕССИЯ ЗАКРЫТА!
   │
6. SSE-генератор начинает работу  # ❌ СЕССИЯ УЖЕ ЗАКРЫТА!
   ├─ async with SSEUnitOfWork(existing_session=db):
   │   ├─ process_message_use_case.execute()
   │   │   ├─ MessageProcessor.process()
   │   │   │   ├─ conversation_service.update_conversation()
   │   │   │   │   ├─ repository.save(conversation)
   │   │   │   │   │   ├─ mapper.to_model()
   │   │   │   │   │   │   ├─ DELETE FROM messages  # ❌ НА ЗАКРЫТОЙ СЕССИИ!
   │   │   │   │   │   │   └─ INSERT INTO messages  # ❌ НА ЗАКРЫТОЙ СЕССИИ!
   │   │   │   │   │   └─ await db.flush()  # ❌ ОШИБКА ИЛИ NOP
   │   │   │   │   └─ await db.commit()  # ❌ НА ЗАКРЫТОЙ СЕССИИ!
```

### Почему это происходит

#### 1. FastAPI Dependency Injection

FastAPI выполняет `get_db()` **ДО** вызова endpoint функции:

```python
@router.post("/stream")
async def message_stream_sse(
    db: AsyncSession = Depends(get_db),  # ← Выполняется ЗДЕСЬ
    ...
):
    async def generate():  # ← Генератор создан, но НЕ выполнен
        async with SSEUnitOfWork(existing_session=db):
            ...
    
    return StreamingResponse(generate())  # ← Endpoint завершен
    # FastAPI: await db.commit() + await db.close()  ← ЗДЕСЬ!
```

#### 2. StreamingResponse

`StreamingResponse` **НЕ ждет** завершения генератора:

```python
return StreamingResponse(generate())
# ↑ Возвращает response немедленно
# ↓ Генератор выполняется ПОСЛЕ
```

#### 3. get_db() Context Manager

```python
async def get_db():
    async with async_session_maker() as session:
        try:
            yield session  # ← Сессия передана в endpoint
            # Endpoint завершен, возвращаемся сюда
            await session.commit()  # ← COMMIT
        finally:
            await session.close()  # ← CLOSE
    # Генератор все еще работает, но сессия закрыта!
```

## Доказательства

### 1. Логи показывают правильный порядок операций

```
19:47:12.811 - SSEUnitOfWork initialized
19:47:12.834 - Adding message (role=user)
19:47:12.834 - Added 1 message models to session
19:47:12.837 - Saved conversation
19:47:19.022 - Adding message (role=assistant)
19:47:19.022 - Added 3 message models to session
19:47:19.023 - Saved conversation
19:47:19.028 - SSEUnitOfWork: Context exiting normally
19:47:19.030 - get_db(): Transaction committed successfully
```

Но в БД **0 сообщений**!

### 2. Сессия создана, сообщения нет

```sql
-- Сессия есть
SELECT * FROM sessions WHERE id = '94c2698b-c78d-4f38-873d-e4acc9a5fc1d';
-- ✅ 1 row

-- Сообщений нет
SELECT * FROM messages WHERE session_db_id = '94c2698b-c78d-4f38-873d-e4acc9a5fc1d';
-- ❌ 0 rows
```

### 3. Mapper удаляет ВСЕ сообщения перед добавлением

```python
# conversation_mapper.py:180-182
await db.execute(
    delete(MessageModel).where(MessageModel.session_db_id == model.id)
)
# ↑ Удаляет все старые сообщения
# ↓ Добавляет новые
for message in entity.messages.messages:
    db.add(msg_model)
```

Если commit не выполняется:
- Старые сообщения удалены
- Новые добавлены в сессию
- **Rollback** → новые потеряны, старые уже удалены
- **Результат**: 0 сообщений

## Решение

### Вариант 1: Передать сессию в генератор (БЫСТРО)

```python
@router.post("/stream")
async def message_stream_sse(
    request: MessageStreamRequest,
    process_message_use_case=Depends(get_process_message_use_case),
    ...
):
    async def generate():
        # Создать НОВУЮ сессию внутри генератора
        async with async_session_maker() as db:
            async with SSEUnitOfWork(existing_session=db) as uow:
                try:
                    async for chunk in process_message_use_case.execute(request):
                        yield f"data: {chunk.model_dump_json()}\n\n"
                except Exception as e:
                    yield f"data: {error_chunk.model_dump_json()}\n\n"
                finally:
                    # Commit перед закрытием
                    await db.commit()
    
    return StreamingResponse(generate(), ...)
```

### Вариант 2: Использовать contextlib.aclosing (ПРАВИЛЬНО)

```python
from contextlib import aclosing

@router.post("/stream")
async def message_stream_sse(
    request: MessageStreamRequest,
    db: AsyncSession = Depends(get_db),
    ...
):
    async def generate():
        async with SSEUnitOfWork(existing_session=db) as uow:
            try:
                async for chunk in process_message_use_case.execute(request):
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except Exception as e:
                yield f"data: {error_chunk.model_dump_json()}\n\n"
    
    # Обернуть генератор в aclosing для корректного cleanup
    return StreamingResponse(
        aclosing(generate()),
        ...
    )
```

### Вариант 3: Commit внутри генератора (РЕКОМЕНДУЕТСЯ)

```python
@router.post("/stream")
async def message_stream_sse(
    request: MessageStreamRequest,
    process_message_use_case=Depends(get_process_message_use_case),
    ...
):
    async def generate():
        # Создать сессию внутри генератора
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
            
            # Финальный commit
            await db.commit()
    
    return StreamingResponse(generate(), ...)
```

## Почему UoW не помог

UoW правильно управляет сессией:
- ✅ Не закрывает чужую сессию
- ✅ Делает rollback при ошибках
- ✅ Логирует операции

Но проблема в **архитектуре FastAPI + StreamingResponse**:
- FastAPI закрывает сессию ДО начала работы генератора
- UoW получает уже закрытую сессию
- Все операции выполняются на закрытой сессии

## Следующие шаги

1. 🔴 **СРОЧНО**: Реализовать Вариант 3 (создание сессии внутри генератора)
2. 🟡 Добавить проверку `session.is_active` в UoW
3. 🟡 Добавить метрики для отслеживания failed commits
4. 🟢 Написать интеграционные тесты

---

**Подготовлено**: Roo Code Agent  
**Источник**: Production logs + DB inspection
