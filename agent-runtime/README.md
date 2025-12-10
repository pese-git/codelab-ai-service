# Agent Runtime Service

Agent Runtime — отдельный микросервис (FastAPI), отвечающий за управление сессиями агента, стриминг сообщений между пользователем и LLM-прокси, хранение user/assistant истории. Используется внутри Codelab для посредничества между фронтом и языковыми моделями.

## Основные возможности

- Обработка пользовательских сообщений с поддержкой сессий
- REST и SSE (Server-Sent Events) API для асинхронного ответа
- Проксирование LLM-запросов на сервис llm-proxy через внутренний API Key
- Расширяемая слоистая архитектура (api, services, models, middleware, core)
- In-memory session store (хранение истории в памяти сервиса)

---

## Архитектура

- `app/main.py` — точка входа, инициализация FastAPI, подключение middleware, роутеров
- `app/api/v1/endpoints.py` — единственный API v1 (легко расширять под будущие версии)
- `app/models/schemas.py` — Pydantic-схемы сообщений, токенов, health-check
- `app/services/llm_stream_service.py` — бизнес-логика стриминга и обработки сессий
- `app/middleware/internal_auth.py` — internal-auth для защиты эндпоинтов API
- `app/core/config.py` — централизованный доступ к переменным окружения/логгеру

---

## Быстрый старт

```bash
# Запуск через Docker Compose (+ пересборка при изменениях)
docker compose up -d --build

# Прогон всех автотестов:
cd agent-runtime
uv run pytest --maxfail=3 --disable-warnings -v tests
```

---

## API

- `GET /health` — Проверка статуса сервиса
- `POST /agent/message/stream` — Начать стриминговую сессию (SSE).
  
  Требуется заголовок:
  ```
  X-Internal-Auth: <INTERNAL_API_KEY>
  Content-Type: application/json
  ```
  
  Пример запроса:
  ```bash
  curl -X POST 'http://localhost:8001/agent/message/stream' \
    -H 'Content-Type: application/json' \
    -H 'X-Internal-Auth: your-internal-key' \
    -d '{
      "session_id": "user-session-1",
      "type": "user_message",
      "content": "Your message here"
    }'
  ```
  Потоковый SSE-ответ поступает порциями, пример:
  ```
  data: {"token":"Hello, ","is_final":false,"type": "assistant_message"}
  data: {"token":"world! ","is_final":false,"type": "assistant_message"}
  data: {"token":"","is_final":true,"type": "assistant_message"}
  data: [DONE]
  ```
  Используемый потоковый протокол полностью совместим с LLM-proxy и его актуальными endpoint'ами (`/v1/llm/models`, `/v1/chat/completions`).

---

## Конфигурирование (переменные окружения)

- `LLM_PROXY_URL` — URL сервиса llm-proxy (по умолчанию: http://localhost:8002)
- `INTERNAL_API_KEY` — секрет для авторизации запросов (по умолчанию: change-me-internal-key)
- `LOG_LEVEL` — уровень логирования (`INFO` по умолчанию)
- `VERSION` — версия (например, 0.1.0)

---

## Расширение

- Добавить новые endpoints — через `api/v1/endpoints.py` или добавить версию с новым роутером
- Вынести storage сессий — заменить in-memory sessions на persistent (Postgres, Redis и др.)
- Дополнить сервисы — реализовать вспомогательные функции в `services/`
- Править политики авторизации — через middleware

---

## Тестирование

- E2E и unit-тесты структурированы в папке `tests/`
- Запуск:  
```bash
uv run pytest tests
```

---

## Authors & License

© 2025 Codelab Contributors  
MIT License
