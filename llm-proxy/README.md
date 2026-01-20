# LLM Proxy Service

LLM Proxy — микросервис для унификации доступа к различным языковым моделям (LLM) через единое API, реализующий защищённое взаимодействие для сервисов экосистемы CodeLab.

**Версия**: 1.0.0  
**Дата обновления**: 20 января 2026  
**Статус**: ✅ Production Ready

---

## Основные возможности

- ✅ **Единое REST API** для обращения к языковым моделям
- ✅ **SSE (Server-Sent Events)** для стриминговых ответов token-by-token
- ✅ **Защита эндпоинтов** через внутренний API-ключ (X-Internal-Auth)
- ✅ **Интеграция с LiteLLM proxy** для поддержки 100+ LLM провайдеров
- ✅ **Поддержка провайдеров**: OpenAI, Anthropic, Ollama, OpenRouter, DeepSeek, Qwen
- ✅ **Встроенные retry, fallback и rate limiting** через LiteLLM
- ✅ **Унифицированный формат** ответов (OpenAI-compatible)
- ✅ **Tool calling и function calling** для всех провайдеров
- ✅ **Локальные модели** через Ollama (приватность и экономия)

---

## Архитектура

LLM-Proxy использует LiteLLM как внешний прокси-сервис:

```
Клиент → LLM-Proxy → LiteLLM Proxy → LLM Провайдеры
                                      ├── OpenAI
                                      ├── Anthropic
                                      ├── Ollama
                                      ├── Azure OpenAI
                                      ├── OpenRouter
                                      └── и другие (100+)
```

### Преимущества архитектуры с LiteLLM

- ✅ Встроенные retry, fallback, rate limiting
- ✅ Поддержка 100+ провайдеров из коробки
- ✅ Независимое масштабирование LiteLLM proxy
- ✅ Упрощенная кодовая база llm-proxy
- ✅ Централизованное управление моделями и ключами

### Структура проекта

```
app/
├── main.py                          # Точка входа FastAPI
├── api/v1/endpoints.py             # API роутеры
├── models/schemas.py               # Pydantic схемы
├── services/
│   ├── llm_service.py              # Бизнес-логика LLM
│   └── llm_adapters/
│       ├── base.py                 # Базовый адаптер
│       ├── litellm_adapter.py      # LiteLLM адаптер
│       └── fake.py                 # Mock адаптер для тестов
├── middleware/
│   └── internal_auth.py            # Внутренняя авторизация
└── core/
    └── config.py                   # Конфигурация

tests/                              # Тесты
```

---

## Быстрый старт

### 1. Запуск LiteLLM Proxy (опционально)

Для использования с LiteLLM proxy:

```bash
# Установка LiteLLM
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
  master_key: "sk-1234"
```

### 2. Настройка переменных окружения

Создайте `.env` файл на основе `.env.example`:

```bash
# Режим работы
LLM_PROXY__LLM_MODE=litellm          # или mock для тестирования

# LiteLLM настройки
LLM_PROXY__LITELLM_PROXY_URL=http://localhost:4000
LLM_PROXY__LITELLM_API_KEY=sk-1234
LLM_PROXY__DEFAULT_MODEL=gpt-3.5-turbo

# Безопасность
LLM_PROXY__INTERNAL_API_KEY=change-me-internal-key

# Логирование
LLM_PROXY__LOG_LEVEL=INFO
```

### 3. Запуск LLM-Proxy

#### Через Docker Compose

```bash
# Запуск всех сервисов
docker compose up -d --build

# Просмотр логов
docker compose logs -f llm-proxy
```

#### Локальная разработка

```bash
# Установка зависимостей
cd llm-proxy
uv pip install -e .

# Запуск сервиса
uv run uvicorn app.main:app --reload --port 8002

# Запуск тестов
uv run pytest --maxfail=3 --disable-warnings -v tests
```

---

## API

### Endpoints

- `GET /health` — Проверка статуса сервиса
- `GET /v1/llm/models` — Список поддерживаемых языковых моделей
- `POST /v1/chat/completions` — Чат-комплишны с поддержкой SSE streaming

**Все защищённые эндпоинты требуют заголовка:**  
`X-Internal-Auth: <LLM_PROXY__INTERNAL_API_KEY>`

### Примеры запросов

#### Получить список моделей

```bash
curl -X GET 'http://localhost:8002/v1/llm/models' \
  -H 'Accept: application/json' \
  -H 'X-Internal-Auth: ${LLM_PROXY__INTERNAL_API_KEY}'
```

Ответ:
```json
{
  "models": [
    {
      "id": "gpt-3.5-turbo",
      "provider": "openai",
      "capabilities": ["chat", "streaming", "function_calling"]
    },
    {
      "id": "gpt-4",
      "provider": "openai",
      "capabilities": ["chat", "streaming", "function_calling"]
    }
  ]
}
```

#### Стриминговый чат-комплишн

```bash
curl -X POST 'http://localhost:8002/v1/chat/completions' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'X-Internal-Auth: ${LLM_PROXY__INTERNAL_API_KEY}' \
  -d '{
    "messages": [{"content": "Say hello!", "role": "user"}],
    "model": "gpt-4",
    "stream": true,
    "temperature": 1
  }'
```

SSE-ответ:
```
data: {"choices": [{"delta": {"content": "Hello"}}]}
data: {"choices": [{"delta": {"content": "!"}}]}
data: [DONE]
```

#### Не-стриминговый запрос

```bash
curl -X POST 'http://localhost:8002/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -H 'X-Internal-Auth: ${LLM_PROXY__INTERNAL_API_KEY}' \
  -d '{
    "messages": [{"content": "Say hello!", "role": "user"}],
    "model": "gpt-3.5-turbo",
    "stream": false
  }'
```

---

## Конфигурация

### Переменные окружения

Все переменные имеют префикс `LLM_PROXY__`:

#### Основные настройки

- `LLM_PROXY__LLM_MODE` — Режим работы: `litellm` (продакшен) или `mock` (тестирование)
- `LLM_PROXY__INTERNAL_API_KEY` — Ключ для внутренней авторизации
- `LLM_PROXY__LOG_LEVEL` — Уровень логирования (INFO/DEBUG)
- `LLM_PROXY__VERSION` — Версия сервиса

#### LiteLLM Proxy настройки

- `LLM_PROXY__LITELLM_PROXY_URL` — URL LiteLLM proxy (по умолчанию http://localhost:4000)
- `LLM_PROXY__LITELLM_API_KEY` — API-ключ для доступа к LiteLLM proxy
- `LLM_PROXY__DEFAULT_MODEL` — Модель по умолчанию (gpt-3.5-turbo)

#### Ограничения

- `LLM_PROXY__MAX_CONCURRENT_REQUESTS` — Максимум одновременных запросов
- `LLM_PROXY__REQUEST_TIMEOUT` — Таймаут запросов (секунды)

---

## Примеры конфигурации LiteLLM

### Базовая конфигурация

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
  
  # Ollama (локальный)
  - model_name: llama2
    litellm_params:
      model: ollama/llama2
      api_base: http://ollama:11434

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

---

## Интеграция с Ollama

Docker Compose включает сервис Ollama для запуска локальных моделей:

```bash
# Запуск всех сервисов включая Ollama
docker compose up -d

# Загрузка модели в Ollama
docker compose exec ollama ollama pull llama2

# Проверка доступных моделей
docker compose exec ollama ollama list
```

Пример конфигурации LiteLLM для Ollama:

```yaml
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
```

Использование:

```bash
curl -X POST 'http://localhost:8002/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -H 'X-Internal-Auth: ${LLM_PROXY__INTERNAL_API_KEY}' \
  -d '{
    "model": "llama2",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## Поддерживаемые провайдеры

Через LiteLLM поддерживается 100+ провайдеров:

- **OpenAI** - GPT-3.5, GPT-4, GPT-4 Turbo
- **Anthropic** - Claude 3 (Haiku, Sonnet, Opus)
- **Azure OpenAI** - Все модели OpenAI через Azure
- **Google** - Gemini, PaLM
- **Cohere** - Command, Command-R
- **Ollama** - Локальные модели (Llama, Mistral, и др.)
- **OpenRouter** - Доступ к множеству моделей
- **DeepSeek** - DeepSeek Coder
- **Qwen** - Qwen модели
- И многие другие...

Полный список: https://docs.litellm.ai/docs/providers

---

## Расширение

### Добавление нового адаптера LLM

1. Создайте класс в `services/llm_adapters/`
2. Наследуйтесь от `BaseLLMAdapter`
3. Реализуйте методы `chat_completion()` и `list_models()`
4. Зарегистрируйте в `llm_service.py`

### Добавление новой версии API

1. Создайте router в `api/v2/endpoints.py`
2. Определите новые схемы в `models/`
3. Подключите router в `main.py`

### Добавление middleware

1. Создайте middleware в `middleware/`
2. Добавьте в `main.py` через `app.add_middleware()`

---

## Тестирование

```bash
# Все тесты
uv run pytest tests

# С покрытием
uv run pytest tests --cov=app --cov-report=html

# Mock режим для тестов
LLM_PROXY__LLM_MODE=mock uv run pytest tests
```

---

## Мониторинг

### Логирование

Все запросы логируются с:
- Timestamp
- Request ID
- Model
- Tokens used
- Duration
- Status

### Метрики

- Количество запросов по моделям
- Использование токенов
- Время ответа
- Ошибки и таймауты

---

## Troubleshooting

### LiteLLM proxy недоступен

1. Проверьте, что LiteLLM proxy запущен
2. Убедитесь в правильности `LITELLM_PROXY_URL`
3. Проверьте логи LiteLLM

### Ошибки аутентификации

1. Проверьте `LITELLM_API_KEY`
2. Убедитесь, что ключи провайдеров корректны
3. Проверьте конфигурацию LiteLLM

### Медленные ответы

1. Проверьте производительность LiteLLM proxy
2. Убедитесь, что провайдер отвечает быстро
3. Проверьте сетевую задержку

---

## Документация

- [Главный README](../README.md)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [Технические требования](../doc/tech-req-llm-proxy-service.md)

---

## Контрибьюторам

- Все настройки через `core/config.py` и AppConfig
- Бизнес-логика только в сервисах
- Используйте адаптеры для разных провайдеров
- Пишите тесты для новой функциональности
- Документируйте изменения

---

© 2026 Codelab Contributors  
MIT License
