# Changelog: HTTP Streaming Implementation for Agent Runtime

## Дата: 2025-12-27

### Обзор изменений

Реализована поддержка HTTP Streaming (SSE) архитектуры для Agent Runtime согласно плану из `doc/gateway-http-streaming-implementation-plan.md`.

### Основные изменения

#### 1. Модели данных (`app/models/schemas.py`)

**Добавлено:**
- `AgentStreamRequest` - модель для входящих запросов к streaming endpoint
  - Поддерживает как `user_message`, так и `tool_result`
  - Содержит `session_id` и `message` (Dict)
  
- `StreamChunk` - модель для SSE событий
  - Типы: `assistant_message`, `tool_call`, `error`, `done`
  - Поля для tool_call: `call_id`, `tool_name`, `arguments`
  - Поля для сообщений: `content`, `token`, `is_final`
  - Поле для ошибок: `error`

#### 2. Session Manager (`app/services/session_manager.py`)

**Добавлено:**
- `append_tool_result(session_id, tool_name, result)` - добавляет tool_result в историю как function message
- `get_history(session_id)` - возвращает историю сообщений в виде списка dict для передачи в LLM

**Назначение:**
- Поддержка полной истории диалога включая tool_call и tool_result
- Упрощенный API для работы с историей сессий

#### 3. LLM Stream Service (`app/services/llm_stream_service.py`)

**Полностью переписано:**
- Новая функция `stream_response(session_id, history)` - основная функция для streaming
  - Принимает историю сообщений
  - При получении tool_call от LLM - отправляет его в stream и **ЗАВЕРШАЕТ** генерацию
  - **НЕ** пытается выполнять tool локально
  - Возвращает `StreamChunk` объекты через async generator
  
- Старая функция `llm_stream()` помечена как DEPRECATED
  - Оставлена для обратной совместимости
  - Использует новую `stream_response()` внутри

**Ключевые изменения в логике:**
- Удален импорт `tool_call_handler` - tools больше не выполняются локально
- При tool_call:
  1. Добавляется assistant message с tool_call в историю
  2. Отправляется `StreamChunk` с типом `tool_call`
  3. Stream **завершается** (return)
  4. Ожидается следующий запрос с `tool_result`
- При обычном ответе:
  1. Добавляется assistant message в историю
  2. Отправляется `StreamChunk` с типом `assistant_message`

#### 4. API Endpoints (`app/api/v1/endpoints.py`)

**Добавлено:**
- Новый endpoint `POST /agent/message/stream` с SSE streaming
  - Использует `EventSourceResponse` из `sse-starlette`
  - Принимает `AgentStreamRequest`
  - Обрабатывает два типа сообщений:
    - `user_message` - добавляет в историю как user message
    - `tool_result` - добавляет в историю как function message через `append_tool_result()`
  - Генерирует SSE события через `stream_response()`
  - Отправляет события: `message` (с данными StreamChunk) и `done`
  - Обработка ошибок с отправкой `error` события

**Изменено:**
- Старый endpoint переименован в `/agent/message/stream/legacy`
- Помечен как DEPRECATED
- Оставлен для обратной совместимости

### Архитектурные изменения

#### Новый flow взаимодействия:

1. **User message:**
   ```
   Gateway → POST /agent/message/stream (SSE) → Agent
   Agent → SSE stream: assistant_message chunks
   ```

2. **Tool call:**
   ```
   Agent → SSE stream: tool_call event → завершение stream
   Gateway получает tool_call → отправляет в IDE
   ```

3. **Tool result:**
   ```
   IDE выполняет tool → отправляет tool_result в Gateway
   Gateway → POST /agent/message/stream (SSE) с tool_result → Agent
   Agent → SSE stream: assistant_message (продолжение)
   ```

#### Ключевые принципы:

- **Stateless streaming:** Каждый запрос создает новый SSE stream
- **Tool execution delegation:** Agent НЕ выполняет tools, только генерирует tool_call
- **History management:** SessionManager хранит полную историю включая tool_calls и results
- **Error handling:** Все ошибки отправляются как SSE события

### Обратная совместимость

- Старые endpoints сохранены с суффиксом `/legacy`
- `tool_call_handler.py` оставлен для старого кода (orchestrator, chat_service)
- Старая функция `llm_stream()` работает через новую `stream_response()`

### Зависимости

- `sse-starlette==1.6.5` - уже присутствует в `pyproject.toml`

### Тестирование

Код успешно компилируется:
```bash
python -m py_compile app/api/v1/endpoints.py app/models/schemas.py \
  app/services/session_manager.py app/services/llm_stream_service.py
```

### Следующие шаги

1. Интеграционное тестирование с Gateway
2. End-to-end тестирование полного flow с tool execution
3. Удаление deprecated кода после миграции Gateway
4. Performance тестирование streaming под нагрузкой

### Файлы изменены

- ✅ `app/models/schemas.py` - добавлены новые модели
- ✅ `app/services/session_manager.py` - добавлены методы для tool_result
- ✅ `app/services/llm_stream_service.py` - полностью переписан
- ✅ `app/api/v1/endpoints.py` - новый SSE endpoint

### Файлы НЕ изменены (для обратной совместимости)

- `app/services/tool_call_handler.py` - оставлен для старого кода
- `app/services/tool_registry.py` - используется orchestrator
- `app/services/orchestrator.py` - старая логика
- `app/services/chat_service.py` - старая логика

### Примечания

- Новый endpoint использует SSE (Server-Sent Events) для streaming
- Tool execution теперь полностью на стороне IDE через Gateway
- Agent только генерирует tool_call и ожидает tool_result
- История сессии включает все tool_calls и results для контекста LLM
