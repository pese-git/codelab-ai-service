# ExecutionEngine & SubtaskExecutor - Руководство разработчика

> **Версия:** 0.6.0-alpha  
> **Дата:** 2026-01-31  
> **Статус:** Ready for Integration

---

## 📚 Содержание

1. [Обзор](#обзор)
2. [SubtaskExecutor](#subtaskexecutor)
3. [ExecutionEngine](#executionengine)
4. [Примеры использования](#примеры-использования)
5. [Best Practices](#best-practices)
6. [Troubleshooting](#troubleshooting)

---

## Обзор

### Архитектура

```
┌─────────────────────────────────────────────────┐
│           OrchestratorAgent                     │
│  (координирует весь процесс)                    │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│           ExecutionEngine                       │
│  • Управление жизненным циклом плана            │
│  • Батчирование подзадач                        │
│  • Параллельное выполнение                      │
│  • Агрегация результатов                        │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│           SubtaskExecutor                       │
│  • Выполнение одной подзадачи                   │
│  • Маршрутизация к агенту                       │
│  • Обработка результатов                        │
│  • Error handling                               │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│           Target Agent                          │
│  (CoderAgent, DebugAgent, AskAgent)             │
└─────────────────────────────────────────────────┘
```

### Компоненты

| Компонент | Ответственность | Уровень |
|-----------|----------------|---------|
| **ExecutionEngine** | Координация плана | High-level |
| **SubtaskExecutor** | Выполнение подзадачи | Low-level |
| **DependencyResolver** | Порядок выполнения | Utility |
| **PlanRepository** | Персистентность | Infrastructure |

---

## SubtaskExecutor

### Назначение

Выполняет **одну подзадачу** в целевом агенте и обновляет её статус.

### Инициализация

```python
from app.domain.services.subtask_executor import SubtaskExecutor
from app.domain.repositories.plan_repository import PlanRepository

# Создание
subtask_executor = SubtaskExecutor(
    plan_repository=plan_repository,
    max_retries=3  # Опционально, по умолчанию 3
)
```

### Основные методы

#### 1. execute_subtask()

Выполнить подзадачу в целевом агенте.

```python
result = await subtask_executor.execute_subtask(
    plan_id="plan-123",
    subtask_id="subtask-456",
    session_id="session-789",
    session_service=session_service,
    stream_handler=stream_handler
)

# Результат
{
    "subtask_id": "subtask-456",
    "status": "completed",  # или "failed"
    "result": {
        "content": "Task completed successfully",
        "metadata": {...}
    },
    "agent": "coder",
    "started_at": "2026-01-31T10:00:00Z",
    "completed_at": "2026-01-31T10:05:30Z",
    "duration_seconds": 330.0
}
```

#### 2. retry_failed_subtask()

Повторить выполнение неудавшейся подзадачи.

```python
result = await subtask_executor.retry_failed_subtask(
    plan_id="plan-123",
    subtask_id="subtask-456",
    session_id="session-789",
    session_service=session_service,
    stream_handler=stream_handler
)
```

#### 3. get_subtask_status()

Получить текущий статус подзадачи.

```python
status = await subtask_executor.get_subtask_status(
    plan_id="plan-123",
    subtask_id="subtask-456"
)

# Результат
{
    "subtask_id": "subtask-456",
    "description": "Implement feature X",
    "agent": "coder",
    "status": "running",
    "dependencies": ["subtask-123"],
    "result": None,
    "error": None,
    "started_at": "2026-01-31T10:00:00Z",
    "completed_at": None,
    "duration_seconds": None
}
```

### Контекст для агента

SubtaskExecutor автоматически подготавливает контекст с результатами зависимостей:

```python
# Агент получает:
context = {
    "subtask_id": "subtask-456",
    "plan_id": "plan-123",
    "plan_goal": "Build feature X",
    "dependencies": {
        "subtask-123": {
            "description": "Create database schema",
            "result": "Schema created successfully",
            "agent": "coder"
        }
    },
    "metadata": {...},
    "execution_mode": "subtask"
}
```

### Error Handling

```python
from app.domain.services.subtask_executor import SubtaskExecutionError

try:
    result = await subtask_executor.execute_subtask(...)
except SubtaskExecutionError as e:
    # Обработка ошибки
    logger.error(f"Subtask execution failed: {e}")
    
    # Подзадача автоматически помечена как FAILED
    # Можно попробовать retry
    result = await subtask_executor.retry_failed_subtask(...)
```

---

## ExecutionEngine

### Назначение

Координирует выполнение **всего плана** с учётом зависимостей и параллелизма.

### Инициализация

```python
from app.domain.services.execution_engine import ExecutionEngine
from app.domain.services.subtask_executor import SubtaskExecutor
from app.domain.services.dependency_resolver import DependencyResolver

# Создание
execution_engine = ExecutionEngine(
    plan_repository=plan_repository,
    subtask_executor=subtask_executor,
    dependency_resolver=dependency_resolver,
    max_parallel_tasks=3  # Опционально, по умолчанию 3
)
```

### Основные методы

#### 1. execute_plan()

Выполнить весь план.

```python
result = await execution_engine.execute_plan(
    plan_id="plan-123",
    session_id="session-789",
    session_service=session_service,
    stream_handler=stream_handler
)

# Результат
{
    "plan_id": "plan-123",
    "status": "completed",  # или "failed"
    "completed_subtasks": 5,
    "failed_subtasks": 0,
    "total_subtasks": 5,
    "success_rate": 100.0,
    "results": {
        "subtask-1": {...},
        "subtask-2": {...},
        ...
    },
    "errors": {},
    "duration_seconds": 450.5
}
```

#### 2. get_execution_status()

Получить текущий статус выполнения плана.

```python
status = await execution_engine.get_execution_status(
    plan_id="plan-123"
)

# Результат
{
    "plan_id": "plan-123",
    "status": "in_progress",
    "progress": {
        "total": 5,
        "done": 2,
        "failed": 0,
        "running": 1,
        "pending": 2,
        "percentage": 40.0
    },
    "current_subtask_id": "subtask-3",
    "started_at": "2026-01-31T10:00:00Z",
    "completed_at": None
}
```

#### 3. cancel_execution()

Отменить выполнение плана.

```python
result = await execution_engine.cancel_execution(
    plan_id="plan-123",
    reason="User requested cancellation"
)

# Результат
{
    "plan_id": "plan-123",
    "status": "cancelled",
    "reason": "User requested cancellation",
    "cancelled_at": "2026-01-31T10:15:00Z"
}
```

### Параллельное выполнение

ExecutionEngine автоматически определяет, какие подзадачи можно выполнять параллельно:

```python
# План с зависимостями:
# Task 1 (no deps) ─┐
# Task 2 (no deps) ─┼─> Task 4 (deps: 1,2,3)
# Task 3 (no deps) ─┘

# ExecutionEngine создаст батчи:
batches = [
    ["task-1", "task-2", "task-3"],  # Batch 1: параллельно
    ["task-4"]                        # Batch 2: после завершения 1-3
]

# Выполнение:
# 1. Запускает task-1, task-2, task-3 параллельно (asyncio.gather)
# 2. Ждёт завершения всех трёх
# 3. Запускает task-4
```

### Ограничение параллелизма

```python
# Если независимых задач больше, чем max_parallel_tasks:
# Task 1, Task 2, Task 3, Task 4, Task 5 (все независимые)
# max_parallel_tasks = 2

# Батчи:
batches = [
    ["task-1", "task-2"],  # Batch 1
    ["task-3", "task-4"],  # Batch 2
    ["task-5"]             # Batch 3
]
```

### Error Handling

```python
from app.domain.services.execution_engine import ExecutionEngineError

try:
    result = await execution_engine.execute_plan(...)
    
    if result.status == "failed":
        # Частичный успех - некоторые подзадачи failed
        logger.warning(
            f"Plan partially failed: "
            f"{result.failed_subtasks}/{result.total_subtasks} failed"
        )
        
        # Проверить ошибки
        for subtask_id, error in result.errors.items():
            logger.error(f"Subtask {subtask_id} failed: {error}")
            
except ExecutionEngineError as e:
    # Критическая ошибка (план не найден, не утверждён и т.д.)
    logger.error(f"Execution engine error: {e}")
```

---

## Примеры использования

### Пример 1: Простое выполнение плана

```python
async def execute_simple_plan():
    # 1. Создать компоненты
    plan_repo = PlanRepositoryImpl(db_session)
    dep_resolver = DependencyResolver()
    subtask_exec = SubtaskExecutor(plan_repo)
    exec_engine = ExecutionEngine(plan_repo, subtask_exec, dep_resolver)
    
    # 2. Выполнить план
    result = await exec_engine.execute_plan(
        plan_id="plan-123",
        session_id="session-789",
        session_service=session_service,
        stream_handler=stream_handler
    )
    
    # 3. Проверить результат
    if result.status == "completed":
        print(f"✅ Plan completed successfully!")
        print(f"   Duration: {result.duration_seconds}s")
    else:
        print(f"❌ Plan failed: {result.failed_subtasks} subtasks failed")
```

### Пример 2: Мониторинг прогресса

```python
async def monitor_plan_execution(plan_id: str):
    exec_engine = get_execution_engine()
    
    # Запустить выполнение в фоне
    task = asyncio.create_task(
        exec_engine.execute_plan(plan_id, ...)
    )
    
    # Мониторить прогресс
    while not task.done():
        status = await exec_engine.get_execution_status(plan_id)
        
        print(f"Progress: {status['progress']['percentage']:.1f}%")
        print(f"  Done: {status['progress']['done']}")
        print(f"  Running: {status['progress']['running']}")
        print(f"  Pending: {status['progress']['pending']}")
        
        await asyncio.sleep(5)  # Обновлять каждые 5 секунд
    
    # Получить финальный результат
    result = await task
    return result
```

### Пример 3: Обработка ошибок с retry

```python
async def execute_with_retry(plan_id: str, max_retries: int = 3):
    exec_engine = get_execution_engine()
    
    for attempt in range(max_retries):
        try:
            result = await exec_engine.execute_plan(plan_id, ...)
            
            if result.status == "completed":
                return result
            
            # Частичный успех - попробовать retry failed subtasks
            if result.failed_subtasks > 0:
                logger.warning(
                    f"Attempt {attempt + 1}: "
                    f"{result.failed_subtasks} subtasks failed"
                )
                
                # Retry каждой failed subtask
                subtask_exec = get_subtask_executor()
                for subtask_id in result.errors.keys():
                    try:
                        await subtask_exec.retry_failed_subtask(
                            plan_id, subtask_id, ...
                        )
                    except Exception as e:
                        logger.error(f"Retry failed for {subtask_id}: {e}")
                
        except ExecutionEngineError as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    raise ExecutionEngineError("Max retries exceeded")
```

### Пример 4: Cancellation

```python
async def execute_with_timeout(plan_id: str, timeout_seconds: int = 300):
    exec_engine = get_execution_engine()
    
    # Запустить выполнение
    task = asyncio.create_task(
        exec_engine.execute_plan(plan_id, ...)
    )
    
    try:
        # Ждать с таймаутом
        result = await asyncio.wait_for(task, timeout=timeout_seconds)
        return result
        
    except asyncio.TimeoutError:
        # Отменить выполнение
        logger.warning(f"Plan execution timeout after {timeout_seconds}s")
        
        await exec_engine.cancel_execution(
            plan_id=plan_id,
            reason=f"Timeout after {timeout_seconds}s"
        )
        
        raise
```

---

## Best Practices

### 1. Dependency Injection

```python
# ✅ Хорошо: DI через конструктор
class MyService:
    def __init__(
        self,
        execution_engine: ExecutionEngine,
        plan_repository: PlanRepository
    ):
        self.execution_engine = execution_engine
        self.plan_repository = plan_repository

# ❌ Плохо: прямое создание
class MyService:
    def __init__(self):
        self.execution_engine = ExecutionEngine(...)  # Tight coupling
```

### 2. Error Handling

```python
# ✅ Хорошо: специфичные исключения
try:
    result = await exec_engine.execute_plan(...)
except ExecutionEngineError as e:
    # Обработка ошибок ExecutionEngine
    handle_execution_error(e)
except SubtaskExecutionError as e:
    # Обработка ошибок SubtaskExecutor
    handle_subtask_error(e)

# ❌ Плохо: общий Exception
try:
    result = await exec_engine.execute_plan(...)
except Exception as e:  # Слишком широко
    pass
```

### 3. Logging

```python
# ✅ Хорошо: структурированное логирование
logger.info(
    "Starting plan execution",
    extra={
        "plan_id": plan_id,
        "session_id": session_id,
        "subtasks_count": len(plan.subtasks)
    }
)

# ❌ Плохо: неструктурированное
logger.info(f"Starting plan {plan_id}")
```

### 4. Async/Await

```python
# ✅ Хорошо: правильное использование async/await
async def execute_plans(plan_ids: List[str]):
    tasks = [
        exec_engine.execute_plan(plan_id, ...)
        for plan_id in plan_ids
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

# ❌ Плохо: блокирующий вызов
def execute_plans(plan_ids: List[str]):
    results = []
    for plan_id in plan_ids:
        result = asyncio.run(exec_engine.execute_plan(plan_id, ...))  # Блокирует
        results.append(result)
    return results
```

### 5. Resource Management

```python
# ✅ Хорошо: контекстный менеджер для сессий
async with get_db_session() as session:
    plan_repo = PlanRepositoryImpl(session)
    exec_engine = ExecutionEngine(plan_repo, ...)
    result = await exec_engine.execute_plan(...)

# ❌ Плохо: ручное управление
session = get_db_session()
try:
    plan_repo = PlanRepositoryImpl(session)
    result = await exec_engine.execute_plan(...)
finally:
    session.close()  # Можно забыть
```

---

## Troubleshooting

### Проблема: "Plan not found"

```python
# Причина: план не существует или неправильный ID
# Решение: проверить существование плана
plan = await plan_repository.get_by_id(plan_id)
if not plan:
    raise ValueError(f"Plan {plan_id} not found")
```

### Проблема: "Plan is not approved"

```python
# Причина: план в статусе DRAFT
# Решение: утвердить план перед выполнением
plan.approve()
await plan_repository.update(plan)
```

### Проблема: "Circular dependencies detected"

```python
# Причина: циклические зависимости в плане
# Решение: проверить граф зависимостей
dep_resolver = DependencyResolver()
if dep_resolver.has_cyclic_dependencies(plan):
    # Исправить зависимости
    pass
```

### Проблема: "Agent not available"

```python
# Причина: целевой агент не зарегистрирован
# Решение: зарегистрировать агента
from app.domain.services.agent_registry import agent_registry

agent_registry.register_agent(coder_agent)
agent_registry.register_agent(debug_agent)
```

### Проблема: Медленное выполнение

```python
# Причина: низкий max_parallel_tasks
# Решение: увеличить параллелизм
exec_engine = ExecutionEngine(
    ...,
    max_parallel_tasks=5  # Было 3, стало 5
)
```

### Проблема: Memory leak

```python
# Причина: не освобождаются ресурсы после выполнения
# Решение: использовать контекстные менеджеры
async with get_execution_engine() as engine:
    result = await engine.execute_plan(...)
# Ресурсы автоматически освобождены
```

---

## Дополнительные ресурсы

- [Planning System Architecture](../../doc/planning-system-architecture.md)
- [Quick Start Guide](PLANNING_SYSTEM_QUICKSTART.md)
- [API Documentation](../../doc/api/)
- [Test Examples](../tests/test_execution_engine.py)

---

**Версия:** 1.0.0  
**Последнее обновление:** 2026-01-31  
**Автор:** CodeLab Team
