# LLM Proxy Service

LLM Proxy — микросервис для унификации доступа к различным языковым моделям (LLM), реализующий защищённое API для сервисов экосистемы. Является частью мультисервисной архитектуры Codelab.

## Основные возможности

- Единое REST API для обращения к языковым моделям
- SSE (Server-Sent Events) для стриминговых ответов token-by-token
- Защита эндпоинтов через внутренний API-ключ (middleware)
- Лёгкое масштабирование и расширяемость архитектуры за счёт слоёв (api, services, models, middleware)
- Поддержка нескольких провайдеров LLM: OpenAI, vLLM (локальные модели), Fake (для тестов)
- Унифицированный формат ответов
- Прозрачная маршрутизация на нужного провайдера

---

## Архитектура

- `app/main.py` — точка входа, инициализация FastAPI и подключение маршрутов/слоёв/конфигов
- `app/api/v1/endpoints.py` — маршруты API (v1, легко расширить под v2)
- `app/models/schemas.py` — Pydantic-схемы входных и выходных данных
- `app/services/llm_service.py` — бизнес-логика взаимодействия с LLM (stream/fake, SSE)
- `app/services/llm_adapters/*.py` — адаптеры для разных провайдеров (OpenAI, vLLM, Fake и др.)
- `app/middleware/internal_auth.py` — middleware с внутренней авторизацией
- `app/core/config.py` — централизованный доступ к переменным окружения и логированию

---

## Быстрый старт (разработка)

```bash
# Запуск с пересборкой через Docker Compose
docker compose up -d --build

# Запуск всех автотестов для сервиса llm-proxy
cd llm-proxy
uv run pytest --maxfail=3 --disable-warnings -v tests
```

## API

- `GET /health` — Проверка статуса сервиса
- `GET /v1/llm/models` — Список поддерживаемых языковых моделей
- `POST /v1/chat/completions` — Основная точка для чат-комплишнов, поддержка SSE (stream), temperature и пр.

> Все защищённые эндпоинты требуют заголовка:  
`x-internal-auth: <LLM_PROXY__INTERNAL_API_KEY>` (см. .env)

### Пример новых запросов

Получить список доступных LLM-моделей:
```bash
curl -X GET \
  'http://localhost:8002/v1/llm/models' \
  -H 'accept: application/json' \
  -H 'x-internal-auth: ${LLM_PROXY__INTERNAL_API_KEY}'
```

Стриминговый чат-комплишн — ответ идёт в формате Server-Sent Events (SSE):
```bash
curl -X POST 'http://localhost:8002/v1/chat/completions' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'x-internal-auth: ${LLM_PROXY__INTERNAL_API_KEY}' \
  -d '{
    "messages": [{"content": "Say hello!", "role": "user"}],
    "model": "gpt-4",
    "stream": true,
    "temperature": 1
  }'
```

SSE-ответ приходит порциями:
```
data: { ... chunk ... }
data: { ... chunk ... }
data: [DONE]
```


---

## Конфигурация (через переменные окружения)

Все переменные окружения имеют префикс `LLM_PROXY__` для предотвращения конфликтов в мультисервисной среде.

### Основные настройки:
- `LLM_PROXY__LLM_MODE` — используемый провайдер: `mock`, `openai`, `vllm`
- `LLM_PROXY__INTERNAL_API_KEY` — Cекретный приватный ключ для доступа к API (по умолчанию "change-me-internal-key", переопределяется в .env/docker-compose)
- `LLM_PROXY__LOG_LEVEL` — Уровень логирования (`INFO`/`DEBUG`/...)
- `LLM_PROXY__VERSION` — Версия сервиса (по умолчанию "0.1.0")

### OpenAI:
- `LLM_PROXY__OPENAI_API_KEY` — API-ключ OpenAI
- `LLM_PROXY__OPENAI_BASE_URL` — URL эндпоинта OpenAI API (по умолчанию https://api.openai.com/v1)

### vLLM (локальный сервер совместимый с OpenAI):
- `LLM_PROXY__VLLM_API_KEY` — (опционально) API-ключ для локального vLLM
- `LLM_PROXY__VLLM_BASE_URL` — URL эндпоинта vLLM (по умолчанию http://localhost:8000/v1)

---

## Пример запуска с vLLM

1. Запустите локальный vLLM сервер (инструкция — в доке vllm)
2. Укажите в .env:
   ```
   LLM_PROXY__LLM_MODE=vllm
   LLM_PROXY__VLLM_BASE_URL=http://localhost:8000/v1
   LLM_PROXY__VLLM_API_KEY=  # если нужен
   ```
3. Запустите сервис, как обычно — прокси будет использовать локальную модель вместо OpenAI

---

## Расширение

- Для добавления новых адаптеров LLM создайте класс в `services/llm_adapters/`
- Для поддержки новых версий API — создайте router в `api/v2/endpoints.py`
- Для внедрения нового способа авторизации/аудита — добавьте новый middleware в `middleware/`
- Все настройки и логи централизованы через `core/config.py` и AppConfig

---

## Тестирование

Тесты структурированы по слоям, запуск:
```bash
uv run pytest tests
```
или внутри контейнера.

---

## Authors & License

© 2025 Codelab Contributors  
MIT License
