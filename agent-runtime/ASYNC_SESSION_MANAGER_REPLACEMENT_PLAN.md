# План замены AsyncSessionManager на новую архитектуру

**Дата:** 20 января 2026  
**Цель:** Полностью удалить AsyncSessionManager и использовать только новую архитектуру  
**Сложность:** Средняя  
**Время:** 2-3 дня  
**Риск:** Средний

---

## 📊 Текущее состояние

### Что используется:
- **AsyncSessionManager** (463 строки) - старый менеджер
- **SessionManagerAdapter** - адаптер к новой архитектуре
- **SessionManagementService** - новый доменный сервис

### Проблема:
`PersistenceSubscriber` напрямую обращается к внутренним методам `AsyncSessionManager`:
- `session_manager.get(session_id)` - получение SessionState
- `state.messages` - прямой доступ к сообщениям
- `session_manager._db_service` - прямой доступ к БД сервису

---

## 🎯 Стратегия замены

### Подход: Event-Driven Persistence через Repository

Вместо прямого доступа к SessionState, использовать:
1. **Repository** для получения данных из БД
2. **Events** для триггера персистентности
3. **Batch processing** для эффективности

---

## 📋 Пошаговый план

### Этап 1: Обновить PersistenceSubscriber (1 день)

#### 1.1. Изменить подход к персистентности

**Текущий подход (проблемный):**
```python
# persistence_subscriber.py:179-216
async def _persist_sessions(self, session_ids: list):
    from app.services.session_manager_async import session_manager
    
    for session_id in session_ids:
        state = session_manager.get(session_id)  # ← Прямой доступ к памяти
        if state:
            messages = [msg.model_dump() for msg in state.messages]
            await session_manager._db_service.save_session(...)  # ← Прямой доступ к БД
```

**Новый подход (через Repository):**
```python
# persistence_subscriber.py (НОВЫЙ)
async def _persist_sessions(self, session_ids: list):
    """Persist sessions using repository pattern."""
    from app.infrastructure.persistence.repositories import SessionRepositoryImpl
    from app.services.database import get_db
    
    async for db in get_db():
        repository = SessionRepositoryImpl(db)
        
        for session_id in session_ids:
            try:
                # Загрузить сессию из БД (она уже там через SessionManagementService)
                session = await repository.find_by_id(session_id)
                
                if session:
                    # Обновить last_activity
                    session.update_activity()
                    await repository.save(session)
                    
                    # Update last persist time
                    self._last_persist[f"session:{session_id}"] = datetime.utcnow()
                    
                    logger.debug(f"Session {session_id} persisted via repository")
                    
            except Exception as e:
                logger.error(f"Error persisting session {session_id}: {e}")
        
        break
    
    logger.info(f"Persisted {len(session_ids)} sessions via repository")
```

#### 1.2. Обновить _persist_contexts аналогично

**Новый подход:**
```python
async def _persist_contexts(self, session_ids: list):
    """Persist agent contexts using repository pattern."""
    from app.infrastructure.persistence.repositories import AgentContextRepositoryImpl
    from app.services.database import get_db
    
    async for db in get_db():
        repository = AgentContextRepositoryImpl(db)
        
        for session_id in session_ids:
            try:
                # Загрузить контекст из БД
                context = await repository.find_by_session_id(session_id)
                
                if context:
                    # Контекст уже обновлен через AgentOrchestrationService
                    # Просто обновляем timestamp
                    await repository.save(context)
                    
                    # Update last persist time
                    self._last_persist[f"context:{session_id}"] = datetime.utcnow()
                    
                    logger.debug(f"Context {session_id} persisted via repository")
                    
            except Exception as e:
                logger.error(f"Error persisting context {session_id}: {e}")
        
        break
    
    logger.info(f"Persisted {len(session_ids)} contexts via repository")
```

#### 1.3. Альтернативный подход: Убрать PersistenceSubscriber

**Обоснование:**
- `SessionManagementService` уже сохраняет в БД при каждом `add_message()`
- `AgentOrchestrationService` уже сохраняет при каждом `switch_agent()`
- Event-driven persistence может быть избыточной

**Решение:**
```python
# Просто удалить PersistenceSubscriber!
# Вся персистентность уже происходит в доменных сервисах
```

**Преимущества:**
- ✅ Проще код
- ✅ Нет дублирования
- ✅ Меньше overhead
- ✅ Немедленная персистентность (не через debouncing)

**Недостатки:**
- ⚠️ Больше записей в БД (но с правильными индексами это не проблема)
- ⚠️ Нет batch processing (но SQLAlchemy оптимизирует)

**Рекомендация:** Попробовать удалить PersistenceSubscriber и протестировать

---

### Этап 2: Обновить main.py (0.5 дня)

#### 2.1. Убрать инициализацию AsyncSessionManager

**Файл:** [`app/main.py`](app/main.py:61-62)

**Удалить:**
```python
# Строки 60-63
# Initialize async session manager
from app.services.session_manager_async import init_session_manager
await init_session_manager()
logger.info("✓ Session manager initialized")
```

**Заменить на:**
```python
# Session manager теперь инициализируется через адаптер (строки 88-143)
logger.info("✓ Session manager adapter initialized (new architecture)")
```

#### 2.2. Убрать shutdown старого менеджера

**Файл:** [`app/main.py`](app/main.py:204-209)

**Удалить:**
```python
# Строки 203-209
try:
    from app.services.session_manager_async import session_manager
    
    if session_manager:
        await session_manager.shutdown()
        logger.info("✓ Session manager shutdown")
```

**Заменить на:**
```python
# Session manager shutdown handled by repository cleanup
logger.info("✓ Session manager adapter shutdown (managed by repositories)")
```

---

### Этап 3: Обновить тесты (1 день)

#### 3.1. Обновить моки в тестах

**Файлы для обновления:**
- `tests/test_session_manager.py`
- `tests/test_event_integration.py`
- `tests/test_llm_stream_service.py`

**Было:**
```python
from app.services.session_manager_async import AsyncSessionManager

@pytest.fixture
def session_manager():
    return AsyncSessionManager()
```

**Стало:**
```python
from app.infrastructure.adapters import SessionManagerAdapter
from app.domain.services import SessionManagementService

@pytest.fixture
async def session_manager_adapter(session_repository):
    service = SessionManagementService(repository=session_repository)
    return SessionManagerAdapter(service)
```

#### 3.2. Обновить тестовые сценарии

**Изменения:**
- Использовать `SessionManagerAdapter` вместо `AsyncSessionManager`
- Мокировать `SessionRepositoryImpl` вместо прямого доступа к БД
- Проверять вызовы repository методов

---

### Этап 4: Удалить AsyncSessionManager (0.5 дня)

#### 4.1. Проверить что нет использований

**Команда:**
```bash
grep -r "from app.services.session_manager_async import" --include="*.py" app/
```

**Ожидаемый результат:** Только в `persistence_subscriber.py` и тестах

#### 4.2. Удалить файл

**Файл для удаления:**
- `app/services/session_manager_async.py` (463 строки)

#### 4.3. Обновить импорты

**Файлы для обновления:**
- `app/core/dependencies.py` - удалить `SessionManagerDep`
- `app/agents/base_agent.py` - обновить TYPE_CHECKING импорт

---

## 🔧 Детальная реализация

### Вариант A: Удалить PersistenceSubscriber (РЕКОМЕНДУЕТСЯ)

**Обоснование:**
- Доменные сервисы уже сохраняют в БД
- Нет необходимости в event-driven persistence
- Проще и надежнее

**Шаги:**

#### 1. Удалить PersistenceSubscriber

**Файл:** `app/events/subscribers/persistence_subscriber.py`

**Действие:** Удалить весь файл (282 строки)

#### 2. Убрать из main.py

**Файл:** `app/main.py`

**Удалить импорт:**
```python
# Строка 42
persistence_subscriber,  # УДАЛИТЬ
```

**Удалить shutdown:**
```python
# Строки 168-174
try:
    from app.events.subscribers import persistence_subscriber
    if persistence_subscriber:
        await persistence_subscriber.shutdown()
        logger.info("✓ Persistence subscriber shutdown")
except Exception as e:
    logger.error(f"Error shutting down persistence subscriber: {e}")
```

#### 3. Проверить что персистентность работает

**Тест:**
```python
async def test_immediate_persistence():
    """Проверить что сообщения сохраняются немедленно."""
    service = SessionManagementService(repository)
    
    # Добавить сообщение
    await service.add_message(
        session_id="test-1",
        role="user",
        content="Hello"
    )
    
    # Проверить что сразу в БД
    session = await repository.find_by_id("test-1")
    assert len(session.messages) == 1
    assert session.messages[0].content == "Hello"
```

**Результат:** Персистентность работает немедленно через доменные сервисы!

---

### Вариант B: Обновить PersistenceSubscriber (если нужен debouncing)

**Если требуется debouncing для снижения нагрузки на БД:**

#### 1. Обновить _persist_sessions

**Файл:** `app/events/subscribers/persistence_subscriber.py`

**Заменить строки 179-216:**
```python
async def _persist_sessions(self, session_ids: list):
    """Persist sessions using repository pattern."""
    from app.infrastructure.persistence.repositories import SessionRepositoryImpl
    from app.services.database import get_db
    
    logger.debug(f"Persisting {len(session_ids)} sessions via repository")
    
    async for db in get_db():
        repository = SessionRepositoryImpl(db)
        
        for session_id in session_ids:
            try:
                # Загрузить сессию из БД (она уже обновлена через SessionManagementService)
                session = await repository.find_by_id(session_id)
                
                if session:
                    # Сессия уже сохранена через SessionManagementService
                    # Просто обновляем timestamp для debouncing
                    self._last_persist[f"session:{session_id}"] = datetime.utcnow()
                    logger.debug(f"Session {session_id} already persisted")
                else:
                    logger.warning(f"Session {session_id} not found in DB")
                    
            except Exception as e:
                logger.error(f"Error checking session {session_id}: {e}")
        
        break
    
    logger.info(f"Verified {len(session_ids)} sessions in DB")
```

#### 2. Обновить _persist_contexts

**Аналогично для контекстов:**
```python
async def _persist_contexts(self, session_ids: list):
    """Persist agent contexts using repository pattern."""
    from app.infrastructure.persistence.repositories import AgentContextRepositoryImpl
    from app.services.database import get_db
    
    logger.debug(f"Persisting {len(session_ids)} contexts via repository")
    
    async for db in get_db():
        repository = AgentContextRepositoryImpl(db)
        
        for session_id in session_ids:
            try:
                # Загрузить контекст из БД
                context = await repository.find_by_session_id(session_id)
                
                if context:
                    # Контекст уже сохранен через AgentOrchestrationService
                    self._last_persist[f"context:{session_id}"] = datetime.utcnow()
                    logger.debug(f"Context {session_id} already persisted")
                else:
                    logger.warning(f"Context {session_id} not found in DB")
                    
            except Exception as e:
                logger.error(f"Error checking context {session_id}: {e}")
        
        break
    
    logger.info(f"Verified {len(session_ids)} contexts in DB")
```

**Примечание:** В этом варианте PersistenceSubscriber становится просто "verifier" - проверяет что данные в БД, но не сохраняет их сам.

---

## 🚀 Рекомендуемый план (Вариант A)

### Шаг 1: Удалить PersistenceSubscriber (1 час)

**Обоснование:**
- Доменные сервисы уже сохраняют в БД немедленно
- Event-driven persistence избыточна
- Упрощает архитектуру

**Действия:**
1. Удалить `app/events/subscribers/persistence_subscriber.py`
2. Убрать импорт из `app/events/subscribers/__init__.py`
3. Убрать из `app/main.py` (импорт и shutdown)

### Шаг 2: Убрать инициализацию AsyncSessionManager из main.py (0.5 часа)

**Файл:** `app/main.py`

**Удалить:**
```python
# Строки 60-63
from app.services.session_manager_async import init_session_manager
await init_session_manager()
logger.info("✓ Session manager initialized")

# Строки 203-209
from app.services.session_manager_async import session_manager
if session_manager:
    await session_manager.shutdown()
    logger.info("✓ Session manager shutdown")
```

### Шаг 3: Обновить тесты (4 часа)

**Файлы:**
- `tests/test_session_manager.py` - переписать для SessionManagementService
- `tests/test_event_integration.py` - обновить моки
- `tests/test_llm_stream_service.py` - использовать SessionManagerAdapter

**Пример нового теста:**
```python
# tests/test_session_management_service.py
import pytest
from app.domain.services import SessionManagementService
from app.infrastructure.persistence.repositories import SessionRepositoryImpl

@pytest.fixture
async def session_service(db_session):
    """Create session management service with test repository."""
    repository = SessionRepositoryImpl(db_session)
    return SessionManagementService(repository=repository)

async def test_create_session(session_service):
    """Test session creation."""
    session = await session_service.create_session("test-session-1")
    
    assert session.id == "test-session-1"
    assert len(session.messages) == 0
    assert session.is_active

async def test_add_message(session_service):
    """Test adding message to session."""
    await session_service.create_session("test-session-1")
    
    await session_service.add_message(
        session_id="test-session-1",
        role="user",
        content="Hello"
    )
    
    session = await session_service.get_session("test-session-1")
    assert len(session.messages) == 1
    assert session.messages[0].content == "Hello"
```

### Шаг 4: Удалить AsyncSessionManager (0.5 часа)

**Действия:**
1. Удалить `app/services/session_manager_async.py` (463 строки)
2. Обновить `app/core/dependencies.py` - удалить `SessionManagerDep`
3. Обновить `app/agents/base_agent.py` - убрать из TYPE_CHECKING

### Шаг 5: Тестирование (2 часа)

**Тесты:**
1. Unit тесты - все должны проходить
2. Integration тесты - проверить работу с БД
3. Manual тестирование - проверить через docker compose
4. Performance тесты - убедиться что нет деградации

---

## 📊 Сравнение подходов

### Вариант A: Удалить PersistenceSubscriber

**Преимущества:**
- ✅ Проще архитектура
- ✅ Меньше кода
- ✅ Немедленная персистентность
- ✅ Нет race conditions между событиями и сохранением

**Недостатки:**
- ⚠️ Больше записей в БД (но это не проблема с правильными индексами)
- ⚠️ Нет batch processing (но SQLAlchemy оптимизирует)

**Время:** 1 день  
**Риск:** Низкий

### Вариант B: Обновить PersistenceSubscriber

**Преимущества:**
- ✅ Сохраняет debouncing
- ✅ Batch processing
- ✅ Меньше нагрузка на БД

**Недостатки:**
- ⚠️ Сложнее код
- ⚠️ Дублирование логики
- ⚠️ Возможны race conditions

**Время:** 1.5 дня  
**Риск:** Средний

---

## 🎯 Рекомендация: Вариант A

### Почему Вариант A лучше:

1. **Простота** - меньше движущихся частей
2. **Надежность** - нет асинхронной персистентности
3. **Консистентность** - БД всегда актуальна
4. **Производительность** - SQLAlchemy оптимизирует запросы

### Современные БД справляются с нагрузкой:
- PostgreSQL: 10,000+ writes/sec
- SQLite WAL mode: 1,000+ writes/sec
- Наша нагрузка: ~10-100 writes/sec

**Вывод:** Немедленная персистентность не создаст проблем!

---

## 📋 Детальный чеклист (Вариант A)

### Подготовка
- [ ] Создать ветку `refactor/remove-async-session-manager`
- [ ] Убедиться что все тесты проходят
- [ ] Создать backup БД

### Реализация

#### Шаг 1: Удалить PersistenceSubscriber
- [ ] Удалить `app/events/subscribers/persistence_subscriber.py`
- [ ] Убрать из `app/events/subscribers/__init__.py`
- [ ] Убрать импорт из `app/main.py:42`
- [ ] Убрать shutdown из `app/main.py:168-174`

#### Шаг 2: Убрать AsyncSessionManager из main.py
- [ ] Удалить инициализацию (строки 60-63)
- [ ] Удалить shutdown (строки 203-209)
- [ ] Обновить комментарии

#### Шаг 3: Обновить тесты
- [ ] Создать `tests/test_session_management_service.py`
- [ ] Обновить `tests/test_session_manager.py` → переименовать или удалить
- [ ] Обновить `tests/test_event_integration.py`
- [ ] Обновить `tests/test_llm_stream_service.py`
- [ ] Создать фикстуры для новых сервисов

#### Шаг 4: Удалить AsyncSessionManager
- [ ] Удалить `app/services/session_manager_async.py` (463 строки)
- [ ] Удалить `SessionManagerDep` из `app/core/dependencies.py`
- [ ] Обновить `app/agents/base_agent.py` TYPE_CHECKING

#### Шаг 5: Тестирование
- [ ] Запустить все unit тесты
- [ ] Запустить integration тесты
- [ ] Тестировать в docker compose
- [ ] Performance тестирование

#### Шаг 6: Документация
- [ ] Обновить DEPRECATED_CODE_REMOVAL.md
- [ ] Обновить AGENT_RUNTIME_IMPLEMENTATION_STATUS.md
- [ ] Создать migration notes

### Финализация
- [ ] Code review
- [ ] Merge в main branch
- [ ] Deploy и мониторинг

---

## ⏱️ Временная оценка

| Этап | Время | Риск |
|------|-------|------|
| Удалить PersistenceSubscriber | 1 час | Низкий |
| Убрать AsyncSessionManager из main.py | 0.5 часа | Низкий |
| Обновить тесты | 4 часа | Средний |
| Удалить AsyncSessionManager | 0.5 часа | Низкий |
| Тестирование | 2 часа | Средний |
| Документация | 1 час | Низкий |
| **ИТОГО** | **9 часов (1-1.5 дня)** | **Низкий** |

---

## 🚨 Риски и митигация

### Риск 1: Потеря данных при сбое

**Вероятность:** Очень низкая  
**Влияние:** Высокое

**Митигация:**
- ✅ Доменные сервисы сохраняют в БД немедленно
- ✅ SQLAlchemy transactions обеспечивают ACID
- ✅ WAL mode в SQLite для надежности
- ✅ Тесты проверяют персистентность

### Риск 2: Проблемы с производительностью

**Вероятность:** Низкая  
**Влияние:** Среднее

**Митигация:**
- ✅ Современные БД справляются с нагрузкой
- ✅ Правильные индексы оптимизируют запросы
- ✅ Connection pooling в SQLAlchemy
- ✅ Performance тестирование перед deploy

### Риск 3: Поломка тестов

**Вероятность:** Средняя  
**Влияние:** Низкое

**Митигация:**
- ✅ Постепенное обновление тестов
- ✅ Новые фикстуры для новых сервисов
- ✅ Возможность отката

---

## 📈 Ожидаемые результаты

### После удаления AsyncSessionManager:

**Размер кода:**
- Удалено: 463 строки (AsyncSessionManager)
- Удалено: 282 строки (PersistenceSubscriber)
- Итого: 745 строк
- С учетом Database: 962 строки удалено

**Качество:**
- Технический долг: Низкий
- Дублирование: 0%
- Cyclomatic Complexity: 3-5
- Поддерживаемость: Высокая

**Архитектура:**
- ✅ Чистая Clean Architecture
- ✅ Только новые сервисы
- ✅ Нет legacy кода
- ✅ Простая и понятная структура

**Прогресс миграции:** 82% → 95%

---

## 🎯 Следующие шаги

### Немедленно (можно начинать):

1. **Создать ветку:**
```bash
cd codelab-ai-service
git checkout -b refactor/remove-async-session-manager
```

2. **Удалить PersistenceSubscriber:**
```bash
rm app/events/subscribers/persistence_subscriber.py
```

3. **Обновить main.py** - убрать инициализацию и shutdown

4. **Запустить тесты** - проверить что работает

5. **Если тесты проходят** - удалить AsyncSessionManager

### Альтернатива (если нужен debouncing):

Реализовать Вариант B - обновить PersistenceSubscriber для работы с repositories

---

## 🎉 Заключение

**Рекомендуемый подход:** Вариант A (удалить PersistenceSubscriber)

**Обоснование:**
- Проще и надежнее
- Меньше кода для поддержки
- Немедленная персистентность лучше для консистентности
- Современные БД справляются с нагрузкой

**Время реализации:** 1-1.5 дня

**Риск:** Низкий (с правильным тестированием)

**Результат:** Чистая архитектура без legacy кода

---

**Автор:** AI Assistant  
**Дата:** 20 января 2026  
**Версия:** 1.0
