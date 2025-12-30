# План Рефакторинга LLM-Proxy для Использования LiteLLM Proxy

## Обзор

Необходимо заменить существующую систему адаптеров на использование внешнего LiteLLM proxy-сервера, который обеспечит унифицированный доступ ко всем LLM провайдерам с встроенными возможностями retry, fallback и rate limiting.

## Текущая Архитектура

- **Адаптеры**: BaseLLMAdapter, OpenAIAdapter, VLLMAdapter, FakeLLMAdapter
- **Маршрутизация**: get_llm_adapter() на основе LLM_MODE (mock/openai/vllm)
- **API**: /v1/chat/completions, /v1/llm/models
- **Зависимости**: openai>=1.3.5, anthropic>=0.7.4, tenacity>=8.2.3
- **Проблемы**: Несогласованные форматы ответов, отсутствие retry/fallback/rate limiting

## Целевая Архитектура

- **Внешний прокси**: LiteLLM работает как отдельный proxy-сервис
- **Единый адаптер**: LiteLLMAdapter, который перенаправляет запросы к LiteLLM proxy
- **Конфигурация**: LiteLLM proxy настраивается отдельно с поддержкой всех провайдеров
- **Встроенные возможности**: retry, fallback, rate limiting на уровне LiteLLM proxy
- **Поддержка провайдеров**: OpenAI, Anthropic, Azure, Gemini, vLLM, Ollama и другие через LiteLLM

---

## 1. Архитектурные Решения

### 1.1 Интеграция LiteLLM Proxy

- **Внешний сервис**: LiteLLM запускается как отдельный proxy-сервер (`litellm --proxy`)
- **Внутренний адаптер**: LiteLLMAdapter перенаправляет запросы к LiteLLM proxy endpoint
- **Конфигурация**: LiteLLM proxy настраивается через config.yaml или переменные окружения
- **Масштабируемость**: LiteLLM proxy можно масштабировать независимо

### 1.2 Изменения в Файловой Структуре

**Удаляемые файлы:**
- `app/services/llm_adapters/openai.py` (~148 строк)
- `app/services/llm_adapters/vllm.py` (~90 строк)

**Изменяемые файлы:**
- `app/services/llm_adapters/base.py` - возможно, небольшие корректировки
- `app/services/llm_adapters/fake.py` - сохранить для тестов, исправить баг с last_message
- `app/core/dependencies.py` - заменить логику выбора адаптера
- `app/core/config.py` - добавить URL для LiteLLM proxy
- `app/api/v1/endpoints.py` - без изменений (адаптер обеспечивает совместимость)
- `app/models/schemas.py` - без изменений
- `pyproject.toml` - добавить litellm зависимость

**Создаваемые файлы:**
- `app/services/llm_adapters/litellm_adapter.py` - новый адаптер для LiteLLM proxy
- `litellm_config.yaml` - конфигурация для LiteLLM proxy

### 1.3 Сохранение Обратной Совместимости

- API endpoints `/v1/chat/completions` и `/v1/llm/models` остаются без изменений
- Формат запросов ChatCompletionRequest остается совместимым
- Формат ответов ChatCompletionResponse/Chunk остается OpenAI-compatible

---

## 2. Конфигурация

### 2.1 Настройка LiteLLM Proxy

Создать `litellm_config.yaml`:

```yaml
model_list:
  - model_name: gpt-4o-mini
    litellm_params:
      model: gpt-4o-mini
      api_key: "sk-..."
  - model_name: gpt-3.5-turbo
    litellm_params:
      model: gpt-3.5-turbo
      api_key: "sk-..."
  - model_name: claude-3-haiku
    litellm_params:
      model: claude-3-haiku-20240307
      api_key: "sk-ant-..."
  - model_name: azure-gpt-4
    litellm_params:
      model: azure/gpt-4
      api_key: "azure-key"
      api_base: "https://resource.openai.azure.com/"
      api_version: "2024-02-15-preview"

general_settings:
  master_key: "sk-1234"  # API ключ для доступа к proxy
  database_url: "sqlite:///./litellm.db"  # для логов и rate limiting

router_settings:
  routing_strategy: "simple-shuffle"  # или "least-busy" для балансировки
  fallbacks:
    - gpt-4o-mini: ["gpt-3.5-turbo"]
    - claude-3-haiku: ["gpt-4o-mini"]
  retry_policy:
    max_retries: 3
    delay: 1.0
  rate_limit:
    rpm: 60
    tpm: 100000
```

### 2.2 Переменные Окружения для LLM-Proxy

```env
# URL для LiteLLM proxy
LLM_PROXY__LITELLM_PROXY_URL=http://localhost:4000

# API ключ для доступа к LiteLLM proxy
LLM_PROXY__LITELLM_API_KEY=sk-1234

# Основная модель (используется по умолчанию)
LLM_PROXY__DEFAULT_MODEL=gpt-4o-mini

# Для обратной совместимости с mock режимом
LLM_PROXY__LLM_MODE=mock  # mock | litellm
```

### 2.3 Запуск LiteLLM Proxy

```bash
# Установка
pip install litellm[proxy]

# Запуск с конфигом
litellm --config litellm_config.yaml --port 4000

# Или через переменные окружения
export LITELLM_MODEL_API_KEY="sk-..."
litellm --model gpt-4o-mini --port 4000
```

---

## 3. Изменения в Зависимостях

### 3.1 Добавляемые Зависимости

```toml
[project.dependencies]
# ... существующие ...
"litellm[proxy]>=1.40.0",  # для proxy функционала
"httpx>=0.25.1",          # для HTTP запросов к proxy (уже есть)
```

### 3.2 Удаляемые Зависимости

- `anthropic>=0.7.4` (будет доступен через LiteLLM proxy)
- `tenacity>=8.2.3` (retry обрабатывается LiteLLM proxy)

---

## 4. Изменения в Коде

### 4.1 Новый LiteLLMAdapter (`app/services/llm_adapters/litellm_adapter.py`)

```python
import logging
from typing import AsyncGenerator, Optional

import httpx
from openai import AsyncOpenAI

from app.core.config import AppConfig
from app.models.schemas import ChatCompletionRequest

from .base import BaseLLMAdapter

logger = logging.getLogger("llm-proxy.litellm_adapter")

class LiteLLMAdapter(BaseLLMAdapter):
    def __init__(self):
        self.proxy_url = AppConfig.LITELLM_PROXY_URL.rstrip("/")
        self.api_key = AppConfig.LITELLM_API_KEY
        self.default_model = AppConfig.DEFAULT_MODEL

        # OpenAI клиент для общения с LiteLLM proxy
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.proxy_url + "/v1"
        )

    async def get_models(self) -> list:
        try:
            models_resp = await self.client.models.list()
            models_list = []
            for model in models_resp.data:
                models_list.append({
                    "id": model.id,
                    "name": model.id,
                    "provider": "LiteLLM",  # или определить по префиксу
                    "context_length": 4096,  # упрощенное значение
                    "is_available": True,
                })
            logger.debug(f"[LiteLLMAdapter] Fetched models: {len(models_list)}")
            return models_list
        except Exception as e:
            logger.warning(f"[LiteLLMAdapter] Cannot fetch models: {e}")
            # Fallback
            return [{
                "id": self.default_model,
                "name": self.default_model,
                "provider": "LiteLLM",
                "context_length": 4096,
                "is_available": True,
            }]

    async def chat(self, request: ChatCompletionRequest):
        # Используем модель из запроса или по умолчанию
        model = request.model or self.default_model

        messages = [msg.model_dump(exclude_none=True) for msg in request.messages]

        params = {
            "model": model,
            "messages": messages,
            "stream": getattr(request, "stream", False),
        }

        # Дополнительные параметры
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.max_tokens is not None:
            params["max_tokens"] = request.max_tokens
        if getattr(request, "tools", None):
            params["tools"] = request.tools
        if getattr(request, "tool_choice", None):
            params["tool_choice"] = request.tool_choice

        if not params["stream"]:
            try:
                response = await self.client.chat.completions.create(**params)
                logger.debug(f"[LiteLLMAdapter] Response: {response.choices[0].message}")
                return response.choices[0].message.model_dump()
            except Exception as e:
                logger.error(f"[LiteLLMAdapter] Completion error: {e}")
                return f"[Error] LLM proxy unavailable: {e}"
        else:
            async def token_gen():
                try:
                    stream = await self.client.chat.completions.create(**params)
                    async for chunk in stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                except Exception as e:
                    logger.error(f"[LiteLLMAdapter] Streaming error: {e}")
                    yield f"[Error] LLM proxy stream unavailable: {e}"

            return token_gen()
```

### 4.2 Изменения в dependencies.py

```python
from app.core.config import AppConfig
from app.services.llm_adapters.litellm_adapter import LiteLLMAdapter
from app.services.llm_adapters.fake import FakeLLMAdapter


def get_llm_adapter():
    llm_mode = (getattr(AppConfig, "LLM_MODE", "litellm") or "litellm").lower()
    if llm_mode == "mock":
        return FakeLLMAdapter()
    return LiteLLMAdapter()
```

### 4.3 Изменения в config.py

```python
class AppConfig:
    INTERNAL_API_KEY: str = os.getenv("LLM_PROXY__INTERNAL_API_KEY", "change-me-internal-key")
    LOG_LEVEL: str = os.getenv("LLM_PROXY__LOG_LEVEL", "INFO")
    VERSION: str = os.getenv("LLM_PROXY__VERSION", "0.1.0")

    # LiteLLM proxy настройки
    LITELLM_PROXY_URL: str = os.getenv("LLM_PROXY__LITELLM_PROXY_URL", "http://localhost:4000")
    LITELLM_API_KEY: str = os.getenv("LLM_PROXY__LITELLM_API_KEY", "")
    DEFAULT_MODEL: str = os.getenv("LLM_PROXY__DEFAULT_MODEL", "gpt-4o-mini")

    # Для обратной совместимости
    LLM_MODE: str = os.getenv("LLM_PROXY__LLM_MODE", "litellm")  # mock | litellm
```

### 4.4 Исправление FakeLLMAdapter

```python
# В fake.py исправить строку 62
async def token_gen():
    words = "Mock LLM streaming response".split()  # вместо last_message
    for word in words:
        logger.debug(f"[FakeLLMAdapter][stream] yield token: {word}")
        yield word + " "
        await asyncio.sleep(0.2)
```

---

## 5. Миграция Функционала

### 5.1 Миграция Streaming

- **Текущий**: Разные реализации в каждом адаптере
- **Новый**: Единая реализация через LiteLLM proxy
- **Совместимость**: Сохраняется SSE формат ответов

### 5.2 Миграция Tool Calling / Function Calling

- **Текущий**: Прокидывание tools в OpenAI API
- **Новый**: LiteLLM proxy поддерживает tool calling для всех провайдеров
- **Совместимость**: Формат остается OpenAI-compatible

### 5.3 Миграция Получения Списка Моделей

- **Текущий**: Разные реализации для каждого провайдера
- **Новый**: Через `/v1/models` endpoint LiteLLM proxy
- **Совместимость**: Возвращает список в формате LLMModel

### 5.4 Сохранение FakeLLMAdapter для Тестов

- **Исправить баг**: Заменить `last_message` на фиксированный текст
- **Интеграция**: Через `LLM_MODE=mock`

---

## 6. Docker и Деплоймент

### 6.1 Обновление Dockerfile

Добавить установку litellm[proxy] и копирование конфига:

```dockerfile
# Добавить в Dockerfile
COPY litellm_config.yaml /app/litellm_config.yaml
RUN pip install litellm[proxy]
```

### 6.2 Docker Compose

Добавить сервис для LiteLLM proxy:

```yaml
services:
  llm-proxy:
    # ... существующий сервис

  litellm-proxy:
    image: ghcr.io/berriai/litellm:main-latest
    ports:
      - "4000:4000"
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
    command: ["--config", "/app/config.yaml", "--port", "4000"]
    environment:
      - LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - llm-proxy
```

---

## 7. Тестирование

### 7.1 Обновление Существующих Тестов

- `tests/test_main.py`: Обновить для работы с LiteLLMAdapter
- `tests/test_models.py`: Проверить получение списка моделей через proxy

### 7.2 Новые Тесты

**Интеграционные тесты:**
- `tests/test_litellm_proxy_integration.py`: Тесты с запущенным LiteLLM proxy
- `tests/test_fallback.py`: Тесты fallback через proxy
- `tests/test_rate_limiting.py`: Тесты rate limiting

### 7.3 Тестовая Конфигурация

```yaml
# litellm_config.test.yaml для тестов
model_list:
  - model_name: fake-model
    litellm_params:
      model: fake/fake-model
      api_key: "fake-key"

general_settings:
  master_key: "test-key"
  database_url: "sqlite:///./test.db"
```

---

## 8. Документация

### 8.1 README.md

**Добавить раздел "Архитектура с LiteLLM":**

```markdown
## Архитектура

LLM-Proxy теперь использует LiteLLM как внешний прокси-сервис:

```
Клиент → LLM-Proxy → LiteLLM Proxy → LLM Провайдеры
```

### Преимущества:
- Встроенные retry, fallback, rate limiting
- Поддержка 100+ провайдеров
- Независимое масштабирование
- Упрощенная кодовая база
```

**Раздел "Быстрый Старт":**

```markdown
## Быстрый Старт

1. **Запустите LiteLLM proxy:**
```bash
pip install litellm[proxy]
litellm --model gpt-4o-mini --port 4000
```

2. **Настройте переменные окружения:**
```env
LLM_PROXY__LITELLM_PROXY_URL=http://localhost:4000
LLM_PROXY__LITELLM_API_KEY=sk-1234
```

3. **Запустите LLM-Proxy:**
```bash
uvicorn app.main:app --reload
```
```

### 8.2 Конфигурационные Примеры

Создать `examples/` с примерами:

- `examples/basic.env` - базовая конфигурация
- `examples/multiprovider.env` - несколько провайдеров
- `examples/azure.env` - конфигурация для Azure
- `examples/production.env` - production настройки

---

## 9. План Реализации

### Этап 1: Настройка LiteLLM Proxy (1 день)
- [ ] Установить и настроить LiteLLM proxy локально
- [ ] Создать базовую конфигурацию
- [ ] Протестировать подключение разных провайдеров

### Этап 2: Имплементация LiteLLMAdapter (2 дня)
- [ ] Реализовать базовый адаптер
- [ ] Интегрировать с dependencies.py
- [ ] Тестировать базовые функции (chat, models)

### Этап 3: Миграция и Очистка (1 день)
- [ ] Удалить старые адаптеры
- [ ] Исправить FakeLLMAdapter
- [ ] Обновить зависимости

### Этап 4: Docker и Деплоймент (1 день)
- [ ] Обновить Docker конфигурацию
- [ ] Настроить docker-compose
- [ ] Протестировать интеграцию

### Этап 5: Тестирование и Документация (2 дня)
- [ ] Написать тесты
- [ ] Обновить документацию
- [ ] Создать примеры конфигурации

---

## 10. Риски и Митингация

### 10.1 Зависимость от Внешнего Сервиса

**Проблема:** LiteLLM proxy становится единой точкой отказа
- **Митингация:** Настроить health checks, monitoring
- **Fallback:** Сохранить возможность работы без proxy для критических случаев

### 10.2 Производительность

**Проблема:** Дополнительный hop через proxy
- **Митингация:** Оптимизировать конфигурацию LiteLLM, использовать HTTP/2
- **Мониторинг:** Отслеживать latency и throughput

### 10.3 Обновления LiteLLM

**Проблема:** Breaking changes в новых версиях
- **Митингация:** Использовать конкретные версии, тестировать обновления
- **Документация:** Отслеживать changelog и migration guides

---

## Заключение

Рефакторинг позволит:
- Сократить кодовую базу на ~300 строк
- Обеспечить поддержку 100+ LLM провайдеров через LiteLLM
- Добавить встроенные retry, fallback, rate limiting
- Упростить архитектуру за счет разделения ответственности
- Сохранить полную обратную совместимость API

План готов к реализации в Code режиме.