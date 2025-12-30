# LLM Proxy Service

LLM Proxy — микросервис для унификации доступа к различным языковым моделям (LLM), реализующий защищённое API для сервисов экосистемы. Является частью мультисервисной архитектуры Codelab.

## Основные возможности

- Единое REST API для обращения к языковым моделям
- SSE (Server-Sent Events) для стриминговых ответов token-by-token
- Защита эндпоинтов через внутренний API-ключ (middleware)
- Лёгкое масштабирование и расширяемость архитектуры за счёт слоёв (api, services, models, middleware)
- **Интеграция с LiteLLM proxy** для поддержки 100+ LLM провайдеров
- Встроенные retry, fallback и rate limiting через LiteLLM
- Унифицированный формат ответов (OpenAI-compatible)
- Поддержка tool calling и function calling

---

## Архитектура

LLM-Proxy теперь использует LiteLLM как внешний прокси-сервис:

```
Клиент → LLM-Proxy → LiteLLM Proxy → LLM Провайдеры (OpenAI, Anthropic, Azure, Gemini, vLLM, Ollama и др.)
```

### Преимущества архитектуры с LiteLLM:
- Встроенные retry, fallback, rate limiting
- Поддержка 100+ провайдеров из коробки
- Независимое масштабирование LiteLLM proxy
- Упрощенная кодовая база llm-proxy
- Централизованное управление моделями и ключами

### Структура проекта:
- `app/main.py` — точка входа, инициализация FastAPI и подключение маршрутов/слоёв/конфигов
- `app/api/v1/endpoints.py` — маршруты API (v1, легко расширить под v2)
- `app/models/schemas.py` — Pydantic-схемы входных и выходных данных
- `app/services/llm_service.py` — бизнес-логика взаимодействия с LLM (stream/fake, SSE)
- `app/services/llm_adapters/litellm_adapter.py` — адаптер для работы с LiteLLM proxy
- `app/services/llm_adapters/fake.py` — mock-адаптер для тестирования
- `app/middleware/internal_auth.py` — middleware с внутренней авторизацией
- `app/core/config.py` — централизованный доступ к переменным окружения и логированию

---

## Быстрый старт (разработка)

### 1. Запуск LiteLLM Proxy

Сначала необходимо запустить LiteLLM proxy сервер:

```bash
# Установка LiteLLM (если еще не установлен)
pip install 'litellm[proxy]'

# Запуск с базовой конфигурацией
litellm --model gpt-3.5-turbo --port 4000

# Или с конфигурационным файлом
litellm --config litellm_config.yaml --port 4000
```

Пример `litellm_config.yaml`:
```yaml
model_list:
  - model_name: gpt-3.5-turbo
    litellm_params:
      model: gpt-3.5-turbo
      api_key: "sk-..."
  - model_name: gpt-4
    litellm_params:
      model: gpt-4
      api_key: "sk-..."

general_settings:
  master_key: "sk-1234"  # API ключ для доступа к proxy
```

### 2. Настройка переменных окружения

Создайте `.env` файл на основе `.env.example`:
```bash
LLM_PROXY__LITELLM_PROXY_URL=http://localhost:4000
LLM_PROXY__LITELLM_API_KEY=sk-1234
LLM_PROXY__DEFAULT_MODEL=gpt-3.5-turbo
LLM_PROXY__LLM_MODE=litellm
```

### 3. Запуск LLM-Proxy

```bash
# Запуск с пересборкой через Docker Compose
docker compose up -d --build

# Или локально для разработки
cd llm-proxy
uv run uvicorn app.main:app --reload --port 8002

# Запуск всех автотестов для сервиса llm-proxy
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
- `LLM_PROXY__LLM_MODE` — режим работы: `litellm` (продакшен) или `mock` (тестирование)
- `LLM_PROXY__INTERNAL_API_KEY` — секретный приватный ключ для доступа к API (по умолчанию "change-me-internal-key")
- `LLM_PROXY__LOG_LEVEL` — уровень логирования (`INFO`/`DEBUG`/...)
- `LLM_PROXY__VERSION` — версия сервиса (по умолчанию "0.1.0")

### LiteLLM Proxy настройки:
- `LLM_PROXY__LITELLM_PROXY_URL` — URL LiteLLM proxy сервера (по умолчанию http://localhost:4000)
- `LLM_PROXY__LITELLM_API_KEY` — API-ключ для доступа к LiteLLM proxy (опционально)
- `LLM_PROXY__DEFAULT_MODEL` — модель по умолчанию (по умолчанию gpt-3.5-turbo)

---

## Примеры конфигурации LiteLLM

### Базовая конфигурация (один провайдер)

```yaml
# litellm_config.yaml
model_list:
  - model_name: gpt-3.5-turbo
    litellm_params:
      model: gpt-3.5-turbo
      api_key: "sk-..."

general_settings:
  master_key: "sk-1234"
```

### Мультипровайдерная конфигурация

```yaml
# litellm_config.yaml
model_list:
  # OpenAI
  - model_name: gpt-4
    litellm_params:
      model: gpt-4
      api_key: "sk-..."
  
  # Anthropic
  - model_name: claude-3-haiku
    litellm_params:
      model: claude-3-haiku-20240307
      api_key: "sk-ant-..."
  
  # Azure OpenAI
  - model_name: azure-gpt-4
    litellm_params:
      model: azure/gpt-4
      api_key: "azure-key"
      api_base: "https://resource.openai.azure.com/"
      api_version: "2024-02-15-preview"
  
  # vLLM (локальный)
  - model_name: local-llama
    litellm_params:
      model: openai/local-llama
      api_base: "http://localhost:8000/v1"

general_settings:
  master_key: "sk-1234"
  database_url: "sqlite:///./litellm.db"

router_settings:
  routing_strategy: "simple-shuffle"
  fallbacks:
    - gpt-4: ["gpt-3.5-turbo"]
    - claude-3-haiku: ["gpt-4"]
  retry_policy:
    max_retries: 3
    delay: 1.0
  rate_limit:
    rpm: 60
    tpm: 100000
```

### Запуск с конфигурацией

```bash
# Запуск LiteLLM proxy с конфигом
litellm --config litellm_config.yaml --port 4000

# Или через Docker
docker run -p 4000:4000 \
  -v $(pwd)/litellm_config.yaml:/app/config.yaml \
  ghcr.io/berriai/litellm:main-latest \
  --config /app/config.yaml --port 4000
```

### Интеграция с Ollama

Docker Compose включает сервис Ollama для запуска локальных моделей:

```bash
# Запуск всех сервисов включая Ollama
docker compose up -d

# Загрузка модели в Ollama
docker compose exec ollama ollama pull llama2

# Проверка доступных моделей
docker compose exec ollama ollama list
```

Пример конфигурации LiteLLM для работы с Ollama:

```yaml
# litellm_config.yaml
model_list:
  # Ollama модели
  - model_name: llama2
    litellm_params:
      model: ollama/llama2
      api_base: http://ollama:11434
  
  - model_name: mistral
    litellm_params:
      model: ollama/mistral
      api_base: http://ollama:11434
  
  # OpenAI модели
  - model_name: gpt-3.5-turbo
    litellm_params:
      model: gpt-3.5-turbo
      api_key: "sk-..."

general_settings:
  master_key: "sk-1234"
```

После настройки можно использовать локальные модели через LLM-Proxy:

```bash
curl -X POST 'http://localhost:8002/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -H 'x-internal-auth: ${LLM_PROXY__INTERNAL_API_KEY}' \
  -d '{
    "model": "llama2",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

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
