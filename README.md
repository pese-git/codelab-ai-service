# CodeLab AI Service

Микросервисная архитектура для AI-powered IDE с мультиагентной системой, предоставляющая унифицированный доступ к различным LLM провайдерам, OAuth2 аутентификацию и инструменты для работы с кодом.

**Версия**: 1.0.0  
**Дата обновления**: 27 марта 2026  
**Статус**: ✅ Production Ready

---

## 🎯 Статус проекта

**Текущий этап:** ✅ MVP Завершен (Март 2026)

**Последние обновления (27 марта 2026):**
- ✅ codelab-auth-service (feat: PostgreSQL database initialization support)
- ✅ codelab-core-service (feat: RS256 JWT validation with JWKS integration)
- ✅ codelab-ai-service (chore: Docker infrastructure updates, submodule references)

**Реализованные возможности:**
- ✅ Мультиагентная система (5 специализированных агентов)
- ✅ Event-Driven Architecture
- ✅ Async database (PostgreSQL/SQLite)
- ✅ OAuth2 аутентификация с RS256 JWT и JWKS
- ✅ PostgreSQL database initialization
- ✅ HITL с database persistence
- ✅ Session persistence
- ✅ WebSocket + SSE streaming
- ✅ Nginx reverse proxy
- ✅ MailHog для email testing
- ✅ Поддержка множественных LLM провайдеров

---

## 🚀 Основные компоненты

### 🔒 Nginx Reverse Proxy
Единая точка входа для всех API запросов (порт 80):
- Маршрутизация между auth-service и core-service
- Поддержка WebSocket соединений
- Изоляция внутренних сервисов
- Управление HTTPS (в production)

**Маршрутизация:**
- `/oauth/*` → codelab-auth-service (OAuth2 endpoints)
- `/.well-known/*` → codelab-auth-service (JWKS endpoints)
- `/api/v1/*` → codelab-core-service (REST API)
- `/api/v1/ws/{session_id}` → codelab-core-service (WebSocket)

Подробная документация: [`nginx/README.md`](nginx/README.md)

### 🔐 Auth Service (codelab-auth-service)
OAuth2 аутентификация и авторизация:
- **JWT токены (access и refresh)** с RS256 алгоритмом
- **JWKS endpoints** для публичных ключей
- **Управление пользователями** и сессиями
- **Email подтверждение** (MailHog integration)
- **Интеграция с Redis** для хранения сессий
- **PostgreSQL** для персистентности (опционально)

### 🌐 Core Service (codelab-core-service)
Основной сервис с мультиагентной системой и REST API:
- **5 специализированных агентов:**
  - **Orchestrator** 🎭 - координатор и маршрутизатор
  - **Coder** 💻 - разработчик кода (полный доступ)
  - **Architect** 🏗️ - проектировщик (только .md файлы)
  - **Debug** 🐛 - отладчик (read-only режим)
  - **Ask** 💬 - консультант (минимальные инструменты)
- **Event-Driven Architecture**
- **Session persistence** с历史 сообщений
- **HITL** (Human-in-the-Loop) с database persistence
- **Tool registry** (9 инструментов)
- **WebSocket + SSE streaming** для real-time communication
- **RS256 JWT validation** с JWKS кэшированием
- **Qdrant vector database** для embedding storage и semantic search

### 🔌 LiteLLM Proxy
Унифицированный доступ к LLM провайдерам:
- Поддержка OpenAI, Anthropic, Ollama и других
- Потоковая передача ответов (SSE)
- Кэширование запросов через Redis
- **Langfuse интеграция** для наблюдаемости
- Tool calling и function calling
- Database хранилище моделей

### 💾 PostgreSQL
Центральная база данных для всех сервисов:
- **Auth Service**: пользователи, сессии, refresh токены
- **Core Service**: сессии, история сообщений, HITL approvals
- **LiteLLM**: конфигурация моделей и кэш
- **Langfuse**: хранилище traces и данных

### ⚡ Redis
Распределенный кэш и очереди сообщений:
- **OAuth сессии** (Session persistence)
- **Rate limiting** для API
- **Кэширование** LiteLLM запросов
- **Langfuse events queue**
- **Qdrant cache** (опционально)

### 🔍 Qdrant Vector Database
Хранилище embeddings для semantic search:
- **Agent context storage** с RAG интеграцией
- **Vector similarity search** для поиска похожих сессий
- **Namespace изоляция** по пользователям

### 📊 Langfuse (Observability Platform)
Полный стек наблюдаемости для LLM:
- **Langfuse Web** (порт 3001) - Web UI для трассировки
- **Langfuse Worker** (порт 3030) - фоновый обработчик
- **ClickHouse** - OLAP база для аналитики
- **MinIO S3** - хранилище медиа и экспортов
- Интеграция с LiteLLM для автоматического трекинга всех LLM запросов

### 📈 Monitoring Stack
Полный стек мониторинга и трассировки:
- **Prometheus** (порт 9090) - сбор метрик
- **Grafana** (порт 3000) - визуализация dashboard'ов
- **Jaeger** (порт 16686) - OpenTelemetry distributed tracing
- Интеграция со всеми сервисами для наблюдаемости

### 📧 MailHog
Email тестирование и отладка:
- **SMTP сервер** (порт 1025) для Auth Service
- **Web UI** (порт 8025) для просмотра отправленных писем
- Полезно для локальной разработки и тестирования email функциональности

---

## 📋 Требования

- Python 3.12+
- Docker и Docker Compose
- uv (быстрый Python package installer)

---

## 🛠 Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/pese-git/codelab-ai-service.git
cd codelab-ai-service
```

### 2. Установка uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Настройка переменных окружения

```bash
cp .env.example .env
```

Отредактируйте `.env` файл:
- Добавьте API ключи для LLM провайдеров
- Настройте внутренние ключи авторизации
- При необходимости измените порты

### 4. Запуск сервисов

```bash
docker compose up -d
```

Эта команда запустит все необходимые сервисы:

**Публичный сервис:**
- **nginx** (порт 80) - reverse proxy

**Сервисы за Nginx:**
- **auth-service** - OAuth2 аутентификация
- **gateway** - WebSocket прокси

**Внутренние сервисы:**
- **agent-runtime** - AI логика
- **llm-proxy** - доступ к LLM
- **postgres** - база данных
- **redis** - кэш

---

## 🔍 Проверка работоспособности

### Основные endpoints
```bash
# Nginx reverse proxy
curl http://localhost/nginx-health

# Auth Service (JWKS и health)
curl http://localhost/health
curl http://localhost/.well-known/jwks.json

# Core Service
curl http://localhost/api/v1/health
curl http://localhost/api/v1/agents

# Monitoring Dashboard'ы (только localhost)
curl http://localhost:3000/      # Grafana
curl http://localhost:16686/    # Jaeger
curl http://localhost:9090/     # Prometheus
curl http://localhost:3001/     # Langfuse Web UI
curl http://localhost:8025/     # MailHog Web UI
```

### Проверка сервисов через docker compose
```bash
# Статус всех сервисов
docker compose ps

# Проверка health статуса
docker compose ps --filter "status=healthy"

# Логи конкретного сервиса
docker compose logs -f codelab-core-service
docker compose logs -f codelab-auth-service
docker compose logs -f litellm
```

---

## 🔌 Примеры использования API

### OAuth2 аутентификация

```bash
# Получение токена
curl -X POST http://localhost/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=user&password=pass"

# Получение JWKS (публичные ключи)
curl http://localhost/.well-known/jwks.json
```

### WebSocket подключение

```javascript
const sessionId = 'my-session-id';
const ws = new WebSocket(`ws://localhost/api/v1/ws/${sessionId}`);

// Отправка сообщения
ws.send(JSON.stringify({
    type: "user_message",
    content: "Создай новый виджет"
}));

// Получение ответа
ws.onmessage = (event) => {
    const response = JSON.parse(event.data);
    console.log(response);
};
```

### REST API

```bash
# Создание сессии
curl -X POST http://localhost/api/v1/sessions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"

# Получение истории сессии
curl http://localhost/api/v1/sessions/{session_id}/history \
  -H "Authorization: Bearer YOUR_TOKEN"

# Список агентов
curl http://localhost/api/v1/agents \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🔑 Внутренняя авторизация между микросервисами

Все внутренние REST/SSE-запросы защищены ключами авторизации:
- Gateway: `GATEWAY__INTERNAL_API_KEY`
- Agent Runtime: `AGENT_RUNTIME__INTERNAL_API_KEY`
- LLM Proxy: `LLM_PROXY__INTERNAL_API_KEY`

Пример использования:

```bash
curl -X POST http://localhost:8001/agent/message/stream \
    -H "X-Internal-Auth: ${AGENT_RUNTIME__INTERNAL_API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{"session_id": "demo", "type": "user_message", "content": "Привет!"}'
```

---

## 🛠 Локальная разработка

### Требования для локальной разработки

```bash
# Python 3.12+
python --version

# uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Docker Desktop (для сервисов: PostgreSQL, Redis, Qdrant, etc)
docker --version
docker compose --version
```

### Запуск сервисов Docker для локальной разработки

```bash
# Запуск только необходимых сервисов (без самих микросервисов)
docker compose up -d postgres redis qdrant langfuse-web langfuse-worker litellm mailhog

# Проверка статуса
docker compose ps
```

### Запуск отдельного микросервиса локально

#### Core Service (основной сервис)
```bash
cd codelab-core-service

# Установка зависимостей
uv pip install -e ".[dev]"

# Запуск с hot reload (требует redis, postgres, qdrant, litellm)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# При первом запуске: инициализация БД
uv run python scripts/init_database.py
uv run alembic upgrade head
```

#### Auth Service
```bash
cd codelab-auth-service

# Установка зависимостей
uv pip install -e ".[dev]"

# Запуск с hot reload (требует redis, postgres опционально)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8003

# При первом запуске: инициализация БД
uv run python scripts/init_database.py
```

### Переменные окружения для локальной разработки

```bash
# codelab-core-service (.env)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/codelab
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
LITELLM_URL=http://localhost:4000
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://localhost:3001
LANGFUSE_PUBLIC_KEY=pk_defaultkey
LANGFUSE_SECRET_KEY=sk_defaultsecret
GATEWAY__AUTH_SERVICE_URL=http://localhost:8003
JWT_ALGORITHM=RS256
JWT_ISSUER=https://auth.codelab.local
JWT_AUDIENCE=codelab-api
AUTH_SERVICE_JWKS_URL=http://localhost:8003/.well-known/jwks.json
JWKS_CACHE_TTL=3600

# codelab-auth-service (.env)
PORT=8003
AUTH_SERVICE__DB_URL=sqlite:///data/auth.db
AUTH_SERVICE__REDIS_URL=redis://localhost:6379/1
AUTH_SERVICE__MASTER_KEY=your-secret-key
AUTH_SERVICE__JWT_ISSUER=https://auth.codelab.local
AUTH_SERVICE__JWT_AUDIENCE=codelab-api
AUTH_SERVICE__SMTP_HOST=localhost
AUTH_SERVICE__SMTP_PORT=1025
```

### Тестирование

```bash
# Запуск тестов для конкретного сервиса
cd codelab-core-service && uv run pytest tests -v
cd codelab-auth-service && uv run pytest tests -v

# Запуск с покрытием кода
uv run pytest tests --cov=app

# Запуск конкретного теста
uv run pytest tests/test_health_endpoints.py -v
```

### Code style и линтинг

```bash
# Проверка кода (Ruff)
uv run ruff check app/

# Автоматическое исправление
uv run ruff check app/ --fix

# Форматирование (Ruff format)
uv run ruff format app/

# Type checking (Pyright)
uv run pyright app/
```

### IDE-specific setup

#### VSCode
1. Установите расширение Python (ms-python.python)
2. Создайте `.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.fixAll": true
        }
    }
}
```

#### PyCharm
1. Установите интерпретатор: `python -m uv pip install -e .`
2. Настройте Run Configuration с параметром `--reload`

---

## 🔧 Управление зависимостями

Проект использует uv и pyproject.toml:

```bash
# Установка зависимостей
uv pip install -e .

# Обновление зависимостей
uv pip install -e . --upgrade

# Dev зависимости
uv pip install -e '.[dev]'
```

---

## 🧩 Архитектура

### Слоистая архитектура каждого сервиса

- **app/api/** - entrypoints FastAPI (REST/WebSocket)
- **app/models/** - Pydantic-схемы
- **app/services/** - бизнес-логика
- **app/middleware/** - авторизация, логирование
- **app/core/** - конфигурация, DI

### Мультиагентная система

```
User Message → Orchestrator → Специализированный Агент → LLM → Tools → Result
```

| Агент | Роль | Инструменты | Ограничения |
|-------|------|-------------|-------------|
| **Orchestrator** 🎭 | Координатор | read_file, list_files, search_in_code | Только анализ |
| **Coder** 💻 | Разработчик | Все (9 инструментов) | Нет |
| **Architect** 🏗️ | Архитектор | read_file, write_file, list_files, search_in_code | Только .md |
| **Debug** 🐛 | Отладчик | read_file, list_files, search_in_code, execute_command | Без write_file |
| **Ask** 💬 | Консультант | read_file, search_in_code, list_files | Только чтение |

---

## 📚 Документация

Подробная документация доступна в директории [`doc/`](doc/):

### Основная документация
- [CHANGELOG.md](CHANGELOG.md) - История изменений
- [Технические требования Gateway](doc/tech-req-gateway.md)
- [Технические требования Agent Runtime](doc/tech-req-agent-runtime-service.md)
- [Технические требования LLM Proxy](doc/tech-req-llm-proxy-service.md)

### Мультиагентная система
- [Обзор мультиагентной системы](doc/MULTI_AGENT_README.md)
- [Быстрый старт](doc/multi-agent-quick-start.md)
- [Архитектура и план](doc/multi-agent-architecture-plan.md)
- [Диаграммы](doc/multi-agent-architecture-diagram.md)

### Event-Driven Architecture
- [Руководство по Event-Driven Architecture](agent-runtime/doc/EVENT_DRIVEN_ARCHITECTURE.md)

### Документация сервисов
- [Nginx README](nginx/README.md)
- [Auth Service README](auth-service/README.md)
- [Gateway README](gateway/README.md)
- [Agent Runtime README](agent-runtime/README.md)
- [LLM Proxy README](llm-proxy/README.md)

### Протоколы
- [WebSocket Protocol](doc/websocket-protocol.md)
- [Agent Extended Protocol](doc/agent_extended_protocol.md)
- [HITL Implementation](doc/HITL_IMPLEMENTATION.md)

---

## 🔄 Управление сервисами

```bash
# Просмотр логов всех сервисов
docker compose logs -f

# Просмотр логов конкретного сервиса
docker compose logs -f gateway
docker compose logs -f agent-runtime

# Остановка всех сервисов
docker compose down

# Остановка с удалением volumes
docker compose down -v

# Перезапуск конкретного сервиса
docker compose restart gateway

# Пересборка и запуск после изменений
docker compose up -d --build
```

---

## 🤝 Участие в разработке

1. Fork репозитория
2. Создайте ветку для ваших изменений
3. Внесите изменения
4. Запустите тесты
5. Отправьте Pull Request

### Правила разработки

- Соблюдайте DI-подход через `core/dependencies.py`
- Не добавляйте бизнес-логику в эндпойнты
- Используйте строгую типизацию (Pydantic)
- Пишите тесты для новой функциональности
- Документируйте изменения в CHANGELOG.md

---

## 📝 Лицензия

MIT License - см. [LICENSE](LICENSE) файл для деталей.

---

## 🔗 Полезные ссылки

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

© 2026 CodeLab Contributors
