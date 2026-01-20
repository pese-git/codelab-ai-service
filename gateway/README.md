# Gateway Service

Gateway Service — современный асинхронный FastAPI-микросервис для защищённой коммуникации между IDE и Agent Runtime через WebSocket и REST API с поддержкой JWT аутентификации.

**Версия**: 1.0.0  
**Дата обновления**: 20 января 2026  
**Статус**: ✅ Production Ready

---

## Современная Архитектура

### Структура проекта

```
app/
├── main.py                   # Точка входа FastAPI
├── api/v1/endpoints.py      # API роутеры (thin controllers)
├── models/                   # Pydantic схемы
│   ├── websocket.py         # WebSocket сообщения
│   ├── rest.py              # REST запросы/ответы
│   ├── tracking.py          # Внутренний трекинг
│   └── schemas.py           # Re-export для совместимости
├── services/                 # Бизнес-логика
│   ├── session_manager.py   # Менеджер WebSocket сессий
│   ├── stream_service.py    # Стриминг между WS и Agent Runtime
│   └── token_buffer_manager.py # Менеджер буферов токенов
├── core/                     # Конфигурация и DI
│   ├── config.py            # Настройки окружения
│   └── dependencies.py      # Провайдеры зависимостей
└── middleware/              # Middleware
    ├── internal_auth.py     # Внутренняя авторизация
    └── jwt_auth.py          # JWT аутентификация

tests/                       # Тесты
```

---

## Ключевые преимущества

- ✅ **Полное отсутствие глобальных переменных**
- ✅ **Dependency Injection** для всех менеджеров состояния
- ✅ **Асинхронная thread-safe архитектура**
- ✅ **Pydantic v2** с строгой типизацией
- ✅ **JWT аутентификация** для WebSocket и REST
- ✅ **Мультиагентная поддержка** (agent switching events)
- ✅ **Лаконичный, поддерживаемый код** в духе best practices FastAPI

---

## Установка и запуск

### Через Docker Compose

```bash
# Запуск всех сервисов
docker compose up -d --build

# Просмотр логов
docker compose logs -f gateway
```

### Локальная разработка

```bash
# Установка зависимостей
uv pip install -e .

# Запуск сервиса
uv run uvicorn app.main:app --reload --port 8000

# Запуск тестов
uv run pytest tests/
```

---

## API

### WebSocket

**Endpoint:** `WS /api/v1/ws/{session_id}`

**Требует:** JWT токен в заголовке Authorization

#### Подключение

```javascript
const ws = new WebSocket('ws://localhost/api/v1/ws/session_123', {
  headers: {
    'Authorization': 'Bearer YOUR_JWT_TOKEN'
  }
});
```

#### Типы сообщений

**От клиента к серверу:**

```json
// Пользовательское сообщение
{
  "type": "user_message",
  "content": "Создай новый виджет",
  "role": "user"
}

// Переключение агента
{
  "type": "switch_agent",
  "agent_type": "coder",
  "content": "Implement the feature"
}

// Результат выполнения инструмента
{
  "type": "tool_result",
  "call_id": "call_123",
  "result": "Success"
}

// HITL решение
{
  "type": "hitl_decision",
  "call_id": "call_123",
  "decision": "APPROVE"
}
```

**От сервера к клиенту:**

```json
// Стриминг ответа ассистента
{
  "type": "assistant_message",
  "token": "Creating ",
  "is_final": false
}

// Переключение агента
{
  "type": "agent_switched",
  "from_agent": "orchestrator",
  "to_agent": "coder",
  "reason": "Code implementation needed"
}

// Вызов инструмента
{
  "type": "tool_call",
  "tool_name": "write_file",
  "call_id": "call_123",
  "arguments": {...},
  "requires_approval": true
}

// Ошибка
{
  "type": "error",
  "error": "Error message"
}
```

---

### REST API (Proxy endpoints)

Все REST endpoints проксируют запросы к Agent Runtime.

**Требуют:** JWT токен в заголовке Authorization

#### Health & Info

- `GET /health` — Статус сервиса
- `GET /api/v1/health` — API health check

#### Agents

- `GET /api/v1/agents` — Список агентов
- `GET /api/v1/agents/{session_id}/current` — Текущий агент сессии

#### Sessions

- `GET /api/v1/sessions` — Список сессий
- `POST /api/v1/sessions` — Создать сессию
- `GET /api/v1/sessions/{session_id}/history` — История сессии
- `GET /api/v1/sessions/{session_id}/pending-approvals` — Pending HITL approvals

#### Примеры

```bash
# Получить список агентов
curl http://localhost/api/v1/agents \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Создать сессию
curl -X POST http://localhost/api/v1/sessions \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"

# Получить историю
curl http://localhost/api/v1/sessions/session_123/history \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Конфигурация через переменные .env

### Основные настройки

- `GATEWAY__INTERNAL_API_KEY` — Ключ для внутренней авторизации
- `GATEWAY__AGENT_URL` — URL Agent Runtime сервиса
- `GATEWAY__REQUEST_TIMEOUT` — Таймаут запросов к Agent Runtime
- `GATEWAY__LOG_LEVEL` — Уровень логирования (INFO/DEBUG)

### WebSocket настройки

- `GATEWAY__WS_HEARTBEAT_INTERVAL` — Интервал heartbeat (секунды)
- `GATEWAY__WS_CLOSE_TIMEOUT` — Таймаут закрытия соединения (секунды)
- `GATEWAY__MAX_CONCURRENT_REQUESTS` — Максимум одновременных запросов

### JWT аутентификация

- `GATEWAY__USE_JWT_AUTH` — Включить JWT аутентификацию (true/false)
- `GATEWAY__AUTH_SERVICE_URL` — URL Auth Service для проверки токенов

Все переменные перечислены в `.env.example`.

---

## Архитектурный подход

### Dependency Injection

Все состояния управляются через DI:

```python
from app.core.dependencies import (
    SessionManagerDep,
    StreamServiceDep,
    TokenBufferManagerDep
)

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    session_manager: SessionManagerDep,
    stream_service: StreamServiceDep
):
    # Использование зависимостей
    await session_manager.add_session(session_id, websocket)
```

### Thread-Safe менеджеры

Все менеджеры состояния thread-safe и поддерживают конкурентный доступ:

- **SessionManager** - управление WebSocket сессиями
- **TokenBufferManager** - буферизация токенов для стриминга
- **StreamService** - обработка стриминга между WS и Agent Runtime

### Масштабируемость

Код поддерживает горизонтальное масштабирование. Для persistence можно легко расширить менеджеры на Redis.

---

## Мультиагентная поддержка

Gateway полностью поддерживает мультиагентную систему Agent Runtime:

### Agent Switching

```javascript
// Запрос переключения агента
ws.send(JSON.stringify({
  type: "switch_agent",
  agent_type: "architect",
  content: "Design the authentication system"
}));

// Получение уведомления о переключении
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "agent_switched") {
    console.log(`Switched from ${data.from_agent} to ${data.to_agent}`);
    console.log(`Reason: ${data.reason}`);
  }
};
```

### Поддерживаемые агенты

- **orchestrator** 🎭 - Координатор
- **coder** 💻 - Разработчик
- **architect** 🏗️ - Архитектор
- **debug** 🐛 - Отладчик
- **ask** 💬 - Консультант

---

## Тестирование

```bash
# Все тесты
uv run pytest tests/

# С покрытием
uv run pytest tests/ --cov=app --cov-report=html

# Конкретный тест
uv run pytest tests/test_main.py -v
```

---

## Безопасность

### JWT Аутентификация

Gateway поддерживает JWT аутентификацию для WebSocket и REST API:

1. Клиент получает JWT токен от Auth Service
2. Токен передается в заголовке Authorization
3. Gateway проверяет токен через Auth Service JWKS endpoint
4. При успешной проверке разрешается доступ

### Внутренняя авторизация

Запросы к Agent Runtime защищены внутренним ключом (X-Internal-Auth).

---

## Мониторинг и логирование

### Structured Logging

Все логи структурированы и содержат:
- Timestamp
- Level
- Session ID
- Request ID
- Message

### Метрики

- Количество активных WebSocket соединений
- Количество обработанных сообщений
- Ошибки и таймауты
- Время обработки запросов

---

## Troubleshooting

### WebSocket не подключается

1. Проверьте JWT токен
2. Убедитесь, что Agent Runtime запущен
3. Проверьте логи Gateway

### Сообщения не доходят

1. Проверьте формат сообщений
2. Убедитесь, что session_id корректный
3. Проверьте логи на ошибки

### Медленный стриминг

1. Проверьте настройки буферизации
2. Убедитесь, что Agent Runtime отвечает быстро
3. Проверьте сетевую задержку

---

## Документация

- [WebSocket Protocol](../doc/websocket-protocol.md)
- [Мультиагентная система](../doc/MULTI_AGENT_README.md)
- [Главный README](../README.md)

---

## Контрибьюторам

- Все состояния через DI (никаких глобальных переменных)
- Бизнес-логика только в сервисах
- Роуты только маршрутизируют запросы
- Используйте строгую типизацию (Pydantic)
- Пишите тесты для новой функциональности

---

© 2026 Codelab Contributors  
MIT License
