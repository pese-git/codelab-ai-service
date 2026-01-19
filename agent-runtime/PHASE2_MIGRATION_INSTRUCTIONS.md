# Фаза 2: Миграция менеджеров - Детальные инструкции

**Дата:** 19 января 2026  
**Статус:** Готово к выполнению

---

## ⚠️ ВАЖНО

Эта фаза требует осторожных изменений в критическом коде.
Рекомендуется выполнять поэтапно с тестированием после каждого шага.

**Время:** 3-4 дня  
**Риск:** Средний  
**Требуется:** Полное регрессионное тестирование

---

## 📋 Фаза 2.3: Замена импортов в MultiAgentOrchestrator

### Файл: `app/services/multi_agent_orchestrator.py`

### Шаг 1: Обновить импорты менеджеров

**Строки 17-18 (было):**
```python
from app.services.agent_context_async import agent_context_manager
from app.services.session_manager_async import session_manager
```

**Заменить на:**
```python
# Используем адаптеры для постепенной миграции
from app.infrastructure.adapters import (
    SessionManagerAdapter,
    AgentContextManagerAdapter
)
```

### Шаг 2: Инициализировать адаптеры в main.py

**В lifespan startup, после инициализации сервисов:**
```python
# Initialize adapters for backward compatibility
from app.infrastructure.adapters import (
    SessionManagerAdapter,
    AgentContextManagerAdapter
)
from app.core.dependencies_new import (
    get_session_management_service,
    get_agent_orchestration_service
)

session_service = await get_session_management_service()
orchestration_service = await get_agent_orchestration_service()

# Create global adapter instances
global session_manager_adapter, agent_context_manager_adapter
session_manager_adapter = SessionManagerAdapter(session_service)
agent_context_manager_adapter = AgentContextManagerAdapter(orchestration_service)

logger.info("✓ Manager adapters initialized")
```

### Шаг 3: Обновить использование в MultiAgentOrchestrator

**Строка 65 (было):**
```python
from app.services.agent_context_async import agent_context_manager as async_ctx_mgr
```

**Заменить на:**
```python
# Используем глобальный адаптер
async_ctx_mgr = agent_context_manager_adapter
```

**Строка 111 (было):**
```python
from app.services.session_manager_async import session_manager as async_session_mgr
```

**Заменить на:**
```python
# Используем глобальный адаптер
async_session_mgr = session_manager_adapter
```

### Тестирование:
```bash
# Запустить тесты multi-agent системы
uv run pytest tests/test_multi_agent_system.py -v

# Должны пройти все тесты
```

---

## 📋 Фаза 2.4: Замена импортов в endpoints.py

### Файл: `app/api/v1/endpoints.py`

### Шаг 1: Обновить импорты

**Строка 64 (было):**
```python
from app.services.session_manager_async import session_manager as async_session_mgr
```

**Заменить на:**
```python
# Используем глобальный адаптер
from app.main import session_manager_adapter as async_session_mgr
```

### Шаг 2: Обновить все использования

Найти все места где используется `async_session_mgr` и убедиться что они работают с адаптером.

**Методы адаптера совместимы:**
- `get_or_create()` ✅
- `append_message()` ✅
- `append_tool_result()` ✅
- `get_history()` ✅

### Тестирование:
```bash
# Запустить API тесты
uv run pytest tests/test_main.py -v

# Проверить streaming endpoint
curl -X POST http://localhost:8001/agent/message/stream \
  -H "Content-Type: application/json" \
  -H "x-internal-auth: change-me-internal-key" \
  -d '{
    "session_id": "test-session",
    "message": {"type": "user_message", "content": "Test"}
  }'
```

---

## 📋 Фаза 2.5: Обновление тестов

### Файлы для обновления:

1. `tests/test_multi_agent_system.py`
2. `tests/test_session_manager.py`
3. `tests/test_main.py`

### Изменения в тестах:

**Было:**
```python
from app.services.session_manager_async import AsyncSessionManager

@pytest.fixture
async def session_manager():
    return AsyncSessionManager()
```

**Стало:**
```python
from app.infrastructure.adapters import SessionManagerAdapter
from app.domain.services import SessionManagementService

@pytest.fixture
async def session_manager(session_repository):
    service = SessionManagementService(session_repository)
    return SessionManagerAdapter(service)
```

### Тестирование:
```bash
# Запустить все тесты
uv run pytest tests/ -v

# Должны пройти ВСЕ тесты (включая старые)
```

---

## 📋 Фаза 2.6: Полное регрессионное тестирование

### Чеклист тестирования:

#### Unit тесты:
- [ ] `pytest tests/test_domain_base.py` - базовые классы
- [ ] `pytest tests/test_domain_entities.py` - доменные сущности
- [ ] `pytest tests/test_application_layer.py` - CQRS
- [ ] `pytest tests/test_infrastructure_repositories.py` - репозитории
- [ ] `pytest tests/test_resilience.py` - защитные механизмы

#### Integration тесты:
- [ ] `pytest tests/test_multi_agent_system.py` - мультиагентная система
- [ ] `pytest tests/test_session_manager.py` - session manager
- [ ] `pytest tests/test_main.py` - API endpoints

#### Manual тесты:
- [ ] Запустить сервис: `uvicorn app.main:app --reload`
- [ ] Проверить health: `GET /health`
- [ ] Проверить streaming: `POST /agent/message/stream`
- [ ] Проверить создание сессии: `POST /sessions`
- [ ] Проверить список сессий: `GET /sessions`
- [ ] Проверить переключение агента: `POST /agents/{id}/switch`

#### Проверка защитных механизмов:
- [ ] Session locks работают (параллельные запросы к одной сессии)
- [ ] Rate limiting работает (61-й запрос возвращает 429)
- [ ] Circuit breaker работает (при недоступности LLM)
- [ ] Cleanup service работает (логи каждый час)

#### Проверка совместимости:
- [ ] Gateway может подключиться
- [ ] Streaming работает как раньше
- [ ] Tool calls обрабатываются
- [ ] HITL работает
- [ ] Метрики собираются

---

## ⚠️ Риски и откат

### Если что-то сломалось:

**Быстрый откат:**
```bash
# Откатить последние коммиты
git revert HEAD~3..HEAD

# Или вернуться к конкретному коммиту
git checkout <commit-before-migration>
```

**Частичный откат:**
```python
# Вернуть старые импорты в конкретном файле
from app.services.session_manager_async import session_manager
# Вместо адаптера
```

---

## 📈 Метрики успеха

### После Фазы 2:

**Код:**
- Используется новая архитектура: 50%
- Старый код через адаптеры: 50%
- Готовность к полной миграции: 80%

**Тесты:**
- Все тесты проходят: 100%
- Новые тесты: 78
- Старые тесты: работают через адаптеры

**Производительность:**
- Нет деградации
- Защитные механизмы работают
- Memory leaks предотвращены

---

## 🎯 Рекомендации

### Выполнять поэтапно:

1. **День 1:** Фаза 2.3 (MultiAgentOrchestrator) + тестирование
2. **День 2:** Фаза 2.4 (endpoints.py) + тестирование
3. **День 3:** Фаза 2.5 (обновление тестов)
4. **День 4:** Фаза 2.6 (полное регрессионное тестирование)

### После каждого шага:
- Запускать тесты
- Проверять логи
- Тестировать вручную
- Коммитить изменения

---

## 🎉 Заключение

**Фаза 2 готова к выполнению!**

Адаптеры созданы и протестированы.
Можно начинать постепенную миграцию старого кода
на новую архитектуру через адаптеры.

**Это опциональный шаг - система уже работает отлично!**

---

**Автор:** AI Assistant  
**Дата:** 19 января 2026
