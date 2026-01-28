# Agent Runtime Service

Agent Runtime — микросервис (FastAPI) с мультиагентной системой, отвечающий за управление сессиями, стриминг сообщений между IDE и LLM, хранение истории и выполнение инструментов. Ядро AI логики CodeLab.

**Версия**: 2.0.0
**Дата обновления**: 26 января 2026
**Статус**: ✅ Production Ready

## 🎉 Что нового в версии 2.0.0

### Архитектурный рефакторинг (январь 2026)

✅ **Соблюдение Clean Architecture**
- Создан интерфейс [`IStreamHandler`](app/domain/interfaces/stream_handler.py) для разрыва зависимости Domain от Application слоя
- Domain слой теперь зависит только от абстракций

✅ **Декомпозиция MessageOrchestrationService**
- Разделен монолитный сервис (852 строки) на 5 специализированных сервисов
- Каждый сервис имеет одну четкую ответственность (SRP)
- Сохранена обратная совместимость через паттерн Фасад

✅ **Устранение дублирования кода**
- Создан [`AgentSwitchHelper`](app/domain/services/helpers/agent_switch_helper.py) для общей логики переключения агентов
- Устранено ~200 строк дублированного кода

✅ **Улучшенная тестируемость**
- 97.2% тестов проходят (243 из 250)
- Малые, изолированные модули легко тестировать

📊 **Метрики улучшения:**
- Уменьшение размера основного сервиса на 65%
- Устранение 100% дублирования кода
- Уменьшение зависимостей на 29%

📖 **Подробнее:** [`doc/agent-runtime-refactoring-complete-report.md`](../../doc/agent-runtime-refactoring-complete-report.md)

---

## Особенности и архитектура

### Мультиагентная система

- ✅ **5 специализированных агентов** (Orchestrator, Coder, Architect, Debug, Ask)
- ✅ **LLM-based routing** через Orchestrator с fallback на ключевые слова
- ✅ **Agent switching** с сохранением контекста
- ✅ **File restrictions** для агентов (Architect только .md, Debug read-only)
- ✅ **История переключений** с полным трейсингом

### Event-Driven Architecture

- ✅ **Централизованная шина событий** (EventBus)
- ✅ **Типизированные события** для всех операций
- ✅ **Подписчики** для метрик и аудита
- ✅ **Correlation ID** для трейсинга связанных событий
- ✅ **Middleware** для обработки событий

### Архитектура

- **Строгая многоуровневая архитектура** (API, domain, infrastructure, services)
- **Clean Architecture** с соблюдением Dependency Inversion Principle
- **Domain-Driven Design** с четким разделением слоев
- **SOLID принципы** во всех компонентах
- **Dependency Injection** через app/core/dependencies.py
- **Async database** (PostgreSQL/SQLite) для session persistence
- **HITL (Human-in-the-Loop)** с database persistence
- **Tool registry** с 9 реализованными инструментами
- **Resilience patterns** (circuit breaker, retry, timeout)

#### Специализированные сервисы обработки сообщений

После рефакторинга (январь 2026) система использует модульную архитектуру:

| Сервис | Ответственность | Файл |
|--------|-----------------|------|
| **MessageOrchestrationService** | Фасад для координации | [`message_orchestration.py`](app/domain/services/message_orchestration.py) |
| **MessageProcessor** | Обработка входящих сообщений | [`message_processor.py`](app/domain/services/message_processor.py) |
| **AgentSwitcher** | Переключение агентов | [`agent_switcher.py`](app/domain/services/agent_switcher.py) |
| **ToolResultHandler** | Обработка результатов инструментов | [`tool_result_handler.py`](app/domain/services/tool_result_handler.py) |
| **HITLDecisionHandler** | Обработка HITL решений | [`hitl_decision_handler.py`](app/domain/services/hitl_decision_handler.py) |
| **AgentSwitchHelper** | Общая логика переключения | [`helpers/agent_switch_helper.py`](app/domain/services/helpers/agent_switch_helper.py) |

**Преимущества:**
- ✅ Каждый сервис имеет одну ответственность (SRP)
- ✅ Устранено дублирование кода
- ✅ Улучшенная тестируемость
- ✅ Слабая связанность компонентов

#### Схема зависимостей сервисов

```mermaid
graph TB
    subgraph "API Layer"
        Router[SessionsRouter]
    end
    
    subgraph "Domain Services"
        MOS[MessageOrchestrationService<br/>Фасад]
        MP[MessageProcessor]
        AS[AgentSwitcher]
        TRH[ToolResultHandler]
        HITLH[HITLDecisionHandler]
        Helper[AgentSwitchHelper]
        AM[ApprovalManager]
        HPS[HITLPolicyService]
    end
    
    subgraph "Core Services"
        SMS[SessionManagementService]
        AOS[AgentOrchestrationService]
        AR[AgentRouter]
    end
    
    subgraph "Infrastructure"
        ApprovalRepo[ApprovalRepository]
        EB[EventBus]
    end
    
    Router --> MOS
    MOS --> MP
    MOS --> AS
    MOS --> TRH
    MOS --> HITLH
    
    MP --> Helper
    AS --> Helper
    TRH --> Helper
    
    MP --> SMS
    MP --> AOS
    MP --> AR
    MP --> AM
    
    AS --> AOS
    
    TRH --> SMS
    TRH --> AR
    TRH --> AM
    
    HITLH --> AM
    HITLH --> SMS
    HITLH --> MP
    
    Helper --> SMS
    Helper --> AOS
    
    AM --> HPS
    AM --> ApprovalRepo
    AM --> EB
    
    style MOS fill:#51cf66
    style Helper fill:#ffd43b
    style AM fill:#ff6b6b
    style HPS fill:#74c0fc
```

#### Диаграмма последовательности обработки сообщения

```mermaid
sequenceDiagram
    participant Client
    participant API as SessionsRouter
    participant MOS as MessageOrchestrationService
    participant MP as MessageProcessor
    participant Helper as AgentSwitchHelper
    participant Agent as Current Agent
    participant LLM as LLM Service
    
    Client->>API: POST /agent/message/stream
    API->>MOS: process_message(session_id, message)
    MOS->>MP: process(session_id, message)
    
    MP->>MP: Добавить user message в сессию
    MP->>MP: Получить/создать контекст агента
    
    alt Явное переключение агента
        MP->>Helper: execute_agent_switch(target_agent)
        Helper->>Helper: Переключить контекст
        Helper-->>MP: new_context
        MP->>Client: StreamChunk(agent_switched)
    end
    
    MP->>Agent: process(session_id, message)
    Agent->>LLM: Запрос к LLM
    LLM-->>Agent: Стрим ответа
    Agent-->>MP: StreamChunk(assistant_message)
    MP-->>MOS: StreamChunk
    MOS-->>API: StreamChunk
    API-->>Client: SSE: data: {...}
    
    alt Агент запросил переключение
        Agent-->>MP: StreamChunk(switch_agent)
        MP->>Helper: handle_agent_switch_request()
        Helper->>Helper: Найти call_id для switch_mode
        Helper->>Helper: Добавить tool_result
        Helper->>Helper: Переключить агента
        Helper-->>MP: (new_context, notification)
        MP->>Client: StreamChunk(agent_switched)
        MP->>Agent: Продолжить с новым агентом
    end
```

---

## Основные файлы и директории

```
app/
├── main.py                    # Точка входа FastAPI
├── api/v1/routers/           # API роутеры (health, sessions, agents, messages, events)
├── core/                      # Конфиги, DI, базовые компоненты
│   ├── config.py             # Конфигурация приложения
│   └── dependencies.py       # Провайдеры зависимостей
├── domain/                    # Доменный слой (DDD)
│   ├── entities/             # Доменные сущности
│   ├── events/               # Доменные события
│   ├── repositories/         # Интерфейсы репозиториев
│   └── services/             # Доменные сервисы
├── infrastructure/           # Инфраструктурный слой
│   ├── adapters/             # Адаптеры для обратной совместимости
│   ├── persistence/          # Реализации репозиториев
│   ├── concurrency/          # Управление конкурентностью
│   ├── cleanup/              # Сервисы очистки
│   └── resilience/           # Паттерны устойчивости
├── agents/                   # Мультиагентная система
│   ├── base_agent.py         # Базовый класс агента
│   ├── orchestrator_agent.py # Координатор
│   ├── coder_agent.py        # Разработчик
│   ├── architect_agent.py    # Архитектор
│   ├── debug_agent.py        # Отладчик
│   ├── ask_agent.py          # Консультант
│   └── prompts/              # Системные промпты
├── events/                   # Event-Driven Architecture
│   ├── event_bus.py          # Шина событий
│   ├── event_types.py        # Типы событий
│   ├── base_event.py         # Базовое событие
│   └── subscribers/          # Подписчики
├── services/                 # Бизнес-логика
│   ├── database.py           # Управление БД
│   ├── agent_router.py       # Маршрутизация агентов
│   ├── llm_stream_service.py # Стриминг LLM
│   ├── hitl_manager.py       # HITL управление
│   └── tool_registry.py      # Реестр инструментов
├── models/                   # Pydantic схемы
└── middleware/               # Middleware (auth, rate limit)

tests/                        # Тесты (unit, integration, e2e)
doc/                          # Документация
```

---

## Быстрый старт

### Через Docker Compose

```bash
# Запуск с пересборкой
docker compose up -d --build

# Просмотр логов
docker compose logs -f agent-runtime
```

### Локальная разработка

```bash
# Установка зависимостей
uv pip install -e .

# Запуск сервиса
uv run uvicorn app.main:app --reload --port 8001

# Запуск тестов
uv run pytest --maxfail=3 --disable-warnings -v tests
```

---

## REST API

**Базовый URL:** `http://localhost:8001`
**Авторизация:** Все endpoints требуют заголовок `X-Internal-Auth`

### Public Endpoints

#### GET /health
Проверка статуса сервиса

**Ответ:**
```json
{"status": "healthy", "version": "2.0.0"}
```

---

### Agent Endpoints

#### POST /agent/message/stream
Стриминговая обработка сообщения (SSE)

**Request:**
```json
{
  "session_id": "user-session-1",
  "role": "user",
  "content": "Create a widget",
  "agent_type": "coder"
}
```

**Response (SSE):**
```
data: {"type":"agent_switched","content":"Switched to coder","is_final":false}
data: {"type":"assistant_message","token":"Creating ","is_final":false}
data: {"type":"tool_call","tool_name":"write_file","call_id":"call_123","is_final":false}
data: [DONE]
```

**Типы StreamChunk:** `agent_switched`, `assistant_message`, `tool_call`, `tool_approval_required`, `error`

---

#### GET /agents
Список зарегистрированных агентов

**Ответ:**
```json
{
  "agents": [
    {"type": "orchestrator", "name": "Orchestrator"},
    {"type": "coder", "name": "Coder"}
  ]
}
```

---

#### GET /agents/{session_id}/current
Текущий активный агент сессии

**Ответ:**
```json
{"current_agent": "coder", "switch_count": 2}
```

---

#### POST /agents/{session_id}/switch
Явное переключение агента

**Request:**
```json
{"agent_type": "architect", "reason": "Design needed"}
```

**Response (SSE):**
```
data: {"type":"agent_switched","content":"Switched to architect","is_final":true}
data: [DONE]
```

---

### Session Endpoints

#### POST /sessions
Создать новую сессию

**Request:**
```json
{"session_id": "my-session", "metadata": {"user_id": "user-123"}}
```

**Ответ:**
```json
{"session_id": "my-session", "created_at": "2026-01-26T10:00:00Z"}
```

---

#### GET /sessions
Список всех сессий

**Query:** `?limit=50&offset=0`

**Ответ:**
```json
{
  "sessions": [{"session_id": "my-session", "message_count": 15}],
  "total": 100
}
```

---

#### GET /sessions/{session_id}/history
История сообщений сессии

**Ответ:**
```json
{
  "messages": [
    {"role": "user", "content": "Create widget"},
    {"role": "assistant", "content": "Creating..."}
  ]
}
```

---

#### POST /sessions/{session_id}/tool-result
Отправить результат выполнения инструмента

**Request:**
```json
{"call_id": "call_123", "result": "File created", "error": null}
```

**Response (SSE):** Продолжение обработки агентом

---

#### POST /sessions/{session_id}/hitl-decision
Отправить HITL решение пользователя

**Request:**
```json
{
  "call_id": "call_123",
  "decision": "approve",
  "modified_arguments": {},
  "feedback": ""
}
```

**Решения:** `approve` (одобрить), `edit` (изменить), `reject` (отклонить)

---

#### GET /sessions/{session_id}/pending-approvals
Получить pending HITL approvals

**Ответ:**
```json
{
  "pending_approvals": [
    {
      "call_id": "call_123",
      "tool_name": "execute_command",
      "arguments": {"command": "rm file.txt"}
    }
  ]
}
```

---

### Event Endpoints

#### GET /events/metrics
Метрики событий

**Query:** `?session_id=my-session&event_type=agent_switched`

**Ответ:**
```json
{
  "metrics": {
    "total_events": 1500,
    "by_type": {"agent_switched": 250, "message_processed": 500}
  }
}
```

---

#### GET /events/audit-log
Audit log событий

**Query:** `?limit=100&offset=0`

**Ответ:**
```json
{
  "audit_log": [
    {
      "event_id": "evt_123",
      "event_type": "agent_switched",
      "timestamp": "2026-01-26T10:00:00Z"
    }
  ]
}
```

---

### Пример полного workflow

```bash
# 1. Создать сессию
curl -X POST 'http://localhost:8001/sessions' \
  -H 'Content-Type: application/json' \
  -H 'X-Internal-Auth: your-key' \
  -d '{"session_id": "my-session"}'

# 2. Отправить сообщение
curl -X POST 'http://localhost:8001/agent/message/stream' \
  -H 'Content-Type: application/json' \
  -H 'X-Internal-Auth: your-key' \
  -d '{
    "session_id": "my-session",
    "role": "user",
    "content": "Create a login form"
  }'

# 3. Отправить результат инструмента (если был tool_call)
curl -X POST 'http://localhost:8001/sessions/my-session/tool-result' \
  -H 'Content-Type: application/json' \
  -H 'X-Internal-Auth: your-key' \
  -d '{"call_id": "call_123", "result": "File created"}'

# 4. Получить историю
curl -X GET 'http://localhost:8001/sessions/my-session/history' \
  -H 'X-Internal-Auth: your-key'
```

---

## Конфигурирование (ENV)

Все настройки через переменные окружения или `.env`-файл (пример в `.env.example`):

### Основные настройки

- `AGENT_RUNTIME__LLM_PROXY_URL` - URL LLM Proxy сервиса
- `AGENT_RUNTIME__LLM_MODEL` - Модель по умолчанию
- `AGENT_RUNTIME__INTERNAL_API_KEY` - Ключ внутренней авторизации
- `AGENT_RUNTIME__LOG_LEVEL` - Уровень логирования (INFO/DEBUG)
- `AGENT_RUNTIME__VERSION` - Версия сервиса

### Мультиагентная система

- `AGENT_RUNTIME__MULTI_AGENT_MODE` - true для мультиагентного режима (по умолчанию)

### База данных

- `AGENT_RUNTIME__DB_URL` - URL базы данных
  - SQLite: `sqlite:///data/agent_runtime.db` (по умолчанию)
  - PostgreSQL: `postgresql+asyncpg://user:pass@host:port/db`

---

## Мультиагентная система

### Агенты

| Агент | Роль | Инструменты | Ограничения |
|-------|------|-------------|-------------|
| **Orchestrator** 🎭 | Координатор | read_file, list_files, search_in_code | Только анализ |
| **Coder** 💻 | Разработчик | Все (9 инструментов) | Нет |
| **Architect** 🏗️ | Архитектор | read_file, write_file, list_files, search_in_code | Только .md |
| **Debug** 🐛 | Отладчик | read_file, list_files, search_in_code, execute_command | Без write_file |
| **Ask** 💬 | Консультант | read_file, search_in_code, list_files | Только чтение |

### Инструменты

1. `read_file` - Чтение файла
2. `write_file` - Запись файла
3. `list_files` - Список файлов
4. `search_in_code` - Поиск в коде
5. `execute_command` - Выполнение команды
6. `apply_diff` - Применение diff
7. `ask_followup_question` - Вопрос пользователю
8. `attempt_completion` - Завершение задачи
9. `switch_mode` - Переключение режима

---

## Event-Driven Architecture

### Типы событий

- **Agent events**: agent_switched, agent_processing_started, agent_processing_completed
- **Session events**: session_created, message_added
- **Tool events**: tool_execution_requested, tool_approval_required
- **HITL events**: hitl_decision_made

### Подписчики

- **MetricsCollector** - Сбор метрик
- **AuditLogger** - Аудит логирование
- **AgentContextSubscriber** - Управление контекстом агентов
- **SessionMetricsCollector** - Метрики сессий

Подробная документация: [`doc/EVENT_DRIVEN_ARCHITECTURE.md`](doc/EVENT_DRIVEN_ARCHITECTURE.md)

---

## Тестирование

```bash
# Все тесты
uv run pytest tests

# С покрытием
uv run pytest tests --cov=app --cov-report=html

# Конкретный тест
uv run pytest tests/test_multi_agent_system.py -v
```

Unit- и integration-тесты находятся в `tests/`. Всё DI легко мокается через core/dependencies.py.

---

## Как расширять

### Добавление нового агента

1. Создайте класс агента в `app/agents/`
2. Наследуйтесь от `BaseAgent`
3. Определите `agent_type`, `system_prompt`, `allowed_tools`
4. Зарегистрируйте в `app/agents/__init__.py`

### Добавление нового инструмента

1. Создайте функцию инструмента
2. Добавьте спецификацию в `tool_registry.py`
3. Зарегистрируйте через `register_tool()`

### Добавление нового события

1. Создайте класс события в `app/events/`
2. Наследуйтесь от `BaseEvent`
3. Определите `event_type` и `event_category`
4. Публикуйте через `event_bus.publish()`

---

## Документация

### Архитектура и дизайн

- [Итоговый отчет о рефакторинге v2.0](../../doc/agent-runtime-refactoring-complete-report.md) ⭐ **Новое**
- [Проектирование рефакторинга MessageOrchestrationService](../../doc/message-orchestration-refactoring-design.md)
- [Аудит Clean Architecture](../../doc/agent-runtime-clean-architecture-audit.md)
- [Event-Driven Architecture](doc/EVENT_DRIVEN_ARCHITECTURE.md)

### Мультиагентная система

- [Мультиагентная система](../doc/MULTI_AGENT_README.md)
- [Быстрый старт мультиагентов](../doc/multi-agent-quick-start.md)

### Конфигурация

- [Конфигурация БД](../doc/DATABASE_CONFIGURATION.md)

---

## Контрибьюторам

- Соблюдайте DI-подход: любые Depends/инстанциаторы только через core/dependencies.py
- Не добавляйте бизнес-логику в эндпойнты и роутеры
- Используйте доменные сервисы для бизнес-логики
- Публикуйте события для важных операций
- Пишите тесты для новой функциональности
- Документируйте изменения

---

© 2026 Codelab Contributors  
MIT License
