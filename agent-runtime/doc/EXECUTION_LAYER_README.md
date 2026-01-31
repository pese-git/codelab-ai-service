# Execution Layer - Quick Reference

> **TL;DR:** SubtaskExecutor выполняет одну подзадачу, ExecutionEngine координирует весь план

---

## 🚀 Quick Start

### Выполнить план

```python
from app.domain.services.execution_engine import ExecutionEngine

# Инициализация (обычно через DI)
execution_engine = get_execution_engine()

# Выполнить план
result = await execution_engine.execute_plan(
    plan_id="plan-123",
    session_id="session-456",
    session_service=session_service,
    stream_handler=stream_handler
)

# Проверить результат
if result.status == "completed":
    print(f"✅ Success! {result.completed_subtasks}/{result.total_subtasks}")
else:
    print(f"❌ Failed: {result.failed_subtasks} subtasks")
```

### Выполнить одну подзадачу

```python
from app.domain.services.subtask_executor import SubtaskExecutor

# Инициализация
subtask_executor = get_subtask_executor()

# Выполнить подзадачу
result = await subtask_executor.execute_subtask(
    plan_id="plan-123",
    subtask_id="subtask-456",
    session_id="session-789",
    session_service=session_service,
    stream_handler=stream_handler
)
```

---

## 📊 Компоненты

| Компонент | Назначение | Когда использовать |
|-----------|------------|-------------------|
| **ExecutionEngine** | Координация плана | Выполнение всего плана |
| **SubtaskExecutor** | Выполнение подзадачи | Retry, тестирование |
| **DependencyResolver** | Порядок выполнения | Валидация зависимостей |

---

## 🎯 API Reference

### ExecutionEngine

```python
# Выполнить план
result: ExecutionResult = await execute_plan(
    plan_id: str,
    session_id: str,
    session_service: SessionManagementService,
    stream_handler: IStreamHandler
)

# Получить статус
status: Dict = await get_execution_status(plan_id: str)

# Отменить выполнение
result: Dict = await cancel_execution(
    plan_id: str,
    reason: str
)
```

### SubtaskExecutor

```python
# Выполнить подзадачу
result: Dict = await execute_subtask(
    plan_id: str,
    subtask_id: str,
    session_id: str,
    session_service: SessionManagementService,
    stream_handler: IStreamHandler
)

# Повторить failed subtask
result: Dict = await retry_failed_subtask(
    plan_id: str,
    subtask_id: str,
    session_id: str,
    session_service: SessionManagementService,
    stream_handler: IStreamHandler
)

# Получить статус
status: Dict = await get_subtask_status(
    plan_id: str,
    subtask_id: str
)
```

---

## 💡 Примеры

### Пример 1: Базовое использование

```python
async def execute_my_plan():
    # 1. Получить компоненты
    exec_engine = get_execution_engine()
    
    # 2. Выполнить
    result = await exec_engine.execute_plan(
        plan_id="plan-123",
        session_id="session-456",
        session_service=session_service,
        stream_handler=stream_handler
    )
    
    # 3. Обработать результат
    print(f"Status: {result.status}")
    print(f"Duration: {result.duration_seconds}s")
    print(f"Success rate: {result.to_dict()['success_rate']}%")
```

### Пример 2: Мониторинг прогресса

```python
async def execute_with_monitoring(plan_id: str):
    exec_engine = get_execution_engine()
    
    # Запустить в фоне
    task = asyncio.create_task(
        exec_engine.execute_plan(plan_id, ...)
    )
    
    # Мониторить
    while not task.done():
        status = await exec_engine.get_execution_status(plan_id)
        print(f"Progress: {status['progress']['percentage']:.1f}%")
        await asyncio.sleep(5)
    
    return await task
```

### Пример 3: Retry failed subtasks

```python
async def execute_with_retry(plan_id: str):
    exec_engine = get_execution_engine()
    subtask_exec = get_subtask_executor()
    
    # Выполнить план
    result = await exec_engine.execute_plan(plan_id, ...)
    
    # Retry failed subtasks
    if result.failed_subtasks > 0:
        for subtask_id in result.errors.keys():
            try:
                await subtask_exec.retry_failed_subtask(
                    plan_id, subtask_id, ...
                )
            except Exception as e:
                logger.error(f"Retry failed: {e}")
```

---

## 🔍 Troubleshooting

| Ошибка | Причина | Решение |
|--------|---------|---------|
| "Plan not found" | Неверный plan_id | Проверить ID |
| "Plan is not approved" | Статус != APPROVED | plan.approve() |
| "Circular dependencies" | Циклы в графе | Исправить зависимости |
| "Agent not available" | Агент не зарегистрирован | agent_registry.register_agent() |

---

## 📚 Документация

- **Детальная архитектура:** [execution-engine-architecture.md](../../doc/execution-engine-architecture.md)
- **Руководство разработчика:** [EXECUTION_ENGINE_GUIDE.md](EXECUTION_ENGINE_GUIDE.md)
- **Примеры тестов:** [test_execution_engine.py](../tests/test_execution_engine.py)

---

## ✅ Checklist для интеграции

- [ ] Зарегистрировать все агенты в AgentRegistry
- [ ] Настроить PlanRepository с БД
- [ ] Создать ExecutionEngine с зависимостями
- [ ] Протестировать на простом плане
- [ ] Протестировать на плане с зависимостями
- [ ] Добавить мониторинг прогресса
- [ ] Настроить error handling
- [ ] Добавить логирование

---

**Версия:** 1.0.0  
**Дата:** 2026-01-31  
**Автор:** CodeLab Team
