# Gateway Service

Gateway Service — современный асинхронный FastAPI-микросервис для защищённой коммуникации между IDE и Agent Runtime через WebSocket и REST API с поддержкой JWT аутентификации.

**Версия**: 1.0 (MVP)
**Дата обновления**: 11 января 2026
**Статус**: ✅ Production Ready

---

## Современная Архитектура

- **api/**
  - `v1/endpoints.py` — только thin-контроллеры (роутеры), без бизнес-логики
- **models/**
  - `websocket.py` — схемы сообщений WebSocket
  - `rest.py` — схемы REST-запросов и ответов
  - `tracking.py` — схемы для задач внутреннего трекинга
  - `schemas.py` — (устар.) re-export для совместимости
- **services/**
  - `session_manager.py` — асинхронный менеджер WebSocket-сессий (DI, thread-safe)
  - `tool_result_manager.py` — асинхронный менеджер ответов агентских tool calls (DI, thread-safe)
  - `token_buffer_manager.py` — асинхронный менеджер буферов токенов (DI, thread-safe)
  - `stream_service.py` — логика стрим-обмена между ws и agent-runtime
- **core/**
  - `dependencies.py` — провайдеры для DI (FastAPI Depends)
  - `config.py` — настройки окружения, логгер
- **middleware/** — авторизация внутренних API через internal auth

---

## Ключевые преимущества

- **Полное отсутствие глобальных переменных**
- **Dependency Injection** для всех менеджеров состояния (чистый DI через Depends)
- **Асинхронная thread-safe архитектура** (корректно работает в продакшен-режиме с несколькими воркерами)
- **Pydantic v2**, строгая типизация, единое определение моделей без дубликатов
- **Лаконичный, поддерживаемый код** в духе best practices FastAPI

---

## Установка и запуск

```bash
# Локальный запуск через Docker Compose:
docker compose up --build

# Локальный запуск разработки:
uvicorn app.main:app --reload
```

---

## Примеры API

### WebSocket (требует JWT)

- `WS /api/v1/ws/{session_id}` — основной endpoint для IDE

**Подключение:**
```javascript
const ws = new WebSocket('ws://localhost/api/v1/ws/session_123', {
  headers: {
    'Authorization': 'Bearer YOUR_JWT_TOKEN'
  }
});
```

**Отправка сообщения:**
```json
{
  "type": "user_message",
  "content": "Создай новый виджет",
  "role": "user"
}
```

**Получение ответов (streaming):**
```json
{"type": "assistant_message", "token": "Созд", "is_final": false}
{"type": "assistant_message", "token": "аю ", "is_final": false}
{"type": "assistant_message", "token": "виджет...", "is_final": true}
```

**Agent switching:**
```json
{"type": "agent_switched", "from_agent": "orchestrator", "to_agent": "coder", "reason": "Code implementation needed"}
```

**Tool calls:**
```json
{"type": "tool_call", "tool_name": "write_file", "call_id": "call_123", "arguments": {...}, "requires_approval": true}
```

### REST (Proxy endpoints)

- `GET /health` — статус сервиса
- `GET /api/v1/health` — API health check
- `GET /api/v1/agents` — список агентов (proxy к Agent Runtime)
- `GET /api/v1/agents/{session_id}/current` — текущий агент (proxy)
- `GET /api/v1/sessions/{session_id}/history` — история сессии (proxy)
- `GET /api/v1/sessions` — список сессий (proxy)
- `POST /api/v1/sessions` — создать сессию (proxy)
- `GET /api/v1/sessions/{session_id}/pending-approvals` — pending HITL approvals (proxy)

**Все proxy endpoints требуют JWT токен в заголовке Authorization.**

---

## Конфигурация через переменные .env

- `GATEWAY__INTERNAL_API_KEY` — сторонний сервис должен передавать этот ключ в заголовке
- `GATEWAY__AGENT_URL` — URL агент-сервиса
- `GATEWAY__REQUEST_TIMEOUT` — таймаут при взаимодействии с агентом

Все переменные перечислены в `.env.example`.

---

## Тестирование

```bash
pytest tests/
```

---

## Архитектурный подход

- Все состояния — thread-safe менеджеры, получаемые через Depends
- Весь бизнес- и session-state вынесен в сервисы, роуты только маршрутизируют
- Код поддерживает горизонтальное масштабирование (легко расширить менеджеры на Redis, если нужно persistence)
- Используется только строгий typing, не допускается дублирование моделей или логики

---

## License

MIT License © 2025 Codelab Contributors
