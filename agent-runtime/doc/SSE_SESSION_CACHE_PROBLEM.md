# Проблема с кэшем SQLAlchemy при создании сессий

**Дата**: 2026-02-09  
**Статус**: 🔴 КРИТИЧНО - Вторая сессия не сохраняется

## Проблема

**Первая сессия работает, вторая ломается с FK error**.

### Паттерн

**Успешная сессия (0f394511)**:
```
03:40:44 POST /sessions → Created new SessionModel → commit → ✅ В БД
03:40:47 POST /agent/message/stream → Updated SessionModel → ✅ Работает
03:40:51 POST /agent/message/stream → Updated SessionModel → ✅ Работает
```

**Проблемная сессия (23d8084d)**:
```
03:41:11 POST /sessions → Created new SessionModel → rollback (404) → ❌ НЕ в БД
03:41:16 POST /agent/message/stream → Updated SessionModel → ❌ FK error
```

## Root Cause

### Шаг 1: Создание через `/sessions`
```python
# sessions_router.py
async def create_session(db: AsyncSession = Depends(get_db)):
    session = await service.get_or_create_conversation(session_id)
    # SessionModel создана и добавлена в db через db.add()
    return {"session_id": session_id}
    # FastAPI: await db.commit()  ← Успех
```

### Шаг 2: Проверка pending approvals
```python
# sessions_router.py
async def get_pending_approvals(session_id, db: AsyncSession = Depends(get_db)):
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(404, "Session not found")  ← ОШИБКА!
    # FastAPI: await db.rollback()  ← ОТКАТ!
```

**Проблема**: Rollback откатывает создание SessionModel из шага 1!

### Шаг 3: Обработка сообщения
```python
# messages_router.py
async with SSEUnitOfWork(session_factory=async_session_maker) as uow:
    # НОВАЯ сессия БД, но SQLAlchemy кэш сохранил SessionModel!
    session = await service.get_or_create_conversation(session_id)
    # ↑ Находит SessionModel в кэше (identity map)
    # ↓ Обновляет поля, но НЕ делает db.add()!
    
    await uow.commit(operation="create_session")
    # ↑ Commit сохраняет изменения, но модель НЕ в БД!
    
    agent = await service.get_or_create_agent(session_id)
    # ↓ FK error: session_db_id не существует в таблице sessions
```

## Почему кэш сохраняется между сессиями

SQLAlchemy использует **identity map** на уровне engine, а не session. Когда создается новая сессия через `async_session_maker()`, она использует тот же engine, и кэш сохраняется!

```python
# database.py
engine = create_async_engine(...)  # ← Один engine для всех сессий
async_session_maker = async_sessionmaker(engine, ...)  # ← Кэш на уровне engine

# messages_router.py
async with async_session_maker() as db:  # ← Новая сессия, но тот же engine!
    # SessionModel из предыдущей сессии все еще в кэше
```

## Решение

### Вариант A: Проверять наличие модели в сессии

```python
# conversation_mapper.py
else:
    # Обновить существующую модель
    model.title = entity.title
    ...
    
    # ✅ Проверить, что модель в сессии БД
    if model not in db:
        logger.warning(f"SessionModel {entity.conversation_id.value} not in session, re-adding")
        db.add(model)
    
    await db.flush()
```

### Вариант B: Использовать merge()

```python
# conversation_mapper.py
else:
    # Обновить существующую модель
    model.title = entity.title
    ...
    
    # ✅ Merge гарантирует, что модель в сессии
    model = await db.merge(model)
    await db.flush()
```

### Вариант C: Expunge после rollback

```python
# database.py get_db()
except Exception as e:
    await db.rollback()
    db.expunge_all()  # ✅ Очистить кэш после rollback
    raise
```

## Рекомендация

**Использовать Вариант A** - проверка `model not in db` перед flush.

**Почему**:
- Минимальные изменения
- Явная проверка и логирование
- Не влияет на другие части системы

## Тестирование

### Сценарий 1: Первая сессия
```
1. POST /sessions → Created new SessionModel → commit → ✅
2. GET /pending-approvals → 200 OK → ✅
3. POST /agent/message/stream → Updated SessionModel → ✅
```

### Сценарий 2: Вторая сессия (проблемный)
```
1. POST /sessions → Created new SessionModel → commit → ✅
2. GET /pending-approvals → 404 → rollback → ❌ SessionModel откачена
3. POST /agent/message/stream → Updated SessionModel (из кэша) → ❌ FK error
```

### Сценарий 3: После исправления
```
1. POST /sessions → Created new SessionModel → commit → ✅
2. GET /pending-approvals → 404 → rollback → ❌ SessionModel откачена
3. POST /agent/message/stream → Updated SessionModel → db.add(model) → ✅ Работает!
```

## Вывод

**Root Cause**: SQLAlchemy кэш сохраняет SessionModel между сессиями БД, даже после rollback.

**Решение**: Проверять `model not in db` и делать `db.add()` при обновлении.

**Приоритет**: 🔴 КРИТИЧНО

---

**Подготовлено**: CodeLab Team  
**Источник**: Production logs analysis (2026-02-09 03:40-03:42)
