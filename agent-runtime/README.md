# Agent Runtime Service

Agent Runtime — отдельный микросервис (FastAPI), отвечающий за управление сессиями агента, стриминг сообщений между пользователем и LLM-прокси, хранение user/assistant истории. Используется внутри Codelab для посредничества между фронтом и языковыми моделями.

---

## Особенности и архитектура

- Строгая многоуровневая архитектура (API, сервисы, модели, middleware, core)
- Вся бизнес-логика инкапсулирована в сервисах (app/services)
- Типизированные Pydantic-модели истории, инструментов и протоколов (app/models)
- Внедрение зависимостей через единый провайдер (app/core/dependencies.py)
- In-memory session store с возможностью расширения до persistent
- Все external dependencies (LLM-прокси, инструменты и т.д.) строятся через DI (Dependency Injection)

---

### Основные файлы

- `app/main.py` — точка входа FastAPI
- `app/api/v1/endpoints.py` — API-роуты v1
- `app/core/` — конфиги, провайдеры зависимостей, базовые слои
- `app/core/dependencies.py` — все провайдеры DI (`get_chat_service`, `get_tool_registry`, и прочее)
- `app/models/` — центральное место моделей (Pydantic-схемы, message/history/tool-структуры)
- `app/services/` — бизнес-логика обработки сообщений, оркестрация, интеграции с LLM, tool registry и др.
- `app/middleware/` — Middleware, например, internal-auth
- `tests/` — тесты (unit, e2e)

---

## Быстрый старт

```bash
# Запуск через Docker Compose (+ пересборка при изменениях)
docker compose up -d --build

# Прогон тестов:
uv run pytest --maxfail=3 --disable-warnings -v tests
```

---

## API

- `GET /health` — Проверка статуса сервиса
- `POST /agent/message/stream` — Стриминговая обработка сообщения (SSE).

  Требуется заголовок авторизации:
  ```
  X-Internal-Auth: <INTERNAL_API_KEY>
  Content-Type: application/json
  ```
  Пример:
  ```bash
  curl -X POST 'http://localhost:8001/agent/message/stream' \
    -H 'Content-Type: application/json' \
    -H 'X-Internal-Auth: your-internal-key' \
    -d '{
      "session_id": "user-session-1",
      "role": "user",
      "content": "Your message here"
    }'
  ```
  SSE-ответ:
  ```
  data: {"token":"Hello, ","is_final":false,"type": "assistant_message"}
  data: {"token":"","is_final":true,"type": "assistant_message"}
  data: [DONE]
  ```

---

## Конфигурирование (ENV):

Все настройки через переменные окружения или `.env`-файл (пример в `.env.example`):

- `AGENT_RUNTIME__LLM_PROXY_URL`
- `AGENT_RUNTIME__LLM_MODEL`
- `AGENT_RUNTIME__INTERNAL_API_KEY`
- `AGENT_RUNTIME__LOG_LEVEL`
- `AGENT_RUNTIME__VERSION`
- ...[поддерживаются настройки OpenAI/vLLM — см. исходники]

---

## Как расширять

- **Добавлять сервисы и провайдеры** — логика только в `app/services/`, зависимости регистрируем через `app/core/dependencies.py`
- **Расширять модели** — все Pydantic-схемы в `app/models/`
- **Новые инструменты и их спецификации** — `app/services/tool_registry.py` и Pydantic-модели аргументов для строгой типизации
- **Переходить на production-стор хранилища** — меняем session_manager через DI

---

## Тестирование

```bash
uv run pytest tests
```
Unit- и e2e-тесты находятся в `tests/`. Всё DI легко мокается через core/dependencies.py.

---

## Контрибьюторам

- Соблюдайте DI-подход: любые Depends/инстанциаторы только через core/dependencies.py!
- Не добавляйте бизнес-логику в эндпойнты и роутеры.
- Для новых слоёв схемы или интеграций — заводите зависимости аналогично зарегистрированным.
- Документирование моделей и интеграций — непосредственно в docstring/пример модели.

---

© 2025 Codelab Contributors  
MIT License
