# LLM Metrics - Quick Start

## Быстрый старт

### 1. Получить метрики сессии

```bash
curl -H "x-internal-auth: secret" \
  http://localhost:8001/events/metrics/session/YOUR_SESSION_ID
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
  "requests_with_tools": 8
}
```

### 2. Список всех сессий с метриками

```bash
curl -H "x-internal-auth: secret" \
  http://localhost:8001/events/metrics/sessions
```

### 3. Общие метрики

```bash
curl -H "x-internal-auth: secret" \
  http://localhost:8001/events/metrics
```

## Что отслеживается

✅ **Автоматически для каждого LLM запроса:**

- Длительность запроса (ms)
- Использование токенов (prompt/completion/total)
- Наличие tool calls
- Успешность/ошибки
- Модель LLM
- Timestamp

## Метрики по сессии

- **total_requests** - всего запросов
- **successful_requests** - успешных
- **failed_requests** - с ошибками
- **total_tokens** - всего токенов
- **average_duration_ms** - средняя длительность
- **average_tokens_per_request** - средние токены на запрос
- **requests_with_tools** - запросов с вызовом инструментов

## Примеры использования

### Мониторинг стоимости

```python
# GPT-4 цены (пример)
PROMPT_PRICE = 0.03  # $0.03 per 1K tokens
COMPLETION_PRICE = 0.06  # $0.06 per 1K tokens

def calculate_cost(metrics):
    prompt_cost = (metrics['total_prompt_tokens'] / 1000) * PROMPT_PRICE
    completion_cost = (metrics['total_completion_tokens'] / 1000) * COMPLETION_PRICE
    return prompt_cost + completion_cost
```

### Проверка производительности

```python
def check_performance(metrics):
    # Медленные запросы?
    if metrics['average_duration_ms'] > 5000:
        print("⚠️ Медленные запросы!")
    
    # Высокий процент ошибок?
    error_rate = metrics['failed_requests'] / metrics['total_requests']
    if error_rate > 0.1:
        print(f"⚠️ Ошибок: {error_rate*100:.1f}%")
```

### Анализ использования

```python
def analyze_usage(metrics):
    print(f"Всего запросов: {metrics['total_requests']}")
    print(f"Токенов: {metrics['total_tokens']}")
    print(f"С инструментами: {metrics['requests_with_tools']}")
    print(f"Средняя длительность: {metrics['average_duration_ms']}ms")
```

## Архитектура

```
LLM Request → Event Published → SessionMetricsCollector → API
     ↓              ↓                      ↓                ↓
  Started      Event Bus            Aggregation        Metrics
  Completed                         Per Session
  Failed
```

## События

1. **LLM_REQUEST_STARTED** - начало запроса
2. **LLM_REQUEST_COMPLETED** - успешное завершение
3. **LLM_REQUEST_FAILED** - ошибка

## Файлы

- [`app/events/llm_events.py`](../app/events/llm_events.py) - определения событий
- [`app/services/llm_stream_service.py`](../app/services/llm_stream_service.py) - публикация событий
- [`app/events/subscribers/session_metrics_collector.py`](../app/events/subscribers/session_metrics_collector.py) - сбор метрик
- [`app/api/v1/endpoints.py`](../app/api/v1/endpoints.py) - API endpoints

## Полная документация

См. [LLM_METRICS_IMPLEMENTATION.md](./LLM_METRICS_IMPLEMENTATION.md)

## Статус

✅ **ГОТОВО К ИСПОЛЬЗОВАНИЮ**

Версия: 0.3.0
