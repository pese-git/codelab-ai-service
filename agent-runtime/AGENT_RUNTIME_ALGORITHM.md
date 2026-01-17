# Алгоритм работы Agent Runtime

## Обзор системы

Agent Runtime - это многокомпонентная система для выполнения задач через специализированных AI агентов. Система поддерживает как простые задачи (прямое выполнение), так и сложные задачи (планирование и координация).

## Основные компоненты

### 1. MultiAgentOrchestrator
Главная точка входа, координирующая работу всех агентов.

### 2. Агенты
- **Orchestrator Agent**: Координатор, классифицирует задачи и маршрутизирует
- **Architect Agent**: Планировщик для сложных задач
- **Coder Agent**: Специалист по написанию и модификации кода
- **Debug Agent**: Специалист по отладке и анализу ошибок
- **Ask Agent**: Специалист по ответам на вопросы
- **Universal Agent**: Универсальный агент для одиночных режимов

### 3. Сервисы
- **SessionManager**: Управление сессиями и историей
- **AgentRouter**: Маршрутизация между агентами
- **ToolRegistry**: Реестр доступных инструментов
- **LLM Stream Service**: Потоковая обработка LLM ответов

## Алгоритм работы

### Шаг 1: Получение запроса пользователя

```
Пользователь → Gateway API → MultiAgentOrchestrator.process_message()
```

### Шаг 2: Инициализация контекста

```python
# Получение/создание сессии
context = await agent_context_manager.get_or_create(session_id)

# Получение session manager
session_mgr = await get_async_session_manager()
```

### Шаг 3: Проверка активных планов

```python
# Есть ли активный план выполнения?
if session_mgr.has_plan(session_id):
    → _execute_plan()  # Продолжить выполнение плана

# Есть ли план в ожидании подтверждения?
elif session_mgr.has_pending_plan_confirmation(session_id):
    → Обработка подтверждения пользователя
```

### Шаг 4: Маршрутизация через Orchestrator Agent

Если текущий агент - **Orchestrator**:

```python
# Анализ запроса через LLM
response = await orchestrator.process(session_id, message, context, session_mgr)

# Классификация задачи
if SIMPLE_TASK:
    → switch_agent(TARGET_AGENT)
elif COMPLEX_TASK:
    → switch_agent(ARCHITECT)  # Для планирования
```

### Шаг 5: Обработка различных типов задач

#### Для SIMPLE задач:
```
Orchestrator → LLM классификация → switch_agent(Coder/Debug/Ask)
→ Целевой агент выполняет задачу
```

#### Для COMPLEX задач:
```
Orchestrator → switch_agent(Architect)
Architect → Анализ задачи → create_plan()
Architect → Показ плана пользователю → Ожидание подтверждения
Пользователь подтверждает → Orchestrator/PlanExecutor → Выполнение плана
```

### Шаг 6: Выполнение планов (Plan Execution)

```python
while plan.has_pending_subtasks():
    subtask = session_mgr.get_next_subtask()

    # Переключение на нужного агента
    switch_agent(subtask.agent)

    # Выполнение подзадачи
    result = await agent.process(subtask.description)

    # Отметка выполнения
    session_mgr.mark_subtask_complete(subtask.id, result)
```

### Шаг 7: Обработка инструментов (Tools)

Каждый агент имеет доступ к инструментам:

```python
# Обработка tool calls
if chunk.type == "tool_call":
    if agent.can_use_tool(chunk.tool_name):
        result = await execute_tool(chunk.tool_name, chunk.arguments)
        yield tool_result
    else:
        yield error("Tool not allowed")
```

## Типы сообщений (StreamChunk)

### 1. assistant_message
Обычные сообщения от агентов

### 2. switch_agent
Переключение между агентами
```json
{
  "type": "switch_agent",
  "target_agent": "coder",
  "reason": "Task requires code changes"
}
```

### 3. plan_notification
Показ плана пользователю для подтверждения
```json
{
  "type": "plan_notification",
  "content": "План выполнения...",
  "metadata": {
    "requires_confirmation": true,
    "subtasks": [...]
  }
}
```

### 4. tool_call / tool_result
Вызовы инструментов и их результаты

### 5. error
Сообщения об ошибках

## Состояния сессии

### 1. NEW_SESSION
Начальное состояние

### 2. AGENT_ACTIVE
Активный агент обрабатывает задачу

### 3. PLAN_PENDING_CONFIRMATION
План создан, ожидается подтверждение пользователя

### 4. PLAN_EXECUTING
План выполняется

### 5. PLAN_COMPLETED
Все подзадачи выполнены

## Обработка ошибок

### 1. LLM ошибки
- Fallback на keyword классификацию
- Повторные попытки с exponential backoff

### 2. Tool ошибки
- Логирование ошибок
- Продолжение выполнения с другими подзадачами

### 3. Agent switching ошибки
- Fallback на Orchestrator
- Сброс сессии

## Масштабируемость

### Добавление новых агентов:
1. Создать класс агента наследующий `BaseAgent`
2. Зарегистрировать в `AgentRouter`
3. Добавить в `AgentType` enum
4. Обновить классификацию в Orchestrator

### Добавление новых инструментов:
1. Реализовать функцию в `tool_registry.py`
2. Зарегистрировать в `LOCAL_TOOLS`
3. Добавить в `allowed_tools` нужных агентов

## Мониторинг и отладка

### Метрики:
- Время выполнения задач
- Количество tool calls
- Количество agent switches
- Успешность выполнения планов

### Логи:
- Debug логи для каждого шага
- Error логи для исключений
- Performance метрики

## Безопасность

### Валидация инструментов:
- Каждая tool call проверяется на соответствие правам агента
- Файловые операции ограничены (Architect только .md файлы)

### Rate limiting:
- Ограничение количества tool calls
- Timeout для долгих операций

---

*Этот документ описывает текущую архитектуру agent-runtime. Для внесения изменений в алгоритм работы требуется обновление данной документации.*