# Changelog: HTTP Streaming Implementation

## Дата: 2025-12-27

### Изменения в Gateway

#### Удалено:
1. **Endpoint `/tool/execute/{session_id}`** - синхронный HTTP endpoint для выполнения tool calls
2. **Файл `app/services/tool_result_manager.py`** - менеджер для хранения pending tool results
3. **Зависимость `get_tool_result_manager()`** из `app/core/dependencies.py`

#### Изменено:

1. **`app/api/v1/endpoints.py`**:
   - Удален endpoint `/tool/execute/{session_id}`
   - Полностью переработан WebSocket endpoint `/ws/{session_id}`:
     - Теперь использует HTTP streaming (SSE) для связи с Agent
     - Поддерживает двунаправленную связь: user_message и tool_result от IDE
     - Пересылает SSE события от Agent в IDE через WebSocket
     - Удалена зависимость от ToolResultManager
   - Удален импорт `WSToolCall` (больше не используется в Gateway)
   - Удален импорт `stream_agent_single` (логика встроена в WebSocket endpoint)

2. **`app/core/config.py`**:
   - Добавлен параметр `AGENT_STREAM_TIMEOUT` (по умолчанию 60.0 секунд)
   - Используется для управления таймаутами HTTP streaming соединений

3. **`app/core/dependencies.py`**:
   - Удалена функция `get_tool_result_manager()`
   - Удален импорт `ToolResultManager`

### Новая архитектура

**Старый flow:**
```
IDE → WS → Gateway → POST /agent/message/stream → Agent (блокируется)
Agent → POST /tool/execute/{session_id} → Gateway (блокируется 30 сек) → WS → IDE
IDE → WS → Gateway → возвращает результат в Agent
```

**Новый flow:**
```
IDE → WS → Gateway → POST /agent/message/stream (SSE) → Agent
Agent → SSE events → Gateway → WS → IDE
IDE → WS (tool_result) → Gateway → POST /agent/message/stream (SSE) → Agent
Agent → SSE events → Gateway → WS → IDE
```

### Преимущества:

1. **Нет блокировки**: Gateway не блокируется в ожидании tool results
2. **Настоящий streaming**: SSE события пересылаются в реальном времени
3. **Упрощенная архитектура**: Меньше кода, меньше состояния
4. **Лучшая производительность**: Нет таймаутов на 30 секунд
5. **Масштабируемость**: Gateway теперь stateless relay

### Обратная совместимость:

- Модели данных `WSUserMessage`, `WSToolResult`, `WSErrorResponse` остались без изменений
- SessionManager и TokenBufferManager продолжают работать как раньше
- Файл `stream_service.py` оставлен для обратной совместимости с тестами

### Требования к Agent Runtime:

Agent Runtime должен поддерживать:
1. HTTP streaming endpoint `/agent/message/stream` с SSE форматом
2. Прием как `user_message`, так и `tool_result` через один endpoint
3. Отправку событий в формате SSE: `data: {json}\n\n`

### Конфигурация:

Новые переменные окружения:
- `GATEWAY__AGENT_STREAM_TIMEOUT` - таймаут для HTTP streaming (по умолчанию 60.0)

Существующие переменные (без изменений):
- `GATEWAY__AGENT_URL` - URL Agent Runtime
- `GATEWAY__INTERNAL_API_KEY` - ключ для внутренней аутентификации
- `GATEWAY__LOG_LEVEL` - уровень логирования
- `GATEWAY__REQUEST_TIMEOUT` - таймаут для обычных HTTP запросов
