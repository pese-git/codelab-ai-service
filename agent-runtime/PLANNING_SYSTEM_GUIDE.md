# Руководство по системе планирования

## Обзор

Система планирования позволяет Orchestrator агенту разбивать сложные задачи на управляемые подзадачи, которые выполняются последовательно специализированными агентами.

## Архитектура

### Компоненты

1. **ExecutionPlan** - План выполнения задачи
   - Содержит список подзадач
   - Отслеживает прогресс выполнения
   - Хранит метаданные о задаче

2. **Subtask** - Отдельная подзадача
   - Описание задачи
   - Назначенный агент
   - Статус выполнения
   - Зависимости от других подзадач

3. **SessionManager** - Управление планами
   - Хранение планов в памяти
   - Методы для управления подзадачами
   - Отслеживание прогресса

4. **MultiAgentOrchestrator** - Выполнение планов
   - Последовательное выполнение подзадач
   - Переключение между агентами
   - Обработка ошибок

## Использование

### Создание плана

Orchestrator может создать план используя инструмент `create_plan`:

```python
create_plan({
    "subtasks": [
        {
            "id": "subtask_1",
            "description": "Add riverpod dependency to pubspec.yaml",
            "agent": "coder",
            "estimated_time": "2 min"
        },
        {
            "id": "subtask_2",
            "description": "Create provider definitions",
            "agent": "coder",
            "estimated_time": "5 min",
            "dependencies": ["subtask_1"]
        },
        {
            "id": "subtask_3",
            "description": "Update main.dart to use ProviderScope",
            "agent": "coder",
            "estimated_time": "3 min",
            "dependencies": ["subtask_2"]
        }
    ]
})
```

### Структура подзадачи

Каждая подзадача должна содержать:

- **id** (обязательно): Уникальный идентификатор (например, "subtask_1")
- **description** (обязательно): Четкое описание задачи
- **agent** (обязательно): Агент для выполнения ("coder", "architect", "debug", "ask")
- **estimated_time** (опционально): Оценка времени (например, "2 min", "5 min")
- **dependencies** (опционально): Список ID подзадач, которые должны быть выполнены первыми

### Статусы подзадач

- **PENDING** - Ожидает выполнения
- **IN_PROGRESS** - Выполняется в данный момент
- **COMPLETED** - Успешно завершена
- **FAILED** - Завершена с ошибкой
- **SKIPPED** - Пропущена

## Примеры использования

### Пример 1: Миграция на Riverpod

**Задача пользователя**: "Migrate from Provider to Riverpod"

**План Orchestrator**:

```json
{
  "subtasks": [
    {
      "id": "subtask_1",
      "description": "Add riverpod dependency to pubspec.yaml",
      "agent": "coder",
      "estimated_time": "2 min"
    },
    {
      "id": "subtask_2",
      "description": "Create provider definitions using Riverpod",
      "agent": "coder",
      "estimated_time": "5 min",
      "dependencies": ["subtask_1"]
    },
    {
      "id": "subtask_3",
      "description": "Update main.dart to use ProviderScope",
      "agent": "coder",
      "estimated_time": "3 min",
      "dependencies": ["subtask_2"]
    },
    {
      "id": "subtask_4",
      "description": "Migrate widgets to use Riverpod hooks",
      "agent": "coder",
      "estimated_time": "10 min",
      "dependencies": ["subtask_3"]
    },
    {
      "id": "subtask_5",
      "description": "Update tests for Riverpod",
      "agent": "coder",
      "estimated_time": "5 min",
      "dependencies": ["subtask_4"]
    }
  ]
}
```

### Пример 2: Реализация системы аутентификации

**Задача пользователя**: "Implement authentication system"

**План Orchestrator**:

```json
{
  "subtasks": [
    {
      "id": "subtask_1",
      "description": "Design authentication architecture and data models",
      "agent": "architect",
      "estimated_time": "10 min"
    },
    {
      "id": "subtask_2",
      "description": "Create user model and database schema",
      "agent": "coder",
      "estimated_time": "5 min",
      "dependencies": ["subtask_1"]
    },
    {
      "id": "subtask_3",
      "description": "Implement authentication service",
      "agent": "coder",
      "estimated_time": "15 min",
      "dependencies": ["subtask_2"]
    },
    {
      "id": "subtask_4",
      "description": "Create login and registration UI",
      "agent": "coder",
      "estimated_time": "10 min",
      "dependencies": ["subtask_3"]
    },
    {
      "id": "subtask_5",
      "description": "Add authentication tests",
      "agent": "coder",
      "estimated_time": "8 min",
      "dependencies": ["subtask_4"]
    }
  ]
}
```

## Когда использовать планирование

### Используйте планирование для:

✅ **Сложных задач**:
- Миграции между фреймворками
- Рефакторинг всей системы
- Реализация новых функций с несколькими компонентами
- Задачи, затрагивающие множество файлов

✅ **Многошаговых процессов**:
- Задачи с четкой последовательностью шагов
- Задачи с зависимостями между шагами
- Задачи, требующие координации разных агентов

✅ **Задач с высоким риском timeout**:
- Задачи, которые могут занять более 5 минут
- Задачи с множеством операций

### НЕ используйте планирование для:

❌ **Простых задач**:
- Изменение одного файла
- Простые исправления ошибок
- Прямые вопросы
- Задачи, которые один агент может выполнить быстро

## API SessionManager

### Методы управления планами

```python
# Сохранить план
session_mgr.set_plan(session_id: str, plan: ExecutionPlan)

# Получить план
plan = session_mgr.get_plan(session_id: str) -> Optional[ExecutionPlan]

# Проверить наличие плана
has_plan = session_mgr.has_plan(session_id: str) -> bool

# Отметить подзадачу как выполненную
session_mgr.mark_subtask_complete(
    session_id: str,
    subtask_id: str,
    result: Optional[str] = None
) -> bool

# Отметить подзадачу как неудачную
session_mgr.mark_subtask_failed(
    session_id: str,
    subtask_id: str,
    error: str
) -> bool

# Получить следующую подзадачу
next_subtask = session_mgr.get_next_subtask(session_id: str) -> Optional[Subtask]

# Очистить план
session_mgr.clear_plan(session_id: str)
```

## Поток выполнения

1. **Пользователь отправляет сложную задачу**
   ```
   User: "Migrate from Provider to Riverpod"
   ```

2. **Orchestrator анализирует задачу**
   - Определяет, что задача сложная
   - Решает создать план

3. **Orchestrator создает план**
   - Использует инструмент `create_plan`
   - Разбивает задачу на подзадачи
   - Определяет зависимости

4. **План сохраняется в SessionManager**
   - План связывается с сессией
   - Готов к выполнению

5. **MultiAgentOrchestrator выполняет план**
   - Получает следующую подзадачу
   - Переключается на соответствующего агента
   - Выполняет подзадачу
   - Отмечает как выполненную
   - Переходит к следующей

6. **Завершение плана**
   - Все подзадачи выполнены
   - Отправляется итоговый отчет
   - План очищается
   - Возврат к Orchestrator

## Обработка ошибок

### Неудачная подзадача

Если подзадача завершается с ошибкой:
- Подзадача отмечается как FAILED
- Ошибка сохраняется в поле `error`
- Выполнение продолжается со следующей подзадачей
- Зависимые подзадачи могут быть пропущены

### Зависимости

Подзадачи с невыполненными зависимостями:
- Пропускаются при получении следующей подзадачи
- Выполняются только после завершения зависимостей
- Если зависимость неудачна, подзадача может быть пропущена

## Мониторинг и отладка

### Логирование

Система планирования логирует:
- Создание планов
- Начало выполнения подзадач
- Завершение подзадач
- Ошибки выполнения
- Прогресс плана

### Метаданные в StreamChunk

Клиент получает метаданные о выполнении:

```python
# При создании плана
{
    "type": "assistant_message",
    "metadata": {
        "plan_id": "plan_abc123",
        "subtask_count": 5,
        "subtasks": [...]
    }
}

# При выполнении подзадачи
{
    "type": "assistant_message",
    "metadata": {
        "subtask_id": "subtask_1",
        "subtask_status": "in_progress",
        "agent": "coder"
    }
}

# При завершении плана
{
    "type": "assistant_message",
    "metadata": {
        "plan_id": "plan_abc123",
        "plan_status": "complete",
        "total_subtasks": 5,
        "completed": 4,
        "failed": 1
    }
}
```

## Тестирование

Запуск тестов системы планирования:

```bash
cd codelab-ai-service/agent-runtime
pytest tests/test_planning_system.py -v
```

## Ограничения

1. **Последовательное выполнение**: Подзадачи выполняются последовательно, не параллельно
2. **Хранение в памяти**: Планы хранятся только в памяти (не персистентны)
3. **Простые зависимости**: Поддерживаются только прямые зависимости между подзадачами
4. **Без повторных попыток**: Неудачные подзадачи не повторяются автоматически

## Будущие улучшения

- [ ] Персистентное хранение планов в базе данных
- [ ] Параллельное выполнение независимых подзадач
- [ ] Автоматические повторные попытки для неудачных подзадач
- [ ] Более сложные графы зависимостей
- [ ] Приостановка и возобновление выполнения плана
- [ ] Оценка времени выполнения на основе истории
- [ ] Визуализация прогресса плана в UI

## Связанные файлы

- [`app/models/schemas.py`](app/models/schemas.py) - Модели данных
- [`app/services/session_manager_async.py`](app/services/session_manager_async.py) - Управление планами
- [`app/services/multi_agent_orchestrator.py`](app/services/multi_agent_orchestrator.py) - Выполнение планов
- [`app/agents/orchestrator_agent.py`](app/agents/orchestrator_agent.py) - Создание планов
- [`app/agents/prompts/orchestrator.py`](app/agents/prompts/orchestrator.py) - Промпт с инструкциями
- [`app/services/tool_registry.py`](app/services/tool_registry.py) - Инструмент create_plan
- [`tests/test_planning_system.py`](tests/test_planning_system.py) - Тесты
