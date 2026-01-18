# EVENT-DRIVEN ARCHITECTURE - РУКОВОДСТВО

**Версия:** 1.0  
**Дата:** 17 января 2026  
**Статус:** Реализовано (Фаза 1)

---

## ОБЗОР

Этот пакет реализует Event-Driven Architecture для Agent Runtime Service, обеспечивая слабую связанность компонентов и улучшенную observability.

Event-Driven Architecture позволяет компонентам взаимодействовать через события вместо прямых вызовов методов. Это обеспечивает:

- **Слабую связанность**: Компоненты не знают друг о друге
- **Расширяемость**: Новые подписчики добавляются без изменения существующего кода
- **Observability**: Все события логируются и могут быть проанализированы
- **Масштабируемость**: Поддержка distributed events через Redis Pub/Sub
- **Тестируемость**: Легко мокировать события для тестирования

## АРХИТЕКТУРА

```
┌─────────────────┐
│   Publishers    │ ──publish──> ┌──────────────┐ ──notify──> ┌─────────────────┐
│   (Сервисы)     │              │  Event Bus   │             │   Subscribers   │
└─────────────────┘              └──────────────┘             └─────────────────┘
```

### Компоненты

1. **Event Bus** - Централизованная шина событий (pub/sub)
2. **Events** - Типизированные события для различных операций
3. **Publishers** - Компоненты, публикующие события (сервисы, агенты)
4. **Subscribers** - Компоненты, подписанные на события (метрики, логирование)

---

## КОМПОНЕНТЫ

### Типы событий (`event_types.py`)

Определяет все типы событий и категории:

```python
from app.events.event_types import EventType, EventCategory

# Категории событий
EventCategory.AGENT    # События агентов
EventCategory.SESSION  # События сессий
EventCategory.TOOL     # События инструментов
EventCategory.HITL     # HITL события
EventCategory.SYSTEM   # Системные события
EventCategory.METRICS  # События метрик

# Конкретные типы событий
EventType.AGENT_SWITCHED              # Переключение агента
EventType.TOOL_EXECUTION_REQUESTED    # Запрос выполнения инструмента
EventType.HITL_DECISION_MADE          # Решение пользователя
# ... и другие
```

### Базовое событие (`base_event.py`)

Базовый класс для всех событий:

```python
from app.events.base_event import BaseEvent

event = BaseEvent(
    event_type=EventType.AGENT_SWITCHED,
    event_category=EventCategory.AGENT,
    session_id="session-123",
    correlation_id="corr-456",  # Для трейсинга
    data={"from_agent": "orchestrator", "to_agent": "coder"},
    source="multi_agent_orchestrator"
)
```

**Поля события:**
- `event_id` - Уникальный ID события (UUID)
- `event_type` - Тип события
- `event_category` - Категория события
- `timestamp` - Время создания
- `session_id` - ID сессии (опционально)
- `correlation_id` - ID для трейсинга связанных событий
- `causation_id` - ID события-причины
- `data` - Данные события (Dict)
- `source` - Компонент-источник
- `version` - Версия формата события

### Event Bus (`event_bus.py`)

Централизованный механизм pub/sub:

```python
from app.events.event_bus import event_bus

# Подписка на конкретный тип события
@event_bus.subscribe(event_type=EventType.AGENT_SWITCHED)
async def on_agent_switched(event: BaseEvent):
    print(f"Агент переключен: {event.data}")

# Подписка на категорию событий
@event_bus.subscribe(event_category=EventCategory.AGENT)
async def on_any_agent_event(event: BaseEvent):
    print(f"Событие агента: {event.event_type}")

# Публикация события
await event_bus.publish(
    AgentSwitchedEvent(
        session_id="session-123",
        from_agent="orchestrator",
        to_agent="coder",
        reason="Требуется модификация кода"
    )
)
```

**Возможности EventBus:**
- Подписка по типу события
- Подписка по категории
- Wildcard подписки (все события)
- Приоритеты обработчиков
- Middleware для обработки событий
- Статистика публикаций
- Thread-safe операции

---

## ТИПЫ СОБЫТИЙ

### События агентов (`agent_events.py`)

События, связанные с операциями агентов:

#### AgentSwitchedEvent
Публикуется при переключении агента.

```python
from app.events.agent_events import AgentSwitchedEvent

event = AgentSwitchedEvent(
    session_id="session-123",
    from_agent="orchestrator",
    to_agent="coder",
    reason="Требуется написание кода",
    confidence="high"
)
await event_bus.publish(event)
```

#### AgentProcessingStartedEvent
Публикуется когда агент начинает обработку сообщения.

```python
event = AgentProcessingStartedEvent(
    session_id="session-123",
    agent_type="coder",
    message="Создай функцию сортировки"
)
```

#### AgentProcessingCompletedEvent
Публикуется когда агент завершает обработку.

```python
event = AgentProcessingCompletedEvent(
    session_id="session-123",
    agent_type="coder",
    duration_ms=1500.5,
    success=True
)
```

#### AgentErrorOccurredEvent
Публикуется при ошибке в агенте.

```python
event = AgentErrorOccurredEvent(
    session_id="session-123",
    agent_type="coder",
    error_message="File not found",
    error_type="FileNotFoundError"
)
```

### События инструментов (`tool_events.py`)

События, связанные с выполнением инструментов и HITL:

#### ToolExecutionRequestedEvent
Запрос на выполнение инструмента.

```python
from app.events.tool_events import ToolExecutionRequestedEvent

event = ToolExecutionRequestedEvent(
    session_id="session-123",
    tool_name="write_file",
    arguments={"path": "test.py", "content": "..."},
    call_id="call-456",
    agent="coder"
)
```

#### ToolApprovalRequiredEvent
Инструмент требует подтверждения пользователя.

```python
event = ToolApprovalRequiredEvent(
    session_id="session-123",
    tool_name="execute_command",
    arguments={"command": "rm -rf /tmp"},
    call_id="call-456",
    reason="Опасная команда"
)
```

#### HITLDecisionMadeEvent
Пользователь принял решение по HITL approval.

```python
event = HITLDecisionMadeEvent(
    session_id="session-123",
    call_id="call-456",
    decision="APPROVE",  # APPROVE, EDIT, REJECT
    tool_name="write_file",
    original_args={"path": "test.py"},
    modified_args=None
)
```

### События сессий (`session_events.py`)

События, связанные с управлением сессиями:

#### SessionCreatedEvent
Создание новой сессии.

```python
from app.events.session_events import SessionCreatedEvent

event = SessionCreatedEvent(
    session_id="session-123",
    system_prompt="You are a helpful assistant"
)
```

#### MessageAddedEvent
Добавление сообщения в сессию.

```python
event = MessageAddedEvent(
    session_id="session-123",
    role="user",
    content_length=100,
    agent_name="coder"
)
```

---

## ПОДПИСЧИКИ

### Metrics Collector (`subscribers/metrics_collector.py`)

Автоматически собирает метрики из событий:

```python
from app.events.subscribers import metrics_collector

# Получить все метрики
metrics = metrics_collector.get_metrics()
print(metrics["agent_switches"])      # Переключения агентов
print(metrics["tool_executions"])     # Выполнения инструментов
print(metrics["hitl_decisions"])      # HITL решения

# Получить конкретные метрики
avg_duration = metrics_collector.get_agent_avg_duration("coder")
success_rate = metrics_collector.get_tool_success_rate("write_file")
switch_count = metrics_collector.get_agent_switch_count("orchestrator", "coder")
```

**Собираемые метрики:**
- Количество переключений между агентами
- Средняя длительность обработки по агентам
- Количество успешных/неуспешных обработок
- Статистика выполнения инструментов
- HITL решения (approve/edit/reject)
- Ошибки по агентам и типам

### Audit Logger (`subscribers/audit_logger.py`)

Логирует критичные события для аудита:

```python
from app.events.subscribers import audit_logger

# Получить audit log
log = audit_logger.get_audit_log(
    session_id="session-123",
    event_type="agent_switched",
    limit=10
)

# Каждая запись содержит:
# - timestamp
# - event_type
# - event_id
# - session_id
# - correlation_id
# - специфичные данные события
```

**Логируемые события:**
- Переключения агентов
- HITL решения
- Ошибки агентов
- Ошибки выполнения инструментов
- Требования approval

---

## ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### Публикация событий

```python
from app.events.event_bus import event_bus
from app.events.agent_events import AgentSwitchedEvent

# Публикация с ожиданием обработчиков
await event_bus.publish(
    AgentSwitchedEvent(
        session_id="session-123",
        from_agent="orchestrator",
        to_agent="coder",
        reason="Модификация кода"
    ),
    wait_for_handlers=True  # Ждать завершения всех обработчиков
)

# Fire and forget (асинхронно)
await event_bus.publish(event)  # Возвращается сразу
```

### Подписка на события

```python
from app.events.event_bus import event_bus
from app.events.event_types import EventType, EventCategory

# Подписка на конкретный тип события
@event_bus.subscribe(event_type=EventType.AGENT_SWITCHED, priority=10)
async def high_priority_handler(event):
    print(f"Высокий приоритет: {event.data}")

# Подписка на категорию событий
@event_bus.subscribe(event_category=EventCategory.AGENT)
async def category_handler(event):
    print(f"Любое событие агента: {event.event_type}")

# Wildcard подписка (все события)
@event_bus.subscribe()
async def wildcard_handler(event):
    print(f"Любое событие: {event.event_type}")

# Прямая подписка (без декоратора)
async def my_handler(event):
    print(event.data)

unsubscribe = event_bus.subscribe(
    event_type=EventType.AGENT_SWITCHED,
    handler=my_handler
)

# Отписка
unsubscribe()
```

### Создание пользовательских подписчиков

```python
from app.events.event_bus import event_bus
from app.events.event_types import EventType

class MyCustomSubscriber:
    """Пользовательский подписчик."""
    
    def __init__(self):
        self._setup_subscriptions()
    
    def _setup_subscriptions(self):
        """Настройка подписок."""
        event_bus.subscribe(
            event_type=EventType.AGENT_SWITCHED,
            handler=self._on_agent_switched,
            priority=5
        )
        
        event_bus.subscribe(
            event_category=EventCategory.TOOL,
            handler=self._on_tool_event,
            priority=3
        )
    
    async def _on_agent_switched(self, event):
        """Обработчик переключения агента."""
        print(f"Агент переключен: {event.data['from_agent']} -> {event.data['to_agent']}")
        # Ваша логика здесь
    
    async def _on_tool_event(self, event):
        """Обработчик событий инструментов."""
        print(f"Событие инструмента: {event.event_type}")
        # Ваша логика здесь

# Инициализация
my_subscriber = MyCustomSubscriber()
```

### Использование Middleware

Middleware позволяет обрабатывать события перед их доставкой подписчикам:

```python
from app.events.event_bus import event_bus
from datetime import datetime

# Middleware для валидации событий
async def validate_event_middleware(event):
    if not event.session_id:
        logger.warning(f"Событие {event.event_type} без session_id")
    return event

# Middleware для обогащения событий
async def enrich_event_middleware(event):
    event.data["enriched_at"] = datetime.utcnow().isoformat()
    return event

# Middleware для фильтрации событий
async def filter_test_events_middleware(event):
    if event.session_id and event.session_id.startswith("test-"):
        return None  # Отменить тестовые события
    return event

# Добавление middleware
event_bus.add_middleware(validate_event_middleware)
event_bus.add_middleware(enrich_event_middleware)
event_bus.add_middleware(filter_test_events_middleware)
```

---

## ИНТЕГРАЦИЯ В СУЩЕСТВУЮЩИЙ КОД

### Фаза 1: Параллельная публикация (Текущая)

События публикуются параллельно с существующими прямыми вызовами:

```python
# Старый код продолжает работать
context.switch_agent(new_agent, reason)

# Новое событие также публикуется
await event_bus.publish(
    AgentSwitchedEvent(
        session_id=session_id,
        from_agent=current_agent.value,
        to_agent=new_agent.value,
        reason=reason
    )
)
```

### Пример интеграции в MultiAgentOrchestrator

```python
# app/services/multi_agent_orchestrator.py

from app.events.event_bus import event_bus
from app.events.agent_events import (
    AgentSwitchedEvent,
    AgentProcessingStartedEvent,
    AgentProcessingCompletedEvent
)
import time
import uuid

class MultiAgentOrchestrator:
    async def process_message(
        self,
        session_id: str,
        message: str,
        agent_type: Optional[AgentType] = None
    ):
        correlation_id = str(uuid.uuid4())
        
        # Публикация события начала обработки
        await event_bus.publish(
            AgentProcessingStartedEvent(
                session_id=session_id,
                agent_type=current_agent.value,
                message=message,
                correlation_id=correlation_id
            )
        )
        
        start_time = time.time()
        success = True
        
        try:
            # Существующая логика обработки
            async for chunk in agent.process(message, history):
                if chunk.type == "switch_agent":
                    # Публикация события переключения
                    await event_bus.publish(
                        AgentSwitchedEvent(
                            session_id=session_id,
                            from_agent=current_agent.value,
                            to_agent=target_agent.value,
                            reason=chunk.data.get("reason", ""),
                            correlation_id=correlation_id
                        )
                    )
                
                yield chunk
        
        except Exception as e:
            success = False
            raise
        
        finally:
            # Публикация события завершения
            duration_ms = (time.time() - start_time) * 1000
            await event_bus.publish(
                AgentProcessingCompletedEvent(
                    session_id=session_id,
                    agent_type=current_agent.value,
                    duration_ms=duration_ms,
                    success=success,
                    correlation_id=correlation_id
                )
            )
```

---

## ТЕСТИРОВАНИЕ

### Unit тесты

```python
import pytest
from app.events.event_bus import EventBus
from app.events.agent_events import AgentSwitchedEvent
from app.events.event_types import EventType

@pytest.mark.asyncio
async def test_event_publishing():
    """Тест публикации события."""
    bus = EventBus()
    received = []
    
    @bus.subscribe(event_type=EventType.AGENT_SWITCHED)
    async def handler(event):
        received.append(event)
    
    await bus.publish(
        AgentSwitchedEvent(
            session_id="test",
            from_agent="orchestrator",
            to_agent="coder",
            reason="test"
        ),
        wait_for_handlers=True
    )
    
    assert len(received) == 1
    assert received[0].data["to_agent"] == "coder"
```

### Integration тесты

```python
from app.events.subscribers import metrics_collector

@pytest.mark.asyncio
async def test_metrics_collection():
    """Тест сбора метрик."""
    # Публикация события
    await event_bus.publish(
        AgentSwitchedEvent(
            session_id="test",
            from_agent="orchestrator",
            to_agent="coder",
            reason="test"
        ),
        wait_for_handlers=True
    )
    
    # Проверка метрик
    count = metrics_collector.get_agent_switch_count("orchestrator", "coder")
    assert count > 0
```

Полный набор тестов: [`tests/test_event_bus.py`](../tests/test_event_bus.py)

---

## ЛУЧШИЕ ПРАКТИКИ

### 1. Используйте Correlation ID

Всегда передавайте correlation_id для трейсинга связанных событий:

```python
correlation_id = str(uuid.uuid4())

await event_bus.publish(
    AgentSwitchedEvent(..., correlation_id=correlation_id)
)

await event_bus.publish(
    ToolExecutionRequestedEvent(..., correlation_id=correlation_id)
)
```

### 2. Обрабатывайте ошибки в подписчиках

Всегда оборачивайте логику подписчика в try/except:

```python
@event_bus.subscribe(event_type=EventType.AGENT_SWITCHED)
async def my_handler(event):
    try:
        # Ваша логика
        await do_something(event)
    except Exception as e:
        logger.error(f"Ошибка в обработчике: {e}")
        # Не пробрасывайте исключение - дайте другим обработчикам продолжить
```

### 3. Используйте правильные приоритеты

- **10**: Критичные обработчики (audit logging, безопасность)
- **5**: Обычные обработчики (метрики, уведомления)
- **0**: Низкий приоритет (аналитика, кэширование)

### 4. Выбирайте wait_for_handlers разумно

- `wait_for_handlers=True` - для критичных операций
- `wait_for_handlers=False` (по умолчанию) - для fire-and-forget

### 5. Данные событий должны быть сериализуемы

Данные события должны быть JSON-сериализуемыми:

```python
# Хорошо
data = {"count": 5, "name": "test", "items": ["a", "b"]}

# Плохо
data = {"object": some_complex_object}  # Не сериализуется
```

---

## СТАТИСТИКА И МОНИТОРИНГ

### Получение статистики Event Bus

```python
from app.events.event_bus import event_bus

stats = event_bus.get_stats()
print(f"Всего опубликовано: {stats.total_published}")
print(f"Успешных обработчиков: {stats.successful_handlers}")
print(f"Неудачных обработчиков: {stats.failed_handlers}")
print(f"Последнее событие: {stats.last_event_time}")
```

### Получение метрик

```python
from app.events.subscribers import metrics_collector

# Все метрики
all_metrics = metrics_collector.get_metrics()

# Структура метрик:
{
    "agent_switches": {
        "orchestrator_to_coder": 15,
        "coder_to_debug": 3,
        ...
    },
    "agent_processing": {
        "coder": {
            "count": 20,
            "total_duration_ms": 30000,
            "success_count": 18,
            "failure_count": 2
        },
        ...
    },
    "tool_executions": {
        "write_file": {
            "requested": 10,
            "completed": 8,
            "failed": 2,
            "requires_approval": 10
        },
        ...
    },
    "hitl_decisions": {
        "write_file": {
            "APPROVE": 7,
            "EDIT": 2,
            "REJECT": 1
        },
        ...
    },
    "errors": {
        "coder": {
            "FileNotFoundError": 1,
            "ValueError": 1
        },
        ...
    }
}
```

### Получение audit log

```python
from app.events.subscribers import audit_logger

# Все записи
all_logs = audit_logger.get_audit_log()

# Фильтрация по сессии
session_logs = audit_logger.get_audit_log(session_id="session-123")

# Фильтрация по типу события
switch_logs = audit_logger.get_audit_log(event_type="agent_switched")

# Ограничение количества
recent_logs = audit_logger.get_audit_log(limit=10)

# Комбинированная фильтрация
logs = audit_logger.get_audit_log(
    session_id="session-123",
    event_type="hitl_decision_made",
    limit=5
)
```

---

## TROUBLESHOOTING

### События не получаются

1. Проверьте, что подписчик инициализирован до публикации событий
2. Убедитесь, что тип/категория события совпадает с подпиской
3. Проверьте логи на наличие ошибок в обработчиках

### Проблемы с производительностью

1. Используйте `wait_for_handlers=False` для некритичных событий
2. Оптимизируйте медленные обработчики
3. Проверьте статистику: `event_bus.get_stats()`

### Отладка

Включите debug логирование:

```python
import logging
logging.getLogger("app.events").setLevel(logging.DEBUG)
```

Проверьте статистику обработчиков:

```python
stats = event_bus.get_stats()
if stats.failed_handlers > 0:
    print(f"Обнаружены ошибки в обработчиках: {stats.failed_handlers}")
```

---

## БУДУЩИЕ УЛУЧШЕНИЯ

### Distributed Event Bus (Redis Pub/Sub)

Для горизонтального масштабирования через несколько инстансов:

```python
from app.events.distributed_event_bus import DistributedEventBus

# Инициализация с Redis
distributed_bus = DistributedEventBus(redis_url="redis://localhost:6379")
await distributed_bus.initialize()

# События теперь распределяются между всеми инстансами
await distributed_bus.publish(event, distribute=True)
```

### Event Store (PostgreSQL)

Для event sourcing и replay:

```python
# Все события сохраняются в БД
# Можно воспроизвести события для отладки или восстановления
events = await event_store.get_events(
    session_id="session-123",
    event_type=EventType.AGENT_SWITCHED
)

# Replay событий
for event in events:
    await event_bus.publish(event)
```

---

## СПРАВОЧНИК API

### EventBus

**Методы:**
- `subscribe(event_type, event_category, handler, priority)` - Подписаться на события
- `unsubscribe(event_type, event_category, handler)` - Отписаться
- `publish(event, wait_for_handlers)` - Опубликовать событие
- `add_middleware(middleware)` - Добавить middleware
- `get_stats()` - Получить статистику
- `clear()` - Очистить все подписки (для тестирования)

### BaseEvent

**Поля:**
- `event_id: str` - Уникальный ID
- `event_type: EventType` - Тип события
- `event_category: EventCategory` - Категория
- `timestamp: datetime` - Время создания
- `session_id: Optional[str]` - ID сессии
- `correlation_id: Optional[str]` - ID для трейсинга
- `causation_id: Optional[str]` - ID события-причины
- `data: Dict[str, Any]` - Данные события
- `source: str` - Компонент-источник
- `version: str` - Версия формата

### MetricsCollector

**Методы:**
- `get_metrics()` - Все метрики
- `get_agent_switch_count(from_agent, to_agent)` - Количество переключений
- `get_agent_avg_duration(agent)` - Средняя длительность обработки
- `get_tool_success_rate(tool_name)` - Процент успешных выполнений
- `reset_metrics()` - Сброс метрик

### AuditLogger

**Методы:**
- `get_audit_log(session_id, event_type, limit)` - Получить audit log
- `clear_audit_log()` - Очистить лог

---

## МИГРАЦИЯ

Подробный план миграции см. в [`doc/event-driven-architecture-proposal.md`](../../../../doc/event-driven-architecture-proposal.md)

### Текущий статус: Фаза 1 завершена ✅

- ✅ Базовая инфраструктура событий создана
- ✅ EventBus реализован и интегрирован
- ✅ Первые подписчики (MetricsCollector, AuditLogger) работают
- ✅ Unit тесты написаны
- ⏳ Следующая фаза: Параллельная публикация событий в существующем коде

---

## ПРИМЕРЫ ИЗ РЕАЛЬНОГО КОДА

### Пример 1: Переключение агента

```python
# В MultiAgentOrchestrator.process_message()
if chunk.type == "switch_agent":
    target_agent = AgentType(chunk.data["to_agent"])
    
    # Публикация события
    await event_bus.publish(
        AgentSwitchedEvent(
            session_id=session_id,
            from_agent=context.current_agent.value,
            to_agent=target_agent.value,
            reason=chunk.data.get("reason", ""),
            confidence=chunk.data.get("confidence"),
            correlation_id=correlation_id
        )
    )
    
    # Существующая логика
    context.switch_agent(target_agent, reason)
```

### Пример 2: Выполнение инструмента

```python
# В LLMStreamService.stream_response()
if tool_calls:
    tool_call = tool_calls[0]
    
    # Публикация события
    await event_bus.publish(
        ToolExecutionRequestedEvent(
            session_id=session_id,
            tool_name=tool_call.name,
            arguments=tool_call.arguments,
            call_id=tool_call.call_id,
            agent=current_agent.value,
            correlation_id=correlation_id
        )
    )
    
    # Проверка HITL
    if requires_approval:
        await event_bus.publish(
            ToolApprovalRequiredEvent(
                session_id=session_id,
                tool_name=tool_call.name,
                arguments=tool_call.arguments,
                call_id=tool_call.call_id,
                reason=approval_reason,
                correlation_id=correlation_id
            )
        )
```

### Пример 3: HITL решение

```python
# В endpoints.py при обработке hitl_decision
await event_bus.publish(
    HITLDecisionMadeEvent(
        session_id=session_id,
        call_id=tool_call_id,
        decision=decision,
        tool_name=pending.tool_name,
        original_args=pending.arguments,
        modified_args=modified_args,
        correlation_id=correlation_id
    )
)
```

---

## ЗАКЛЮЧЕНИЕ

Event-Driven Architecture обеспечивает:

✅ **Слабую связанность** - компоненты независимы  
✅ **Расширяемость** - легко добавлять новую функциональность  
✅ **Observability** - полная история всех действий  
✅ **Тестируемость** - легко писать и поддерживать тесты  
✅ **Готовность к масштабированию** - поддержка distributed events

**Текущий статус:** Фаза 1 реализована, система готова к параллельной публикации событий.

**Следующие шаги:** См. план миграции в основном proposal документе.

---

**Версия документа:** 1.0  
**Дата:** 17 января 2026  
**Автор:** На основе event-driven-architecture-proposal.md
