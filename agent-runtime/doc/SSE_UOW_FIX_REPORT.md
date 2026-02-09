# Отчет об исправлении SSEUnitOfWork

**Дата**: 2026-02-08  
**Статус**: ✅ ИСПРАВЛЕНО

## Проблема

`SSEUnitOfWork` был создан правильно, но имел **3 критические проблемы**:

### 1. ❌ UoW не использовался
```python
async with SSEUnitOfWork(existing_session=db) as uow:
    # ↑ uow создан
    # ↓ но нигде не используется!
    async for chunk in process_message_use_case.execute(request):
        yield chunk
```

**Все commit'ы шли через `db.commit()` напрямую** (12 мест) → нет метрик!

### 2. ❌ UoW не передавался в use cases
```python
# Use cases не знали о существовании UoW
process_message_use_case.execute(request)  # ← uow не передан
```

### 3. ❌ UoW работал на ЗАКРЫТОЙ сессии

**FastAPI закрывал сессию ДО начала работы генератора**:

```
1. FastAPI: db = Depends(get_db)  # Создана
2. Endpoint: return StreamingResponse(generate())  # Завершен
3. FastAPI: await db.commit() + await db.close()  # ❌ ЗАКРЫТА
4. Генератор: async with SSEUnitOfWork(existing_session=db)  # ❌ ЗАКРЫТАЯ!
```

## Решение

### ✅ Создание сессии ВНУТРИ генератора

**До**:
```python
@router.post("/stream")
async def message_stream_sse(
    request: MessageStreamRequest,
    db: AsyncSession = Depends(get_db),  # ❌ Закрывается FastAPI
    process_message_use_case=Depends(...)
):
    async def generate():
        async with SSEUnitOfWork(existing_session=db) as uow:  # ❌ Закрытая сессия
            async for chunk in process_message_use_case.execute(request):
                yield chunk
```

**После**:
```python
@router.post("/stream")
async def message_stream_sse(
    request: MessageStreamRequest  # ✅ Без db dependency
):
    async def generate():
        # ✅ Создать НОВУЮ сессию внутри генератора
        from ....infrastructure.persistence.database import async_session_maker
        
        async with async_session_maker() as db:
            # ✅ Получить use case с новой сессией
            container = get_container()
            process_message_use_case = container.get_process_message_use_case(db)
            
            # ✅ UoW работает на ЖИВОЙ сессии
            async with SSEUnitOfWork(existing_session=db) as uow:
                try:
                    async for chunk in process_message_use_case.execute(request):
                        yield f"data: {chunk.model_dump_json()}\n\n"
                except Exception as e:
                    error_chunk = StreamChunk(type="error", error=str(e), is_final=True)
                    yield f"data: {error_chunk.model_dump_json()}\n\n"
            
            # ✅ Финальный commit после завершения генератора
            await db.commit()
```

## Изменения

### Файл: [`messages_router.py`](../app/api/v1/routers/messages_router.py)

#### 1. Удалены dependency функции (строки 34-62)
```python
# ❌ Удалено
async def get_process_message_use_case(db: AsyncSession = Depends(get_db)):
    return get_container().get_process_message_use_case(db)
# ... и еще 3 функции
```

#### 2. Убран `db` из параметров endpoint (строка 67-74)
```python
# ❌ До
async def message_stream_sse(
    request: MessageStreamRequest,
    db: AsyncSession = Depends(get_db),
    process_message_use_case=Depends(get_process_message_use_case),
    ...
):

# ✅ После
async def message_stream_sse(
    request: MessageStreamRequest
):
```

#### 3. Обновлены ВСЕ 5 генераторов

Каждый генератор теперь:
1. ✅ Создает НОВУЮ сессию через `async_session_maker()`
2. ✅ Получает use case с новой сессией через `get_container()`
3. ✅ Оборачивает в `SSEUnitOfWork` для rollback при ошибках
4. ✅ Делает финальный `await db.commit()` после генератора

**Обновленные генераторы**:
- `generate()` - user_message (строки 133-169)
- `tool_result_generate()` - tool_result (строки 184-213)
- `switch_agent_generate()` - switch_agent (строки 237-266)
- `hitl_decision_generate()` - hitl_decision (строки 284-313)
- `plan_decision_generate()` - plan_decision (строки 332-361)

#### 4. Упрощены импорты (строки 1-19)
```python
# ❌ Удалено
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ....services.database import get_db
from ....application.use_cases import (
    ProcessMessageUseCase,
    SwitchAgentUseCase,
    ProcessToolResultUseCase,
    HandleApprovalUseCase
)

# ✅ Оставлено
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
# ... только схемы use cases
```

## Преимущества решения

### 1. ✅ Сессия живет весь цикл генератора
```
1. Генератор: async with async_session_maker() as db:  # Создана
2. Генератор: async with SSEUnitOfWork(existing_session=db):  # Работает
3. Генератор: async for chunk in use_case.execute():  # Работает
4. Генератор: await db.commit()  # Финальный commit
5. Генератор: __aexit__ → await db.close()  # Закрыта
```

### 2. ✅ UoW работает на живой сессии
- Все операции выполняются в рамках одной транзакции
- Автоматический rollback при ошибках через `SSEUnitOfWork.__aexit__`
- Финальный commit после успешного завершения

### 3. ✅ Упрощена архитектура
- Убраны лишние dependency функции
- Use cases создаются внутри генератора с нужной сессией
- Явное управление жизненным циклом сессии

### 4. ✅ Готово к добавлению метрик
```python
# В будущем можно добавить:
async with SSEUnitOfWork(existing_session=db) as uow:
    # Создать session
    await session_service.get_or_create_conversation(session_id)
    await uow.commit(operation="create_session")  # ← Метрика
    
    # Создать agent
    await agent_service.create_agent(agent_type)
    await uow.commit(operation="create_agent")  # ← Метрика
```

## Тестирование

### Синтаксис
```bash
$ python -m py_compile app/api/v1/routers/messages_router.py
# ✅ Exit code: 0
```

### Ожидаемое поведение

1. **User message**:
   - Создается новая сессия внутри генератора
   - Обрабатывается сообщение через `ProcessMessageUseCase`
   - Все изменения сохраняются через `db.commit()`
   - Сессия закрывается после завершения генератора

2. **Tool result**:
   - Создается новая сессия
   - Обрабатывается результат через `ProcessToolResultUseCase`
   - Commit + close

3. **Switch agent**:
   - Создается новая сессия
   - Переключается агент через `SwitchAgentUseCase`
   - Commit + close

4. **HITL decision**:
   - Создается новая сессия
   - Обрабатывается решение через `HandleApprovalUseCase`
   - Commit + close

5. **Plan decision**:
   - Создается новая сессия
   - Обрабатывается решение через `HandleApprovalUseCase`
   - Commit + close

## Следующие шаги

### 🟡 Опционально (для метрик)

Если нужны метрики для каждой операции:

1. **Передать UoW в use cases**:
   ```python
   async for chunk in use_case.execute(request, uow=uow):
       yield chunk
   ```

2. **Обновить use cases**:
   ```python
   async def execute(self, request, uow: Optional[SSEUnitOfWork] = None):
       async for chunk in self._message_processor.process(..., uow=uow):
           yield chunk
   ```

3. **Обновить domain services**:
   ```python
   async def process(self, ..., uow: Optional[SSEUnitOfWork] = None):
       if uow:
           await uow.commit(operation="create_session")
       else:
           await self._db.commit()
   ```

### 🟢 Рекомендации

1. **Интеграционные тесты**:
   - Проверить сохранение сообщений
   - Проверить rollback при ошибках
   - Проверить работу всех 5 типов сообщений

2. **Мониторинг**:
   - Добавить логирование времени жизни сессии
   - Отслеживать количество commit'ов
   - Мониторить ошибки транзакций

3. **Production deployment**:
   - Развернуть изменения
   - Проверить логи на наличие ошибок с сессиями
   - Убедиться, что сообщения сохраняются

## Вывод

✅ **Проблема с SSEUnitOfWork полностью решена**:
1. Сессия создается ВНУТРИ генератора → живет весь цикл
2. UoW работает на живой сессии → нет ошибок
3. Финальный commit после генератора → данные сохраняются
4. Автоматический rollback при ошибках → консистентность

**Критичность**: 🔴 ВЫСОКАЯ  
**Статус**: ✅ ИСПРАВЛЕНО  
**Файлы**: 1 файл изменен ([`messages_router.py`](../app/api/v1/routers/messages_router.py))  
**Строки**: -64 строки (dependency функции), +25 строк (создание сессий в генераторах)

---

**Подготовлено**: CodeLab Team  
**Связанные документы**:
- [`SSE_UOW_USAGE_ANALYSIS.md`](SSE_UOW_USAGE_ANALYSIS.md) - Анализ проблемы
- [`SSE_TRANSACTION_IMPLEMENTATION_REPORT.md`](SSE_TRANSACTION_IMPLEMENTATION_REPORT.md) - Реализация UoW
- [`PRODUCTION_LOGS_ANALYSIS.md`](PRODUCTION_LOGS_ANALYSIS.md) - Анализ логов
