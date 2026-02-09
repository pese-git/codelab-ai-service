# Внедрение Unit of Work для SSE-стримов

**Дата**: 2026-02-08  
**Статус**: 🚧 В процессе реализации

## Текущее состояние

### ✅ Что уже работает корректно

1. **Единая сессия БД на запрос**
   - Создается через [`get_db()`](../app/infrastructure/persistence/database.py:112)
   - Передается через DI во все слои
   - Используется в [`MessageProcessor`](../app/domain/services/message_processor.py:54) и [`StreamLLMResponseHandler`](../app/application/handlers/stream_llm_response_handler.py:124)

2. **Явные commit'ы**
   - После создания session/agent: [`MessageProcessor:119`](../app/domain/services/message_processor.py:119)
   - После сохранения messages: [`StreamLLMResponseHandler:335`](../app/application/handlers/stream_llm_response_handler.py:335)

3. **DI Container**
   - Корректно передает `db` во все сервисы: [`DIContainer:124`](../app/core/di/container.py:124)

### ⚠️ Что нужно улучшить

1. **Нет явного управления границами транзакций**
   - Commit'ы разбросаны по коду
   - Сложно отследить, где начинается и заканчивается транзакция
   - Нет централизованного rollback при ошибках

2. **Нет метрик транзакций**
   - Не отслеживается длительность транзакций
   - Нет алертов на долгие транзакции (> 100ms)

3. **Нет изоляции между SSE-стримами**
   - Каждый стрим должен иметь свой UoW

## План внедрения

### Фаза 1: Подготовка (1-2 часа)

#### 1.1. Обновить `SSEUnitOfWork`

Добавить поддержку существующей сессии (не создавать новую):

```python
class SSEUnitOfWork:
    """Unit of Work для SSE-стримов."""
    
    def __init__(
        self, 
        session_factory=None,
        existing_session: Optional[AsyncSession] = None
    ):
        """
        Инициализация UoW.
        
        Args:
            session_factory: Фабрика для создания новой сессии (опционально)
            existing_session: Существующая сессия из FastAPI DI (опционально)
        """
        if existing_session is None and session_factory is None:
            raise ValueError("Either session_factory or existing_session must be provided")
        
        self._session_factory = session_factory
        self._session = existing_session
        self._owns_session = existing_session is None
        logger.debug(f"SSEUnitOfWork initialized (owns_session={self._owns_session})")
    
    async def __aenter__(self):
        """Вход в контекст."""
        if self._session is None:
            self._session = self._session_factory()
            logger.debug("SSEUnitOfWork: New session created")
        else:
            logger.debug("SSEUnitOfWork: Using existing session")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекста."""
        if self._session is None:
            return
        
        try:
            if exc_type is not None:
                logger.warning(f"SSEUnitOfWork: Exception ({exc_type.__name__}), rolling back")
                await self._session.rollback()
        finally:
            # Закрываем сессию только если мы её создали
            if self._owns_session:
                await self._session.close()
                logger.debug("SSEUnitOfWork: Session closed")
            else:
                logger.debug("SSEUnitOfWork: Session ownership retained by FastAPI")
            self._session = None
```

#### 1.2. Добавить метрики

```python
import time
from prometheus_client import Histogram, Counter

# Метрики
transaction_duration = Histogram(
    'sse_transaction_duration_seconds',
    'Duration of SSE micro-transactions',
    ['operation']
)

transaction_commits = Counter(
    'sse_transaction_commits_total',
    'Total number of transaction commits',
    ['operation', 'status']
)

class SSEUnitOfWork:
    # ... existing code ...
    
    async def commit(self, operation: str = "unknown"):
        """
        Commit с метриками.
        
        Args:
            operation: Название операции для метрик (например, "save_messages")
        """
        if self._session is None:
            raise RuntimeError("SSEUnitOfWork is not in context")
        
        start_time = time.time()
        try:
            await self._session.commit()
            duration = time.time() - start_time
            
            transaction_duration.labels(operation=operation).observe(duration)
            transaction_commits.labels(operation=operation, status="success").inc()
            
            logger.debug(f"SSEUnitOfWork: Transaction committed (operation={operation}, duration={duration:.3f}s)")
            
            # Предупреждение о долгих транзакциях
            if duration > 0.1:  # > 100ms
                logger.warning(
                    f"⚠️ SLOW TRANSACTION: {operation} took {duration:.3f}s (> 100ms threshold)"
                )
        except Exception as e:
            transaction_commits.labels(operation=operation, status="error").inc()
            logger.error(f"SSEUnitOfWork: Commit failed (operation={operation}): {e}")
            raise
```

### Фаза 2: Внедрение в API handlers (2-3 часа)

#### 2.1. Обновить `messages_router.py`

**Вариант A: Минимальные изменения (РЕКОМЕНДУЕТСЯ)**

Использовать существующую сессию из FastAPI DI:

```python
@router.post("/stream")
async def message_stream_sse(
    request: MessageStreamRequest,
    db: AsyncSession = Depends(get_db),  # Получаем сессию из FastAPI
    process_message_use_case=Depends(get_process_message_use_case),
    ...
):
    """SSE streaming endpoint."""
    
    async def generate():
        # Обернуть в UoW для явного управления транзакциями
        async with SSEUnitOfWork(existing_session=db) as uow:
            try:
                # Use case уже использует db через DI
                async for chunk in process_message_use_case.execute(use_case_request):
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                error_chunk = StreamChunk(type="error", error=str(e), is_final=True)
                yield f"data: {error_chunk.model_dump_json()}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
```

**Вариант B: Полная интеграция (СЛЕДУЮЩИЙ ЭТАП)**

Передать UoW в use case:

```python
@router.post("/stream")
async def message_stream_sse(
    request: MessageStreamRequest,
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming endpoint."""
    
    async def generate():
        async with SSEUnitOfWork(existing_session=db) as uow:
            try:
                # Создать use case с UoW
                container = get_container()
                use_case = container.get_process_message_use_case_with_uow(uow)
                
                async for chunk in use_case.execute(use_case_request):
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                yield f"data: {StreamChunk(type='error', error=str(e)).model_dump_json()}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Фаза 3: Обновление Use Cases (3-4 часа)

#### 3.1. Добавить поддержку UoW в `ProcessMessageUseCase`

```python
class ProcessMessageUseCase(StreamingUseCase[ProcessMessageRequest, StreamChunk]):
    """Use Case для обработки сообщений."""
    
    def __init__(
        self,
        message_processor,
        lock_manager,
        uow: Optional[SSEUnitOfWork] = None  # Опциональный UoW
    ):
        self._message_processor = message_processor
        self._lock_manager = lock_manager
        self._uow = uow
    
    async def execute(self, request: ProcessMessageRequest) -> AsyncGenerator[StreamChunk, None]:
        """Выполнить обработку сообщения."""
        try:
            async with self._lock_manager.lock(request.session_id):
                async for chunk in self._message_processor.process(
                    session_id=request.session_id,
                    message=request.message,
                    agent_type=request.agent_type
                ):
                    yield chunk
                    
                    # Если есть UoW, commit после важных операций
                    if self._uow and chunk.type in ["agent_switched", "tool_call"]:
                        await self._uow.commit(operation=f"process_{chunk.type}")
        
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            yield StreamChunk(type="error", error=str(e), is_final=True)
```

#### 3.2. Обновить `MessageProcessor`

```python
class MessageProcessor:
    """Процессор сообщений."""
    
    def __init__(
        self,
        session_service,
        agent_service,
        agent_router,
        stream_handler,
        switch_helper,
        db: AsyncSession,
        uow: Optional[SSEUnitOfWork] = None  # Опциональный UoW
    ):
        # ... existing code ...
        self._uow = uow
    
    async def process(
        self,
        session_id: str,
        message: str,
        agent_type: Optional[AgentType] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """Обработать сообщение."""
        
        # 1. Получить/создать сессию и агента
        conversation = await self._session_service.get_or_create_conversation(session_id)
        agent_context = await self._agent_service.get_or_create_agent_context(session_id, agent_type)
        
        # COMMIT 1: Сохранить session и agent
        await self._db.commit()
        if self._uow:
            await self._uow.commit(operation="create_session_agent")
        
        # 2. Добавить user message
        conversation.add_user_message(message)
        await self._session_service.update_conversation(conversation)
        
        # 3. Обработать через LLM
        async for chunk in self._stream_handler.handle_stream(...):
            yield chunk
        
        # COMMIT 2: Сохранить messages (выполняется в StreamLLMResponseHandler)
```

### Фаза 4: Тестирование (2-3 часа)

#### 4.1. Интеграционные тесты

```python
# tests/integration/test_sse_unit_of_work.py

import pytest
from app.infrastructure.persistence.unit_of_work import SSEUnitOfWork

@pytest.mark.asyncio
async def test_uow_with_existing_session(async_session):
    """Тест UoW с существующей сессией."""
    async with SSEUnitOfWork(existing_session=async_session) as uow:
        # Проверить, что используется та же сессия
        assert uow.session is async_session
        
        # Выполнить операцию
        await uow.commit(operation="test")
    
    # Сессия не должна быть закрыта (владеет FastAPI)
    assert not async_session.is_active


@pytest.mark.asyncio
async def test_uow_rollback_on_error(async_session):
    """Тест rollback при ошибке."""
    try:
        async with SSEUnitOfWork(existing_session=async_session) as uow:
            # Создать запись
            session_model = SessionModel(id="test-session")
            uow.session.add(session_model)
            await uow.commit(operation="create_session")
            
            # Вызвать ошибку
            raise ValueError("Test error")
    except ValueError:
        pass
    
    # Проверить, что rollback выполнен
    result = await async_session.execute(
        select(SessionModel).where(SessionModel.id == "test-session")
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_transaction_metrics(async_session):
    """Тест метрик транзакций."""
    from prometheus_client import REGISTRY
    
    async with SSEUnitOfWork(existing_session=async_session) as uow:
        await uow.commit(operation="test_operation")
    
    # Проверить метрики
    metrics = REGISTRY.get_sample_value(
        'sse_transaction_commits_total',
        {'operation': 'test_operation', 'status': 'success'}
    )
    assert metrics >= 1
```

### Фаза 5: Мониторинг (1-2 часа)

#### 5.1. Prometheus метрики

Уже добавлены в Фазе 1.2:
- `sse_transaction_duration_seconds` - длительность транзакций
- `sse_transaction_commits_total` - количество commit'ов

#### 5.2. Grafana Dashboard

```yaml
# grafana/dashboards/sse_transactions.json
{
  "title": "SSE Transactions",
  "panels": [
    {
      "title": "Transaction Duration (p95)",
      "targets": [
        {
          "expr": "histogram_quantile(0.95, rate(sse_transaction_duration_seconds_bucket[5m]))"
        }
      ]
    },
    {
      "title": "Slow Transactions (> 100ms)",
      "targets": [
        {
          "expr": "rate(sse_transaction_duration_seconds_bucket{le=\"0.1\"}[5m]) < 1"
        }
      ]
    },
    {
      "title": "Commit Success Rate",
      "targets": [
        {
          "expr": "rate(sse_transaction_commits_total{status=\"success\"}[5m]) / rate(sse_transaction_commits_total[5m])"
        }
      ]
    }
  ]
}
```

#### 5.3. Алерты

```yaml
# prometheus/alerts/sse_transactions.yml
groups:
  - name: sse_transactions
    rules:
      - alert: SlowSSETransaction
        expr: histogram_quantile(0.95, rate(sse_transaction_duration_seconds_bucket[5m])) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow SSE transactions detected"
          description: "95th percentile of SSE transaction duration is {{ $value }}s (> 100ms)"
      
      - alert: HighTransactionFailureRate
        expr: rate(sse_transaction_commits_total{status="error"}[5m]) / rate(sse_transaction_commits_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High transaction failure rate"
          description: "{{ $value | humanizePercentage }} of transactions are failing"
```

## Чеклист реализации

### Фаза 1: Подготовка
- [ ] Обновить `SSEUnitOfWork` для поддержки существующей сессии
- [ ] Добавить метрики Prometheus
- [ ] Написать unit-тесты для UoW

### Фаза 2: API Handlers
- [ ] Обновить `messages_router.py` (Вариант A)
- [ ] Протестировать SSE endpoint
- [ ] Проверить логи на корректность commit'ов

### Фаза 3: Use Cases
- [ ] Добавить поддержку UoW в `ProcessMessageUseCase`
- [ ] Обновить `MessageProcessor`
- [ ] Обновить `StreamLLMResponseHandler`

### Фаза 4: Тестирование
- [ ] Написать интеграционные тесты
- [ ] Запустить нагрузочное тестирование
- [ ] Проверить метрики в Prometheus

### Фаза 5: Мониторинг
- [ ] Создать Grafana dashboard
- [ ] Настроить алерты
- [ ] Документировать troubleshooting

## Оценка времени

| Фаза | Время | Приоритет |
|------|-------|-----------|
| Фаза 1: Подготовка | 1-2 часа | 🔴 Высокий |
| Фаза 2: API Handlers | 2-3 часа | 🔴 Высокий |
| Фаза 3: Use Cases | 3-4 часа | 🟡 Средний |
| Фаза 4: Тестирование | 2-3 часа | 🔴 Высокий |
| Фаза 5: Мониторинг | 1-2 часа | 🟢 Низкий |
| **ИТОГО** | **9-14 часов** | **~2 дня** |

## Риски и митигация

### Риск 1: Конфликт с существующими commit'ами

**Проблема**: В коде уже есть явные `await db.commit()`.

**Решение**: 
- Вариант A: Оставить существующие commit'ы, UoW только для rollback
- Вариант B: Постепенно заменить на `await uow.commit()`

### Риск 2: Производительность

**Проблема**: Дополнительный overhead от UoW.

**Решение**:
- Использовать существующую сессию (не создавать новую)
- Метрики покажут реальный impact
- Оптимизировать при необходимости

### Риск 3: Сложность отладки

**Проблема**: Дополнительный слой абстракции.

**Решение**:
- Подробное логирование в UoW
- Метрики для каждой операции
- Документация troubleshooting

## Следующие шаги

1. ✅ **Аудит завершен** - проблем с сессиями не найдено
2. ✅ **SessionModule проверен** - DI работает корректно
3. 🚧 **Начать Фазу 1** - обновить `SSEUnitOfWork`
4. ⏭️ **Фаза 2** - внедрить в API handlers
5. ⏭️ **Фаза 3** - обновить use cases

---

**Документация**:
- [`SSE_TRANSACTION_ARCHITECTURE_SOLUTION.md`](SSE_TRANSACTION_ARCHITECTURE_SOLUTION.md) - архитектурное решение
- [`SSE_TRANSACTION_IMPLEMENTATION_GUIDE.md`](SSE_TRANSACTION_IMPLEMENTATION_GUIDE.md) - руководство по реализации
- [`SESSION_AUDIT_REPORT.md`](SESSION_AUDIT_REPORT.md) - результаты аудита
