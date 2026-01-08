# План рефакторинга Compatibility Layer в Agent Runtime

## Обзор

Compatibility proxy классы ([`session_manager.py`](app/services/session_manager.py:1), [`agent_context.py`](app/services/agent_context.py:1)) были созданы для обеспечения обратной совместимости при миграции на async архитектуру. Эти классы оставлены для:

1. **Агентов** - используют sync интерфейс для доступа к сессиям
2. **Streaming endpoint** - работает стабильно с текущим интерфейсом
3. **Backward compatibility** - поддержка существующего кода

Их удаление требует глубокого рефакторинга всех агентов и связанных сервисов.

## Текущее состояние

### Файлы Compatibility Layer

1. **[`app/services/session_manager.py`](app/services/session_manager.py:1)** (188 строк)
   - Proxy класс для [`AsyncSessionManager`](app/services/session_manager_async.py:18)
   - Предоставляет sync интерфейс через делегирование к async версии
   - Использует `asyncio.create_task()` для фоновых операций

2. **[`app/services/agent_context.py`](app/services/agent_context.py:1)** (155 строк)
   - Proxy класс для [`AsyncAgentContextManager`](app/services/agent_context_async.py:130)
   - Предоставляет sync интерфейс для управления контекстом агентов
   - Использует `asyncio.create_task()` для фоновых операций

### Места использования Compatibility Layer

#### 1. Агенты (4 файла)
- [`app/agents/architect_agent.py`](app/agents/architect_agent.py:13) - строка 13, 75, 95
- [`app/agents/coder_agent.py`](app/agents/coder_agent.py:12) - строка 12, 67
- [`app/agents/ask_agent.py`](app/agents/ask_agent.py:13) - строка 13, 70, 90
- [`app/agents/debug_agent.py`](app/agents/debug_agent.py:13) - строка 13, 71, 91

**Паттерн использования в агентах:**
```python
from app.services.session_manager import session_manager

# В методе process():
history = session_manager.get_history(session_id)  # Sync вызов
session_manager.append_tool_result(...)  # Sync вызов
```

#### 2. API Endpoints (1 файл)
- [`app/api/v1/endpoints.py`](app/api/v1/endpoints.py:18) - строки 18, 65, 160, 209, 278, 309

**Паттерн использования в endpoints:**
```python
from app.services.session_manager import session_manager  # Fallback

# В async функциях:
session = session_manager.get_or_create(request.session_id)  # Sync вызов в async контексте
session_manager.append_message(...)  # Sync вызов
session_manager.append_tool_result(...)  # Sync вызов
```

#### 3. LLM Stream Service (1 файл)
- [`app/services/llm_stream_service.py`](app/services/llm_stream_service.py:1) - использует async manager напрямую

**Текущая реализация:**
```python
# Уже использует async интерфейс правильно
async def stream_response(
    session_id: str,
    history: List[dict],
    allowed_tools: Optional[List[str]] = None,
    session_mgr: Optional[AsyncSessionManager] = None
):
    # Получает async manager
    if session_mgr is None:
        from app.services.session_manager_async import session_manager as global_mgr
        session_mgr = global_mgr
```

#### 4. Тесты (2 файла)
- [`tests/test_session_manager.py`](tests/test_session_manager.py:1) - 26 использований
- [`tests/test_llm_stream_service.py`](tests/test_llm_stream_service.py:1) - 7 использований

## Проблемы текущей архитектуры

### 1. Смешивание sync/async кода
- Агенты используют sync интерфейс в async контексте
- Proxy классы пытаются определить event loop и адаптироваться
- Риск race conditions и непредсказуемого поведения

### 2. Неявное поведение
- Proxy классы скрывают async операции за sync интерфейсом
- Персистентность происходит в фоне через `asyncio.create_task()`
- Сложно отследить, когда данные реально сохранены

### 3. Дублирование кода
- Два набора классов для одной функциональности
- Увеличенная сложность поддержки
- Потенциальные расхождения в поведении

### 4. Производительность
- Дополнительный слой абстракции
- Неоптимальное использование async/await
- Лишние проверки event loop

## План рефакторинга

### Фаза 1: Подготовка (Анализ завершен ✓)

**Цель:** Понять все места использования и зависимости

**Задачи:**
- ✅ Найти все импорты compatibility layer
- ✅ Проанализировать паттерны использования
- ✅ Определить критические точки
- ✅ Создать план миграции

### Фаза 2: Рефакторинг агентов

**Цель:** Перевести все агенты на async интерфейс

**Изменения в базовом классе:**

```python
# app/agents/base_agent.py
class BaseAgent:
    async def process(
        self, 
        session_id: str,
        message: str,
        context: Dict[str, Any],
        session_mgr: AsyncSessionManager  # Добавить параметр
    ) -> AsyncGenerator[StreamChunk, None]:
        """Process message with async session manager"""
        pass
```

**Изменения в каждом агенте (4 файла):**

1. **Удалить импорт compatibility layer:**
   ```python
   # УДАЛИТЬ:
   from app.services.session_manager import session_manager
   
   # НЕ НУЖНО добавлять импорт - session_mgr передается как параметр
   ```

2. **Обновить сигнатуру метода `process()`:**
   ```python
   async def process(
       self, 
       session_id: str,
       message: str,
       context: Dict[str, Any],
       session_mgr: AsyncSessionManager  # Добавить параметр
   ) -> AsyncGenerator[StreamChunk, None]:
   ```

3. **Использовать переданный session_mgr:**
   ```python
   # БЫЛО:
   history = session_manager.get_history(session_id)
   session_manager.append_tool_result(...)
   
   # СТАЛО:
   history = session_mgr.get_history(session_id)
   await session_mgr.append_tool_result(...)  # Добавить await
   ```

**Файлы для изменения:**
- [`app/agents/architect_agent.py`](app/agents/architect_agent.py:1)
- [`app/agents/coder_agent.py`](app/agents/coder_agent.py:1)
- [`app/agents/ask_agent.py`](app/agents/ask_agent.py:1)
- [`app/agents/debug_agent.py`](app/agents/debug_agent.py:1)
- [`app/agents/orchestrator_agent.py`](app/agents/orchestrator_agent.py:1) (если использует)

### Фаза 3: Обновление Multi-Agent Orchestrator

**Цель:** Передавать async session manager в агенты

**Изменения в [`app/services/multi_agent_orchestrator.py`](app/services/multi_agent_orchestrator.py:1):**

```python
class MultiAgentOrchestrator:
    def __init__(self):
        self._agent_router = agent_router
        # Получить async session manager при инициализации
        from app.services.session_manager_async import session_manager
        self._session_mgr = session_manager
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        agent_type: Optional[AgentType] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        # ...
        
        # Передать session_mgr в агент
        async for chunk in agent.process(
            session_id=session_id,
            message=message,
            context=context_dict,
            session_mgr=self._session_mgr  # Передать async manager
        ):
            yield chunk
```

### Фаза 4: Обновление API Endpoints

**Цель:** Использовать async интерфейс напрямую через DI

**Изменения в [`app/api/v1/endpoints.py`](app/api/v1/endpoints.py:1):**

1. **Удалить fallback импорт:**
   ```python
   # УДАЛИТЬ:
   from app.services.session_manager import session_manager  # Fallback for non-DI code
   ```

2. **Использовать только DI или прямой доступ к async manager:**
   ```python
   # В функциях, где уже есть DI - использовать его
   async def message_stream_sse(
       request: AgentStreamRequest,
       session_mgr: SessionManagerDep  # Уже есть через DI
   ):
       # Использовать session_mgr напрямую
       session = await session_mgr.get_or_create(...)
       await session_mgr.append_message(...)
   
   # В функциях без DI - получить async manager
   async def some_function():
       from app.services.session_manager_async import session_manager
       if session_manager is None:
           raise RuntimeError("SessionManager not initialized")
       
       session = await session_manager.get_or_create(...)
   ```

3. **Добавить await для всех async операций:**
   - `await session_mgr.get_or_create()`
   - `await session_mgr.append_message()`
   - `await session_mgr.append_tool_result()`

**Места для изменения:**
- Строка 65: `session_manager.get_or_create()` → `await session_mgr.get_or_create()`
- Строка 160: `session_manager.append_tool_result()` → `await session_mgr.append_tool_result()`
- Строка 209: `session_manager.append_tool_result()` → `await session_mgr.append_tool_result()`
- Строка 278: `session_manager.append_message()` → `await session_mgr.append_message()`
- Строка 309: `session_manager.append_message()` → `await session_mgr.append_message()`

### Фаза 5: Обновление LLM Stream Service

**Цель:** Убедиться, что сервис корректно работает с async manager

**Текущее состояние:** [`app/services/llm_stream_service.py`](app/services/llm_stream_service.py:1) уже использует async интерфейс правильно.

**Проверить:**
- ✅ Параметр `session_mgr: Optional[AsyncSessionManager]` присутствует
- ✅ Используется `await session_mgr.append_message()`
- ⚠️ Строка 166-168: Прямое изменение `session_state.messages` - нужно заменить на `await session_mgr.append_message()`

**Изменения:**
```python
# БЫЛО (строки 166-168):
session_state = session_mgr.get(session_id)
if session_state:
    session_state.messages.append(assistant_msg)

# СТАЛО:
# Сохранить assistant message через session manager
await session_mgr.append_message(
    session_id=session_id,
    role="assistant",
    content=None  # Для tool_calls content может быть None
)
# Затем добавить tool_calls к последнему сообщению
session_state = session_mgr.get(session_id)
if session_state and session_state.messages:
    session_state.messages[-1] = assistant_msg
```

### Фаза 6: Обновление тестов

**Цель:** Адаптировать тесты к async интерфейсу

**Изменения в [`tests/test_session_manager.py`](tests/test_session_manager.py:1):**

1. **Изменить импорт:**
   ```python
   # БЫЛО:
   from app.services.session_manager import session_manager
   
   # СТАЛО:
   from app.services.session_manager_async import session_manager
   ```

2. **Добавить async/await:**
   ```python
   # БЫЛО:
   def test_create_session():
       session_manager.create(session_id)
       assert session_manager.exists(session_id)
   
   # СТАЛО:
   async def test_create_session():
       await session_manager.create(session_id)
       assert session_manager.exists(session_id)
   ```

3. **Обновить все тесты на async:**
   - Добавить `async` к определениям функций
   - Добавить `await` к вызовам `create()`, `append_message()`, `append_tool_result()`, `delete()`
   - Sync методы (`get()`, `exists()`, `get_history()`) оставить без `await`

**Изменения в [`tests/test_llm_stream_service.py`](tests/test_llm_stream_service.py:1):**

1. **Обновить моки для async методов:**
   ```python
   # Для async методов использовать AsyncMock
   mock_session_manager.append_message = AsyncMock()
   mock_session_manager.append_tool_result = AsyncMock()
   ```

2. **Проверить вызовы async методов:**
   ```python
   # Проверка вызова async метода
   mock_session_manager.append_message.assert_called_once_with(
       session_id, "assistant", "Hi there!"
   )
   ```

### Фаза 7: Удаление Compatibility Layer

**Цель:** Удалить proxy классы после успешной миграции

**Файлы для удаления:**
1. [`app/services/session_manager.py`](app/services/session_manager.py:1) (188 строк)
2. [`app/services/agent_context.py`](app/services/agent_context.py:1) (155 строк)

**Перед удалением проверить:**
- ✅ Все агенты используют async интерфейс
- ✅ Все endpoints используют async интерфейс
- ✅ Все тесты обновлены и проходят
- ✅ Нет импортов удаляемых файлов

**Команда для проверки:**
```bash
# Проверить, что нет импортов compatibility layer
grep -r "from app.services.session_manager import" codelab-ai-service/agent-runtime/app/
grep -r "from app.services.agent_context import" codelab-ai-service/agent-runtime/app/
```

### Фаза 8: Финальная проверка

**Цель:** Убедиться, что система работает корректно

**Проверки:**

1. **Запуск тестов:**
   ```bash
   cd codelab-ai-service/agent-runtime
   pytest tests/ -v
   ```

2. **Проверка линтером:**
   ```bash
   ruff check app/
   mypy app/
   ```

3. **Интеграционное тестирование:**
   - Запустить сервис
   - Создать сессию
   - Отправить сообщение
   - Проверить tool calls
   - Проверить HITL workflow
   - Проверить переключение агентов
   - Проверить персистентность (перезапуск сервиса)

4. **Проверка производительности:**
   - Измерить время отклика
   - Проверить использование памяти
   - Проверить отсутствие утечек памяти

## Риски и митигация

### Риск 1: Нарушение работы streaming endpoint
**Вероятность:** Средняя  
**Влияние:** Критическое  
**Митигация:**
- Тщательное тестирование после каждой фазы
- Сохранить compatibility layer до полной проверки
- Возможность быстрого отката

### Риск 2: Race conditions в async коде
**Вероятность:** Низкая  
**Влияние:** Высокое  
**Митигация:**
- Использовать `asyncio.Lock` где необходимо
- Тщательный code review
- Нагрузочное тестирование

### Риск 3: Проблемы с персистентностью
**Вероятность:** Низкая  
**Влияние:** Среднее  
**Митигация:**
- Проверить все вызовы `await` для операций с БД
- Тестировать сценарии с перезапуском
- Проверить background writer

### Риск 4: Сломанные тесты
**Вероятность:** Высокая  
**Влияние:** Низкое  
**Митигация:**
- Обновлять тесты параллельно с кодом
- Использовать pytest-asyncio
- Проверять coverage

## Преимущества после рефакторинга

### 1. Чистая архитектура
- Единый async интерфейс
- Явные async операции
- Предсказуемое поведение

### 2. Улучшенная производительность
- Удаление лишнего слоя абстракции
- Оптимальное использование async/await
- Меньше overhead

### 3. Упрощенная поддержка
- Меньше кода для поддержки
- Один источник истины
- Проще отладка

### 4. Лучшая типизация
- Явные async типы
- Лучшая поддержка IDE
- Меньше ошибок типов

## Оценка трудозатрат

| Фаза | Задачи | Время | Риск |
|------|--------|-------|------|
| 1. Подготовка | Анализ, планирование | ✅ Завершено | Низкий |
| 2. Рефакторинг агентов | 4-5 файлов | 2-3 часа | Средний |
| 3. Обновление orchestrator | 1 файл | 1 час | Средний |
| 4. Обновление endpoints | 1 файл | 1-2 часа | Высокий |
| 5. Обновление llm_stream | 1 файл | 30 мин | Низкий |
| 6. Обновление тестов | 2 файла | 2-3 часа | Средний |
| 7. Удаление compatibility | 2 файла | 15 мин | Низкий |
| 8. Финальная проверка | Тестирование | 2-3 часа | Средний |
| **ИТОГО** | | **9-13 часов** | |

## Порядок выполнения

1. ✅ **Фаза 1:** Анализ и планирование (завершено)
2. **Фаза 2:** Рефакторинг агентов (начать здесь)
3. **Фаза 3:** Обновление orchestrator
4. **Фаза 4:** Обновление endpoints
5. **Фаза 5:** Обновление llm_stream_service
6. **Фаза 6:** Обновление тестов
7. **Фаза 7:** Удаление compatibility layer
8. **Фаза 8:** Финальная проверка

## Критерии успеха

- ✅ Все агенты используют async интерфейс
- ✅ Все endpoints используют async интерфейс
- ✅ Все тесты проходят
- ✅ Compatibility layer удален
- ✅ Нет регрессий в функциональности
- ✅ Производительность не ухудшилась
- ✅ Code coverage сохранен или улучшен

## Следующие шаги

1. Начать с **Фазы 2: Рефакторинг агентов**
2. Обновить базовый класс [`BaseAgent`](app/agents/base_agent.py:1)
3. Обновить каждый агент по очереди
4. Тестировать после каждого изменения
5. Переходить к следующей фазе только после успешного завершения текущей

---

**Дата создания:** 2026-01-08  
**Автор:** AI Assistant  
**Статус:** План готов к реализации
