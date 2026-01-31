# Planning System - Quick Start

Быстрый старт для разработчиков, работающих с системой планирования.

---

## Что реализовано

### ✅ Базовые компоненты (50% готовности)

1. **TaskClassifier** - Классификация задач
2. **Plan Repository** - Персистентность планов
3. **FSM Orchestrator** - Управление состоянием
4. **DependencyResolver** - Разрешение зависимостей

### ⏳ В разработке

1. **SubtaskExecutor** - Запуск subtasks
2. **ExecutionEngine** - Координация исполнения
3. **Integration** - Интеграция с OrchestratorAgent

---

## Использование компонентов

### TaskClassifier

```python
from app.domain.services.task_classifier import TaskClassifier

classifier = TaskClassifier()

# Классифицировать задачу
classification = await classifier.classify("Create mobile app with login")

print(classification.is_atomic)  # False
print(classification.agent)      # "plan"
print(classification.confidence) # "high"
```

### Plan Repository

```python
from app.domain.repositories.plan_repository import PlanRepository
from app.infrastructure.persistence.repositories.plan_repository_impl import PlanRepositoryImpl

# Создать repository
repo = PlanRepositoryImpl(db_session)

# Сохранить план
await repo.save(plan)

# Найти активный план сессии
plan = await repo.find_by_session_id("session-123")

# Получить все планы сессии
plans = await repo.find_all_by_session_id("session-123", limit=10)
```

### FSM Orchestrator

```python
from app.domain.services.fsm_orchestrator import FSMOrchestrator
from app.domain.entities.fsm_state import FSMEvent, FSMState

orchestrator = FSMOrchestrator()

# Переход: IDLE -> CLASSIFY
new_state = await orchestrator.transition(
    "session-123",
    FSMEvent.RECEIVE_MESSAGE
)

# Проверить текущее состояние
state = orchestrator.get_current_state("session-123")

# Валидировать переход
can_transition = orchestrator.validate_transition(
    "session-123",
    FSMEvent.IS_ATOMIC_FALSE
)
```

### DependencyResolver

```python
from app.domain.services.dependency_resolver import DependencyResolver

resolver = DependencyResolver()

# Получить готовые subtasks
ready = resolver.get_ready_subtasks(plan)

# Проверить циклы
has_cycles = resolver.has_cyclic_dependencies(plan)

# Получить порядок выполнения
levels = resolver.get_execution_order(plan)
for i, level in enumerate(levels):
    print(f"Level {i}: {[st.description for st in level]}")
```

---

## Запуск тестов

```bash
# Все тесты планирования
cd codelab-ai-service/agent-runtime
uv run pytest tests/test_task_classifier.py tests/test_fsm_orchestrator.py -v

# Только TaskClassifier
uv run pytest tests/test_task_classifier.py -v

# Только FSM
uv run pytest tests/test_fsm_orchestrator.py -v

# С coverage
uv run pytest tests/test_task_classifier.py --cov=app/domain/services/task_classifier
```

---

## Структура файлов

```
app/
├── domain/
│   ├── entities/
│   │   ├── task_classification.py    # Модель классификации
│   │   ├── fsm_state.py               # FSM состояния и правила
│   │   └── plan.py                    # План и Subtask (уже был)
│   ├── repositories/
│   │   └── plan_repository.py         # Интерфейс репозитория
│   └── services/
│       ├── task_classifier.py         # Классификатор
│       ├── fsm_orchestrator.py        # FSM управление
│       └── dependency_resolver.py     # Resolver зависимостей
├── infrastructure/
│   └── persistence/
│       ├── models/
│       │   └── plan.py                # SQLAlchemy модели
│       ├── mappers/
│       │   └── plan_mapper.py         # Domain ↔ DB
│       └── repositories/
│           └── plan_repository_impl.py # Реализация
tests/
├── test_task_classifier.py            # 28 тестов
└── test_fsm_orchestrator.py           # 37 тестов
```

---

## Следующие шаги для разработчиков

### 1. SubtaskExecutor (следующий компонент)

Создать `app/domain/services/subtask_executor.py`:

```python
class SubtaskExecutor:
    async def execute(
        self,
        session_id: str,
        subtask: Subtask,
        plan: Plan
    ) -> str:
        """Исполнить subtask в целевом агенте"""
        # 1. Получить целевого агента
        # 2. Вызвать agent.process()
        # 3. Дождаться attempt_completion
        # 4. Вернуть результат
        pass
```

### 2. ExecutionEngine

Создать `app/domain/services/execution_engine.py`:

```python
class ExecutionEngine:
    async def execute_plan(
        self,
        session_id: str,
        plan: Plan
    ) -> ExecutionResult:
        """Исполнить весь план"""
        # 1. Валидировать план
        # 2. plan.start_execution()
        # 3. Цикл: пока есть pending subtasks
        #    - Получить ready subtasks
        #    - Запустить через SubtaskExecutor
        #    - Обновить статус
        # 4. plan.complete()
        pass
```

### 3. Интеграция с OrchestratorAgent

Обновить `app/agents/orchestrator_agent.py`:

```python
class OrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(...)
        self.fsm = FSMOrchestrator()
        self.classifier = TaskClassifier()
        self.execution_engine = ExecutionEngine()
    
    async def process(self, ...):
        # 1. FSM: IDLE -> CLASSIFY
        await self.fsm.transition(session_id, FSMEvent.RECEIVE_MESSAGE)
        
        # 2. Классифицировать
        classification = await self.classifier.classify(message)
        
        # 3. Принять решение
        if classification.is_atomic:
            # Атомарная задача
            await self.fsm.transition(session_id, FSMEvent.IS_ATOMIC_TRUE)
            yield switch_to_agent(classification.agent)
        else:
            # Сложная задача → планирование
            await self.fsm.transition(session_id, FSMEvent.IS_ATOMIC_FALSE)
            await self.fsm.transition(session_id, FSMEvent.ROUTE_TO_ARCHITECT)
            yield switch_to_agent(AgentType.ARCHITECT)
```

---

## Полезные ссылки

- **Архитектура:** `/doc/planning-system-architecture.md`
- **FSM Design:** `/doc/fsm-orchestrator-design.md`
- **Execution Engine Design:** `/doc/execution-engine-design.md`
- **Task Classifier Design:** `/doc/task-classifier-design.md`
- **Plan Repository Design:** `/doc/plan-repository-design.md`
- **Implementation Report:** `/doc/PLANNING_SYSTEM_IMPLEMENTATION_REPORT.md`

---

## Контакты

**Вопросы:** Sergey Penkovsky  
**Ветка:** `feature/planning-system`  
**Статус:** Базовые компоненты готовы, интеграция в процессе
