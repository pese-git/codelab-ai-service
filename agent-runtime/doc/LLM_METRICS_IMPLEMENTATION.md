# LLM Metrics Implementation - Полная реализация

## Обзор

Реализована полная система сбора метрик LLM запросов через Event-Driven Architecture. Система автоматически отслеживает все LLM запросы, собирает детальную статистику и предоставляет API для анализа.

## Архитектура

### 1. События LLM

**Файл:** [`app/events/llm_events.py`](../app/events/llm_events.py)

Три типа событий:

```python
# Начало LLM запроса
LLMRequestStartedEvent(
    session_id: str,
    model: str,
    messages_count: int,
    tools_count: int,
    correlation_id: Optional[str]
)

# Успешное завершение
LLMRequestCompletedEvent(
    session_id: str,
    model: str,
    duration_ms: int,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    has_tool_calls: bool,
    correlation_id: Optional[str]
)

# Ошибка
LLMRequestFailedEvent(
    session_id: str,
    model: str,
    error: str,
    correlation_id: Optional[str]
)
```

### 2. Публикация событий

**Файл:** [`app/services/llm_stream_service.py`](../app/services/llm_stream_service.py)

События публикуются автоматически при каждом LLM запросе:

```python
# Начало запроса
start_time = time.time()
await event_bus.publish(
    LLMRequestStartedEvent(
        session_id=session_id,
        model=AppConfig.LLM_MODEL,
        messages_count=len(history),
        tools_count=len(tools_to_use),
        correlation_id=correlation_id
    )
)

# Вызов LLM
response_data = await llm_proxy_client.chat_completion(...)
duration_ms = int((time.time() - start_time) * 1000)

# Успешное завершение
await event_bus.publish(
    LLMRequestCompletedEvent(
        session_id=session_id,
        model=AppConfig.LLM_MODEL,
        duration_ms=duration_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        has_tool_calls=has_tool_calls,
        correlation_id=correlation_id
    )
)
```

### 3. SessionMetricsCollector

**Файл:** [`app/events/subscribers/session_metrics_collector.py`](../app/events/subscribers/session_metrics_collector.py)

Подписчик собирает метрики по сессиям:

**Возможности:**
- Отслеживание всех LLM запросов по сессиям
- Агрегация метрик (токены, длительность, успешность)
- Детальная история запросов
- Вычисление средних значений

**Структура данных:**

```python
@dataclass
class SessionMetrics:
    session_id: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_duration_ms: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    requests_with_tools: int
    requests: List[LLMRequestMetrics]
```

## API Endpoints

### 1. Метрики конкретной сессии

```bash
GET /events/metrics/session/{session_id}
```

**Ответ:**
```json
{
  "session_id": "abc-123",
  "total_requests": 15,
  "successful_requests": 14,
  "failed_requests": 1,
  "total_duration_ms": 45000,
  "average_duration_ms": 3214.29,
  "total_prompt_tokens": 12500,
  "total_completion_tokens": 8300,
  "total_tokens": 20800,
  "average_tokens_per_request": 1485.71,
  "requests_with_tools": 8,
  "requests": [
    {
      "timestamp": "2026-01-17T15:30:00Z",
      "model": "gpt-4",
      "duration_ms": 3200,
      "prompt_tokens": 850,
      "completion_tokens": 420,
      "total_tokens": 1270,
      "has_tool_calls": true,
      "success": true,
      "error": null
    }
  ]
}
```

### 2. Список всех сессий с метриками

```bash
GET /events/metrics/sessions
```

**Ответ:**
```json
{
  "sessions": ["session-1", "session-2", "session-3"],
  "count": 3
}
```

### 3. Общие метрики событий (существующий)

```bash
GET /events/metrics
```

Возвращает метрики по всем событиям, включая агенты, инструменты, HITL.

## Использование

### Пример 1: Мониторинг активной сессии

```python
import httpx

async def monitor_session(session_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8001/events/metrics/session/{session_id}",
            headers={"x-internal-auth": "secret"}
        )
        metrics = response.json()
        
        print(f"Сессия: {metrics['session_id']}")
        print(f"Запросов: {metrics['total_requests']}")
        print(f"Токенов: {metrics['total_tokens']}")
        print(f"Средняя длительность: {metrics['average_duration_ms']}ms")
```

### Пример 2: Анализ стоимости

```python
# Цены за 1K токенов (пример для GPT-4)
PROMPT_PRICE = 0.03  # $0.03 per 1K tokens
COMPLETION_PRICE = 0.06  # $0.06 per 1K tokens

def calculate_cost(metrics: dict) -> float:
    prompt_cost = (metrics['total_prompt_tokens'] / 1000) * PROMPT_PRICE
    completion_cost = (metrics['total_completion_tokens'] / 1000) * COMPLETION_PRICE
    return prompt_cost + completion_cost

# Получить метрики
metrics = await get_session_metrics(session_id)
cost = calculate_cost(metrics)
print(f"Стоимость сессии: ${cost:.4f}")
```

### Пример 3: Мониторинг производительности

```python
async def check_performance(session_id: str):
    metrics = await get_session_metrics(session_id)
    
    # Проверка средней длительности
    if metrics['average_duration_ms'] > 5000:
        print("⚠️ Медленные запросы!")
    
    # Проверка ошибок
    error_rate = metrics['failed_requests'] / metrics['total_requests']
    if error_rate > 0.1:
        print(f"⚠️ Высокий процент ошибок: {error_rate*100:.1f}%")
    
    # Проверка использования токенов
    if metrics['average_tokens_per_request'] > 2000:
        print("⚠️ Высокое потребление токенов!")
```

## Интеграция

### Инициализация

Подписчик автоматически инициализируется в [`app/main.py`](../app/main.py):

```python
from app.events.subscribers import session_metrics_collector

# При старте приложения
await session_metrics_collector.start()
```

### Очистка метрик

```python
from app.events.subscribers import session_metrics_collector

# Очистить метрики конкретной сессии
session_metrics_collector.clear_session_metrics(session_id)
```

## Метрики в реальном времени

События публикуются синхронно с LLM запросами:

1. **LLM_REQUEST_STARTED** - сразу перед вызовом LLM
2. **LLM_REQUEST_COMPLETED** - сразу после получения ответа
3. **LLM_REQUEST_FAILED** - при любой ошибке

Это позволяет:
- Отслеживать активные запросы
- Вычислять точную длительность
- Собирать статистику в реальном времени

## Расширение

### Добавление новых метрик

1. Расширить `LLMRequestMetrics`:

```python
@dataclass
class LLMRequestMetrics:
    # ... существующие поля
    cache_hit: bool = False  # новое поле
    response_quality_score: float = 0.0
```

2. Обновить события для передачи данных

3. Обновить `to_dict()` для API

### Добавление аналитики

```python
class SessionMetricsCollector:
    def get_token_efficiency(self, session_id: str) -> float:
        """Вычислить эффективность использования токенов."""
        metrics = self.get_session_metrics(session_id)
        if not metrics:
            return 0.0
        
        # Соотношение completion/prompt
        return metrics.total_completion_tokens / max(metrics.total_prompt_tokens, 1)
```

## Производительность

- **Overhead:** Минимальный (~1-2ms на событие)
- **Память:** O(n) где n = количество запросов
- **Потокобезопасность:** Да (async/await)

## Мониторинг

### Проверка работы

```bash
# Получить статистику Event Bus
curl -H "x-internal-auth: secret" \
  http://localhost:8001/events/stats

# Проверить метрики сессии
curl -H "x-internal-auth: secret" \
  http://localhost:8001/events/metrics/session/YOUR_SESSION_ID
```

### Логирование

События логируются на уровне INFO:

```
INFO - LLM request started for session abc-123
INFO - LLM request completed for session abc-123: 3200ms, 1270 tokens
INFO - Session abc-123 metrics updated: 15 requests, 20800 tokens
```

## Связанные документы

- [Event-Driven Architecture](./EVENT_DRIVEN_ARCHITECTURE.md)
- [Metrics Collection Guide](./METRICS_COLLECTION_GUIDE.md)
- [Session Metrics Proposal](./SESSION_METRICS_PROPOSAL.md)
- [Event-Driven Coverage Analysis](./EVENT_DRIVEN_COVERAGE_ANALYSIS.md)

## Статус

✅ **ПОЛНОСТЬЮ РЕАЛИЗОВАНО**

- ✅ LLM события (started/completed/failed)
- ✅ Публикация из llm_stream_service
- ✅ SessionMetricsCollector подписчик
- ✅ API endpoints для метрик
- ✅ Агрегация и вычисления
- ✅ Документация

## Версия

**Версия:** 0.3.0  
**Дата:** 2026-01-17  
**Автор:** Agent Runtime Team
