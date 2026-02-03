# Gateway Service Tests

Комплексный набор тестов для Gateway service после рефакторинга.

## Структура тестов

### Unit тесты (32 теста)

#### 1. [`test_agent_runtime_proxy.py`](test_agent_runtime_proxy.py) - 8 тестов
Тестирует [`AgentRuntimeProxy`](../app/services/agent_runtime_proxy.py) сервис.

**Покрытие:**
- ✅ GET запросы (успешные и с параметрами)
- ✅ POST запросы (успешные и с JSON данными)
- ✅ Обработка HTTP ошибок (404, 500)
- ✅ Обработка общих ошибок (connection errors)
- ✅ Обработка trailing slash в base_url

**Запуск:**
```bash
uv run pytest tests/test_agent_runtime_proxy.py -v
```

#### 2. [`test_message_parser.py`](test_message_parser.py) - 14 тестов
Тестирует [`WebSocketMessageParser`](../app/services/websocket/message_parser.py).

**Покрытие:**
- ✅ Парсинг всех типов сообщений: `user_message`, `tool_result`, `switch_agent`, `hitl_decision`, `plan_decision`
- ✅ Валидация обязательных полей
- ✅ Обработка ошибок (invalid JSON, unknown type, missing fields)
- ✅ Специальная обработка распространенных ошибок (call_id vs approval_request_id)

**Запуск:**
```bash
uv run pytest tests/test_message_parser.py -v
```

#### 3. [`test_config.py`](test_config.py) - 10 тестов
Тестирует [`AppConfig`](../app/core/config.py) с Pydantic Settings.

**Покрытие:**
- ✅ Значения по умолчанию
- ✅ Загрузка из environment variables
- ✅ Валидация таймаутов (min/max)
- ✅ Валидация log level
- ✅ Backward compatibility (uppercase properties)
- ✅ Case-insensitive env vars
- ✅ Boolean parsing
- ✅ Extra fields игнорируются

**Запуск:**
```bash
uv run pytest tests/test_config.py -v
```

---

### Интеграционные тесты (23 теста)

#### 4. [`test_websocket_integration.py`](test_websocket_integration.py) - 9 тестов
Тестирует полный WebSocket protocol flow.

**Покрытие:**
- ✅ `user_message` flow (streaming assistant_message)
- ✅ `tool_call` + `tool_result` flow
- ✅ `plan_approval_required` + `plan_decision` flow
- ✅ `hitl_decision` flow (HITL approval)
- ✅ `switch_agent` flow
- ✅ Обработка невалидных сообщений
- ✅ Обработка неизвестных типов
- ✅ Обработка ошибок от Agent Runtime
- ✅ Фильтрация null значений

**Запуск:**
```bash
uv run pytest tests/test_websocket_integration.py -v
```

#### 5. [`test_proxy_endpoints_integration.py`](test_proxy_endpoints_integration.py) - 14 тестов
Тестирует все REST proxy endpoints.

**Покрытие:**
- ✅ `GET /agents` - список агентов
- ✅ `GET /agents/{session_id}/current` - текущий агент
- ✅ `GET /sessions` - список сессий
- ✅ `POST /sessions` - создание сессии
- ✅ `GET /sessions/{session_id}/history` - история
- ✅ `GET /sessions/{session_id}/pending-approvals` - ожидающие одобрения
- ✅ `GET /events/metrics/session/{session_id}` - метрики сессии
- ✅ `GET /events/metrics/sessions` - список сессий с метриками
- ✅ `GET /events/metrics` - метрики событий
- ✅ `GET /events/audit-log` - аудит лог
- ✅ `GET /events/stats` - статистика Event Bus
- ✅ `GET /health` - health check
- ✅ Обработка HTTP ошибок (404)
- ✅ Обработка таймаутов

**Запуск:**
```bash
uv run pytest tests/test_proxy_endpoints_integration.py -v
```

---

## Запуск всех тестов

### Все тесты
```bash
cd codelab-ai-service/gateway
uv run pytest tests/ -v
```

**Результат:** 55 тестов, все проходят ✅

### С покрытием кода
```bash
uv run pytest tests/ --cov=app --cov-report=html
```

### Только unit тесты
```bash
uv run pytest tests/test_agent_runtime_proxy.py tests/test_message_parser.py tests/test_config.py -v
```

### Только интеграционные тесты
```bash
uv run pytest tests/test_websocket_integration.py tests/test_proxy_endpoints_integration.py -v
```

---

## Статистика тестов

| Категория | Файл | Тестов | Статус |
|-----------|------|--------|--------|
| **Unit** | test_agent_runtime_proxy.py | 8 | ✅ |
| **Unit** | test_message_parser.py | 14 | ✅ |
| **Unit** | test_config.py | 10 | ✅ |
| **Integration** | test_websocket_integration.py | 9 | ✅ |
| **Integration** | test_proxy_endpoints_integration.py | 14 | ✅ |
| **ИТОГО** | | **55** | **✅** |

---

## Покрытие компонентов

### Полностью покрыто тестами
- ✅ [`AgentRuntimeProxy`](../app/services/agent_runtime_proxy.py) - 8 unit тестов
- ✅ [`WebSocketMessageParser`](../app/services/websocket/message_parser.py) - 14 unit тестов
- ✅ [`AppConfig`](../app/core/config.py) - 10 unit тестов
- ✅ WebSocket protocol - 9 интеграционных тестов
- ✅ REST endpoints - 14 интеграционных тестов

### Частично покрыто
- ⚠️ [`SSEStreamHandler`](../app/services/websocket/sse_stream_handler.py) - покрыто через интеграционные тесты
- ⚠️ [`WebSocketHandler`](../app/services/websocket/websocket_handler.py) - покрыто через интеграционные тесты

### Рекомендации для дополнительного покрытия
- 📝 Добавить unit тесты для `SSEStreamHandler`
- 📝 Добавить unit тесты для `WebSocketHandler`
- 📝 Добавить тесты для middleware (internal_auth, jwt_auth)

---

## Гарантии тестов

### ✅ Протокол защищен
Интеграционные тесты гарантируют что:
- Все типы WebSocket сообщений обрабатываются корректно
- SSE события правильно пересылаются в IDE
- Null значения фильтруются
- Ошибки обрабатываются gracefully

### ✅ Рефакторинг безопасен
Unit тесты гарантируют что:
- AgentRuntimeProxy корректно проксирует запросы
- MessageParser валидирует все типы сообщений
- Config загружается и валидируется правильно
- Backward compatibility сохранена

### ✅ Качество кода
- Все тесты используют моки (не требуют запущенного сервера)
- Тесты изолированы друг от друга
- Понятные названия и документация
- Покрытие edge cases (ошибки, невалидные данные)

---

## CI/CD Integration

### GitHub Actions (пример)
```yaml
name: Gateway Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install uv
        run: pip install uv
      - name: Run tests
        run: |
          cd codelab-ai-service/gateway
          uv run pytest tests/ -v --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Troubleshooting

### Проблема: ModuleNotFoundError
**Решение:** Убедитесь что используете `uv run pytest` вместо просто `pytest`

### Проблема: Тесты падают с 401 Unauthorized
**Решение:** Используйте `auth_headers` fixture в тестах proxy endpoints

### Проблема: Pydantic deprecation warnings
**Решение:** Это warnings от старых моделей WebSocket, не влияют на работу

---

**Автор:** CodeLab Team  
**Дата:** 3 февраля 2026  
**Статус:** ✅ Все тесты проходят (55/55)
