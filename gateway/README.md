# Gateway Service

Gateway Service — современный асинхронный FastAPI-микросервис для защищённой коммуникации между пользователем и LLM-агентом по WebSocket и REST API.

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

### WebSocket

- `WS /ws/{session_id}` — основной endpoint. Отправьте JSON:
  ```json
  {
    "type": "user_message",
    "content": "Привет агент!",
    "role": "user"
  }
  ```
  Ответы приходят по частям (streaming):
  ```json
  {"type": "assistant_message", "token": "Прив", "is_final": false}
  {"type": "assistant_message", "token": "ет!", "is_final": true}
  ```

### REST

- `GET /health` — статус сервиса

- `POST /tool/execute/{session_id}`  
  (service-to-service, только для доверенных сервисов: обязателен заголовок `X-Internal-Auth`!)

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
