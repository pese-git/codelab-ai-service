# Руководство по Retry механизму

## Обзор

Retry механизм с exponential backoff автоматически повторяет неудачные запросы к внешним сервисам (LLM Proxy) при временных ошибках.

## Возможности

✅ **Автоматический retry** на временных ошибках:
- Timeout (httpx.TimeoutException)
- Rate limiting (HTTP 429)
- Service unavailable (HTTP 503)
- Gateway timeout (HTTP 504)
- Connection errors

✅ **Exponential backoff**: 2s → 4s → 8s (максимум 10s)

✅ **Умное определение** retry/non-retry ошибок

✅ **Подробное логирование** всех попыток

## Использование

### 1. Автоматический retry в LLM Proxy Client

Retry уже встроен в [`llm_proxy_client.py`](app/services/llm_proxy_client.py:41):

```python
from app.services.llm_proxy_client import llm_proxy_client

# Автоматически повторяет при временных ошибках
response = await llm_proxy_client.chat_completion(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### 2. Использование декоратора для своих функций

```python
from app.services.retry_service import llm_retry

@llm_retry
async def my_external_call():
    # Ваш код, который может упасть с временной ошибкой
    response = await some_api_call()
    return response
```

### 3. Использование helper функции

```python
from app.services.retry_service import call_with_retry

async def my_function():
    return await some_api_call()

# Retry с кастомным количеством попыток
result = await call_with_retry(my_function, max_attempts=5)
```

### 4. Создание кастомного retry декоратора

```python
from app.services.retry_service import create_retry_decorator

# Более агрессивный retry для критичных операций
aggressive_retry = create_retry_decorator(
    max_attempts=5,
    min_wait=1.0,
    max_wait=30.0,
    multiplier=2.0
)

@aggressive_retry
async def critical_operation():
    # Ваш код
    pass
```

## Типы ошибок

### Retry ошибки (автоматически повторяются)

- `httpx.TimeoutException` - таймаут запроса
- `httpx.ConnectError` - ошибка подключения
- `httpx.ReadTimeout` - таймаут чтения
- HTTP 429 - rate limiting
- HTTP 503 - service unavailable
- HTTP 504 - gateway timeout

### Non-retry ошибки (не повторяются)

- HTTP 400 - bad request
- HTTP 401 - unauthorized
- HTTP 403 - forbidden
- HTTP 404 - not found
- HTTP 500 - internal server error
- Все остальные ошибки

## Логирование

Retry механизм логирует все попытки:

```
WARNING - Retrying llm_proxy_client.chat_completion in 2.0 seconds as it raised RetryableError: LLM request failed (retryable): Timeout
WARNING - Retrying llm_proxy_client.chat_completion in 4.0 seconds as it raised RetryableError: LLM request failed (retryable): Timeout
INFO - Received LLM response: status=200, choices=1
```

## Тестирование

### Автоматические тесты

```bash
cd codelab-ai-service/agent-runtime
uv run pytest tests/test_retry_service.py -v
```

### Ручное тестирование

```bash
cd codelab-ai-service/agent-runtime
uv run python test_retry_manual.py
```

Ручной тест демонстрирует:
- Успешный retry после нескольких попыток
- Исчерпание всех попыток
- Немедленный отказ на non-retry ошибках
- Различные типы retry ошибок

## Конфигурация

По умолчанию для LLM вызовов:
- **Максимум попыток**: 3
- **Минимальная задержка**: 2 секунды
- **Максимальная задержка**: 10 секунд
- **Множитель**: 1.0 (линейный backoff)

Задержки между попытками:
1. Первая попытка → немедленно
2. Вторая попытка → через 2 секунды
3. Третья попытка → через 4 секунды (если нужно)

## Примеры из логов

### Успешный retry

```
2026-01-14 09:29:21 - WARNING - Retrying in 2.0 seconds (timeout)
2026-01-14 09:29:23 - WARNING - Retrying in 2.0 seconds (timeout)
2026-01-14 09:29:25 - INFO - Request successful
```

### Non-retry ошибка

```
2026-01-14 09:29:31 - ERROR - Non-retryable error: Bad request (400)
```

## Интеграция с другими компонентами

Retry механизм интегрирован с:
- ✅ LLM Proxy Client
- 🔄 Circuit Breaker (планируется)
- 🔄 Metrics (планируется)

## Best Practices

1. **Используйте retry только для идемпотентных операций** - операции, которые можно безопасно повторять
2. **Не используйте retry для операций записи** без дополнительной логики дедупликации
3. **Мониторьте логи** - частые retry могут указывать на проблемы с внешним сервисом
4. **Настраивайте параметры** под конкретные сценарии использования

## Troubleshooting

### Слишком много retry попыток

Если видите много retry в логах:
1. Проверьте доступность LLM Proxy сервиса
2. Проверьте сетевое соединение
3. Увеличьте timeout для запросов
4. Рассмотрите использование Circuit Breaker

### Retry не срабатывает

1. Убедитесь, что ошибка относится к retry типу
2. Проверьте, что декоратор `@llm_retry` применен
3. Проверьте логи - должны быть WARNING сообщения

## Дальнейшие улучшения

Планируется:
- [ ] Интеграция с Circuit Breaker
- [ ] Метрики retry попыток в Prometheus
- [ ] Адаптивный backoff на основе нагрузки
- [ ] Jitter для предотвращения thundering herd

## См. также

- [`retry_service.py`](app/services/retry_service.py) - реализация
- [`llm_proxy_client.py`](app/services/llm_proxy_client.py) - использование
- [`test_retry_service.py`](tests/test_retry_service.py) - тесты
- [`test_retry_manual.py`](test_retry_manual.py) - ручное тестирование
