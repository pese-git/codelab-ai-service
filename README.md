# CodeLab AI Service

Микросервисная архитектура для AI-powered IDE с мультиагентной системой, предоставляющая унифицированный доступ к различным LLM провайдерам, OAuth2 аутентификацию и инструменты для работы с кодом.

**Версия**: 1.0.0  
**Дата обновления**: 20 января 2026  
**Статус**: ✅ Production Ready

---

## 🎯 Статус проекта

**Текущий этап:** ✅ MVP Завершен (Январь 2026)

**Реализованные возможности:**
- ✅ Мультиагентная система (5 специализированных агентов)
- ✅ Event-Driven Architecture
- ✅ Async database (PostgreSQL/SQLite)
- ✅ OAuth2 аутентификация
- ✅ HITL с database persistence
- ✅ Session persistence
- ✅ WebSocket + SSE streaming
- ✅ Nginx reverse proxy
- ✅ Поддержка множественных LLM провайдеров

---

## 🚀 Основные компоненты

### 🔒 Nginx Reverse Proxy
Единая точка входа для всех API запросов (порт 80):
- Маршрутизация между auth-service и gateway
- Поддержка WebSocket соединений
- Изоляция внутренних сервисов

**Маршрутизация:**
- `/oauth/*` → auth-service (OAuth2 endpoints)
- `/.well-known/*` → auth-service (JWKS endpoints)
- `/api/v1/*` → gateway (REST API)
- `/api/v1/ws/{session_id}` → gateway (WebSocket)

Подробная документация: [`nginx/README.md`](nginx/README.md)

### 🔐 Auth Service
OAuth2 аутентификация и авторизация:
- JWT токены (access и refresh)
- JWKS endpoints для публичных ключей
- Управление пользователями и сессиями
- Интеграция с Redis для хранения сессий

### 🌐 Gateway Service
WebSocket прокси между IDE и Agent Runtime:
- Real-time коммуникация через WebSocket
- Управление сессиями
- Маршрутизация сообщений
- JWT аутентификация

### 🤖 Agent Runtime Service
Основная AI логика с мультиагентной системой:
- **5 специализированных агентов:**
  - **Orchestrator** 🎭 - координатор и маршрутизатор
  - **Coder** 💻 - разработчик кода (полный доступ)
  - **Architect** 🏗️ - проектировщик (только .md файлы)
  - **Debug** 🐛 - отладчик (read-only режим)
  - **Ask** 💬 - консультант (минимальные инструменты)
- Event-Driven Architecture
- Session persistence
- HITL (Human-in-the-Loop)
- Tool registry (9 инструментов)

### 🔌 LLM Proxy Service
Унифицированный доступ к LLM провайдерам:
- Поддержка OpenAI, Anthropic, Ollama
- Потоковая передача ответов (SSE)
- Интеграция с LiteLLM
- Tool calling и function calling

### 💾 PostgreSQL
База данных для персистентности:
- Сессии и история сообщений
- Agent context
- HITL approvals
- Пользователи и OAuth токены

### ⚡ Redis
Кэш и хранилище сессий:
- OAuth сессии
- Rate limiting
- Кэширование

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

```bash
curl http://localhost/                  # Информация о доступных endpoints
curl http://localhost/nginx-health      # nginx proxy
curl http://localhost/auth-health       # auth-service
curl http://localhost/gateway-health    # gateway
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

### Запуск отдельного сервиса

```bash
# Agent Runtime
cd agent-runtime
uv run uvicorn app.main:app --reload --port 8001

# Gateway
cd gateway
uv run uvicorn app.main:app --reload --port 8000

# LLM Proxy
cd llm-proxy
uv run uvicorn app.main:app --reload --port 8002
```

### Тестирование

```bash
# Запуск тестов для конкретного сервиса
cd agent-runtime && uv run pytest tests
cd gateway && uv run pytest tests
cd llm-proxy && uv run pytest tests
```

### Code style

```bash
# Проверка кода
ruff check app/

# Автоматическое исправление
ruff check app/ --fix
```

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
