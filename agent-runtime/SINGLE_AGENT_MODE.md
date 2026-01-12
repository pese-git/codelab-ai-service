# Single-Agent Mode (UniversalAgent)

## Обзор

Single-Agent режим реализован для baseline сравнения с Multi-Agent системой в рамках POC. В этом режиме используется единственный универсальный агент (`UniversalAgent`), который имеет доступ ко всем инструментам и может выполнять любые задачи без делегирования.

## Архитектура

### Ключевая идея

Вместо создания отдельной логики для single-agent режима, мы используем существующую инфраструктуру `agent_router`:
- В **Multi-Agent режиме**: регистрируются Orchestrator + 4 специализированных агента
- В **Single-Agent режиме**: регистрируются только Orchestrator + UniversalAgent

Orchestrator автоматически определяет, что доступен только Universal агент, и всегда маршрутизирует на него.

### Компоненты

1. **UniversalAgent** ([`app/agents/universal_agent.py`](app/agents/universal_agent.py))
   - Единственный рабочий агент в single-agent режиме
   - Имеет доступ ко всем 8 инструментам
   - Нет ограничений на редактирование файлов
   - Универсальный промпт для обработки любых задач

2. **AgentType.UNIVERSAL** ([`app/agents/base_agent.py`](app/agents/base_agent.py:25))
   - Новый тип агента в enum `AgentType`
   - Значение: `"universal"`

3. **MULTI_AGENT_MODE** ([`app/core/config.py`](app/core/config.py:57))
   - Конфигурационный параметр для переключения режимов
   - По умолчанию: `true` (Multi-Agent режим)
   - Переменная окружения: `AGENT_RUNTIME__MULTI_AGENT_MODE`

4. **initialize_agents()** ([`app/agents/__init__.py`](app/agents/__init__.py:17))
   - Условная регистрация агентов в зависимости от режима
   - Multi-Agent: регистрирует 5 агентов (Orchestrator + 4 специалиста)
   - Single-Agent: регистрирует 2 агента (Orchestrator + Universal)

5. **OrchestratorAgent** ([`app/agents/orchestrator_agent.py`](app/agents/orchestrator_agent.py:104))
   - Автоматически определяет single-agent режим
   - Если доступен только Universal агент, маршрутизирует на него без LLM классификации
   - В multi-agent режиме использует LLM для выбора специалиста

## Использование

### Включение Single-Agent режима

#### Через переменную окружения

```bash
export AGENT_RUNTIME__MULTI_AGENT_MODE=false
```

#### Через .env файл

```env
AGENT_RUNTIME__MULTI_AGENT_MODE=false
```

#### Через Docker Compose

```yaml
services:
  agent-runtime:
    environment:
      - AGENT_RUNTIME__MULTI_AGENT_MODE=false
```

### Включение Multi-Agent режима (по умолчанию)

```bash
export AGENT_RUNTIME__MULTI_AGENT_MODE=true
# или просто не устанавливать переменную
```

## Доступные инструменты

UniversalAgent имеет доступ ко всем инструментам:

1. **read_file** - Чтение содержимого файлов
2. **write_file** - Создание и изменение файлов
3. **list_files** - Просмотр структуры директорий
4. **search_in_code** - Поиск паттернов в коде
5. **create_directory** - Создание директорий
6. **execute_command** - Выполнение shell команд
7. **attempt_completion** - Завершение задачи
8. **ask_followup_question** - Запрос уточнений у пользователя

## Отличия от Multi-Agent режима

| Аспект | Multi-Agent | Single-Agent (Universal) |
|--------|-------------|--------------------------|
| Зарегистрированные агенты | 5 (Orchestrator + 4 специалиста) | 2 (Orchestrator + Universal) |
| Маршрутизация | Orchestrator использует LLM для выбора | Orchestrator всегда выбирает Universal |
| Специализация | Каждый агент специализирован | Универсальный агент |
| Ограничения инструментов | Разные для каждого агента | Все инструменты доступны |
| Ограничения файлов | Architect может редактировать только .md | Нет ограничений |
| Переключение агентов | Динамическое между специалистами | Всегда Universal |
| Контекст агентов | Сохраняется между переключениями | Не требуется |
| LLM вызовы для маршрутизации | Да (классификация задачи) | Нет (прямая маршрутизация) |

## Поток обработки запроса

### Multi-Agent режим

```
User Request
    ↓
MultiAgentOrchestrator
    ↓
OrchestratorAgent (LLM классификация)
    ↓
[Coder | Architect | Debug | Ask] Agent
    ↓
Response
```

### Single-Agent режим

```
User Request
    ↓
MultiAgentOrchestrator
    ↓
OrchestratorAgent (автоматический выбор)
    ↓
UniversalAgent
    ↓
Response
```

## Тестирование

### Запуск тестов

```bash
cd codelab-ai-service/agent-runtime

# Тест с Multi-Agent режимом (по умолчанию)
uv run python test_single_agent_mode.py

# Тест с Single-Agent режимом
AGENT_RUNTIME__MULTI_AGENT_MODE=false uv run python test_single_agent_mode.py
```

### Ожидаемый результат (Single-Agent режим)

```
2026-01-12 13:51:47,749 - agent-runtime.agents - INFO - Initializing single-agent system (Universal mode)...
2026-01-12 13:51:47,749 - agent-runtime.agents - INFO - Successfully registered 2 agents: ['orchestrator', 'universal']
2026-01-12 13:51:47,749 - agent-runtime.agents - INFO - Single-agent system initialized successfully
2026-01-12 13:51:47,749 - agent-runtime.agents - INFO - Orchestrator will always route to Universal agent

============================================================
✓ All tests passed!
============================================================
```

## Метрики для сравнения

При проведении POC рекомендуется собирать следующие метрики:

### Производительность
- Время выполнения задачи (latency)
- Количество вызовов LLM
- Общее количество токенов
- Время до первого ответа (TTFR)
- **Overhead маршрутизации** (в single-agent режиме должен быть меньше)

### Качество
- Успешность выполнения задачи
- Количество ошибок
- Необходимость повторных попыток
- Качество сгенерированного кода

### Использование ресурсов
- Количество использованных инструментов
- Типы использованных инструментов
- Количество операций чтения/записи файлов

## Логирование

Single-Agent режим добавляет специфичные лог-сообщения:

```python
# При инициализации
logger.info("Initializing single-agent system (Universal mode)...")
logger.info("Successfully registered 2 agents: ['orchestrator', 'universal']")
logger.info("Orchestrator will always route to Universal agent")

# При маршрутизации
logger.info("Single-agent mode detected, routing to Universal agent")
```

Для включения debug-логов:

```bash
export AGENT_RUNTIME__LOG_LEVEL=DEBUG
```

## Примеры использования

### Пример 1: Создание файла

**Запрос пользователя:**
```
Create a Python file hello.py that prints "Hello, World!"
```

**Single-Agent режим:**
- Orchestrator → Universal Agent
- UniversalAgent напрямую создает файл используя `write_file`

**Multi-Agent режим:**
- Orchestrator → LLM классификация → CoderAgent
- CoderAgent создает файл

### Пример 2: Отладка

**Запрос пользователя:**
```
Debug the error in main.py
```

**Single-Agent режим:**
- Orchestrator → Universal Agent
- UniversalAgent читает файл, анализирует и исправляет

**Multi-Agent режим:**
- Orchestrator → LLM классификация → DebugAgent
- DebugAgent анализирует (read-only)
- Может переключиться на CoderAgent для исправления

## Преимущества подхода через agent_router

1. **Переиспользование кода** - Используется существующая инфраструктура маршрутизации
2. **Простота** - Нет дублирования логики обработки
3. **Консистентность** - Оба режима работают через одинаковый интерфейс
4. **Тестируемость** - Легко переключаться между режимами для тестирования
5. **Меньше overhead** - В single-agent режиме нет LLM вызова для классификации

## Ограничения

1. **Нет специализации** - UniversalAgent не оптимизирован для конкретных задач
2. **Больший промпт** - Универсальный промпт может быть менее эффективным
3. **Нет контекста агентов** - Не сохраняется история переключений между специализированными агентами

## Рекомендации для POC

1. **Тестируйте одинаковые задачи** в обоих режимах
2. **Собирайте метрики** для объективного сравнения
3. **Документируйте результаты** в [`MULTI_AGENT_POC_RESULTS_TEMPLATE.md`](../../MULTI_AGENT_POC_RESULTS_TEMPLATE.md)
4. **Используйте одинаковые LLM модели** для честного сравнения
5. **Тестируйте разные типы задач**: coding, debugging, architecture, questions
6. **Измеряйте overhead маршрутизации** - в single-agent должен быть меньше

## Связанные документы

- [`MULTI_AGENT_POC_PLAN.md`](../../MULTI_AGENT_POC_PLAN.md) - План POC
- [`MULTI_AGENT_POC_BENCHMARK.md`](../../MULTI_AGENT_POC_BENCHMARK.md) - Методология бенчмарков
- [`MULTI_AGENT_POC_METRICS.md`](../../MULTI_AGENT_POC_METRICS.md) - Метрики для сбора
- [`MULTI_AGENT_IMPLEMENTATION.md`](MULTI_AGENT_IMPLEMENTATION.md) - Детали реализации Multi-Agent

## Troubleshooting

### Режим не переключается

Проверьте, что переменная окружения установлена корректно:

```bash
# Проверка текущего значения
echo $AGENT_RUNTIME__MULTI_AGENT_MODE

# Проверка в Python
python -c "from app.core.config import AppConfig; print(AppConfig.MULTI_AGENT_MODE)"
```

### UniversalAgent не импортируется

Убедитесь, что все зависимости установлены:

```bash
cd codelab-ai-service/agent-runtime
uv sync
```

### Тесты не проходят

Запустите тесты с подробным выводом:

```bash
uv run python test_single_agent_mode.py -v
```

### Orchestrator не маршрутизирует на Universal

Проверьте логи инициализации:

```bash
# Должно быть:
# "Successfully registered 2 agents: ['orchestrator', 'universal']"
# "Orchestrator will always route to Universal agent"
```

Если видите 5 агентов, значит MULTI_AGENT_MODE=true.
