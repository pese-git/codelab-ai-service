# Gateway Service

Gateway Service — микросервис FastAPI, выступающий веб-шлюзом для websocket- и REST-коммуникации между пользователем и агентом. Обеспечивает защиту внутренних API, проксирование стриминговых сессий, буферизацию токенов.

## Основные возможности

- WebSocket-поддержка для потокового общения
- Буферизация генерируемых LLM токенов на сессию
- Защита эндпоинтов через Internal API Key
- Эффективное асинхронное проксирование между frontend и agent-runtime
- Применение единой scalable архитектуры (слои: api, models, services, middleware, core)

---

## Архитектура

- `app/main.py` — точка входа FastAPI, настройка middleware, роутеров
- `app/api/v1/endpoints.py` — эндпоинты REST и WebSocket (ws/{session_id})
- `app/models/schemas.py` — Pydantic-схемы сообщений, токенов, ошибок
- `app/services/stream_service.py` — логика sse/websocket буферизации и проксирования сообщений
- `app/middleware/internal_auth.py` — internal-auth middleware для API
- `app/core/config.py` — все переменные окружения и логгер

---

## Быстрый старт

```bash
# Запуск с пересборкой через Docker Compose
docker compose up -d --build

# Проверка e2e и unit тестов:
cd gateway
uv run pytest --maxfail=3 --disable-warnings -v tests
```

---

## API

- `GET /health` — Статус сервиса
- `WS /ws/{session_id}` — WebSocket endpoint для общения с LLM-агентом (live-stream + буферизация).
  
  ⚡️ Backend-интеграция: Gateway прозрачно проксирует потоковые сообщения на `/agent/message/stream` сервиса agent-runtime, который далее работает с `/v1/chat/completions` llm-proxy (SSE протокол, токенизация real-time).
  
  Все внутренние обращения защищены ключом `X-Internal-Auth`, который обязательно должен совпадать между сервисами (см. .env).

  - Сообщения клиента:
    ```json
    {
      "type": "user_message",
      "content": "привет, агент!"
    }
    ```
  - Стримовые ответы assistant (один токен за раз!):
    ```json
    {
      "type": "assistant_message",
      "token": "ответ LLM по токенам",
      "is_final": false
    }
    ```
    Финальное сообщение:
    ```json
    {
      "type": "assistant_message",
      "token": "",
      "is_final": true
    }
    ```
  - Пример ответа об ошибке:
    ```json
    {
      "type": "error",
      "content": "Invalid JSON message"
    }
    ```
  
  Пример подключения (JS):
  ```js
  const ws = new WebSocket('ws://localhost:8000/ws/demo-session');
  ws.onmessage = (e) => console.log(JSON.parse(e.data)); // токены приходят по частям
  ws.onopen = () => ws.send(JSON.stringify({type: "user_message", content: "Привет!"}));
  ```

---

## Конфигурация (env):

Все переменные окружения имеют префикс `GATEWAY__` для избежания конфликтов с другими сервисами.

- `GATEWAY__INTERNAL_API_KEY` — секрет для защиты внутренних ручек (обязательно синхронизировать с agent-runtime!)
  - Значение по умолчанию: `change-me-internal-key`
  - Рекомендуется: использовать сложный случайный ключ в production

- `GATEWAY__AGENT_URL` — URL к backend сервису agent-runtime
  - Значение по умолчанию: `http://localhost:8001`
  - Пример production: `http://agent-runtime:8001`

- `GATEWAY__REQUEST_TIMEOUT` — Таймаут на стрим-запросы в секундах
  - Значение по умолчанию: `30.0`
  - Рекомендуется: увеличить для длительных операций

- `GATEWAY__LOG_LEVEL` — уровень логирования
  - Значение по умолчанию: `DEBUG`
  - Доступные значения: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
  - Рекомендуется: `INFO` для production

- `GATEWAY__VERSION` — версия приложения
  - Значение по умолчанию: `0.1.0`
  - Формат: семантическое версионирование

Для локальной разработки скопируйте `.env.example` в `.env` и настройте необходимые значения:
```bash
cp .env.example .env
```

---

## Расширение

- Реализовать новые версии API — добавить router в `api/v2/endpoints.py`
- Расширить стрим-логику, добавить persistent storage — доработать сервис в `services/`
- Использование кастомных политик авторизации — через middleware
- Добавить поддержку доп. форматов сообщений и ошибок — модифицировать схемы в `models/`

---

## Тестирование

- Тесты разделены по слоям: api, buffer, e2e
- Запуск:  
  ```bash
  uv run pytest tests
  ```

---

## Authors & License

© 2025 Codelab Contributors  
MIT License
