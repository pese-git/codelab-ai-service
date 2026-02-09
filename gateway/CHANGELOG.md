# Changelog - Gateway

Все значимые изменения в Gateway будут документированы в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- **Поддержка автоматического создания сессий** (2026-02-09)
  - WebSocket endpoint принимает временные session_id с префиксом `new_`
  - Условная передача session_id в Agent Runtime (не передается для временных ID)
  - Проксирование `session_info` чанка от Agent Runtime к IDE
  - Автоматическое обновление session_id после получения `session_info`
  - Детальное логирование для отладки процесса создания сессий
  - Документация: `GATEWAY_AUTO_SESSION_SUPPORT.md`
  - Тестовый скрипт: `test_auto_session.py`

### Changed
- **WebSocket endpoint** (`app/api/v1/endpoints.py`)
  - Добавлен флаг `is_temp_session` для определения типа сессии
  - Обновлена документация endpoint
  
- **WebSocketHandler** (`app/services/websocket/websocket_handler.py`)
  - Метод `handle_connection()` принимает параметр `is_temp_session`
  - Метод `_forward_to_agent()` условно формирует payload для Agent Runtime
  - Добавлено отслеживание и обновление session_id
  - Возвращает новый session_id из SSE stream
  
- **SSEStreamHandler** (`app/services/websocket/sse_stream_handler.py`)
  - Метод `process_stream()` возвращает новый session_id если получен
  - Метод `_forward_data()` обрабатывает `session_info` чанк
  - Добавлено логирование получения `session_info`

### Technical Details

#### Изменения в сигнатурах методов

**endpoints.py:**
```python
# Было:
await ws_handler.handle_connection(websocket, session_id)

# Стало:
is_temp_session = session_id.startswith("new_")
await ws_handler.handle_connection(websocket, session_id, is_temp_session)
```

**websocket_handler.py:**
```python
# Было:
async def handle_connection(self, websocket: WebSocket, session_id: str) -> None

# Стало:
async def handle_connection(
    self, websocket: WebSocket, session_id: str, is_temp_session: bool = False
) -> None

# Было:
async def _forward_to_agent(...) -> None

# Стало:
async def _forward_to_agent(..., is_temp_session: bool = False) -> str | None
```

**sse_stream_handler.py:**
```python
# Было:
async def process_stream(...) -> None

# Стало:
async def process_stream(...) -> str | None

# Было:
async def _forward_data(...) -> None

# Стало:
async def _forward_data(...) -> str | None
```

#### Логика обработки временных сессий

1. **Определение типа сессии:**
   ```python
   is_temp_session = session_id.startswith("new_")
   ```

2. **Формирование payload:**
   ```python
   if is_temp_session:
       payload = {"message": ide_msg}  # БЕЗ session_id
   else:
       payload = {"session_id": session_id, "message": ide_msg}
   ```

3. **Обработка session_info:**
   ```python
   if msg_type == "session_info":
       new_session_id = data.get('session_id')
       await websocket.send_json(filtered_data)  # Проксируем в IDE
       return new_session_id  # Возвращаем для обновления
   ```

4. **Обновление session_id:**
   ```python
   new_session_id = await self._forward_to_agent(...)
   if new_session_id and new_session_id != actual_session_id:
       actual_session_id = new_session_id
       is_temp_session = False
   ```

### Backward Compatibility

✅ **Полная обратная совместимость**

Все существующие клиенты, которые используют реальные session_id, продолжат работать без изменений. Новая функциональность активируется только при использовании временных ID с префиксом `new_`.

### Testing

Добавлен тестовый скрипт `test_auto_session.py` для проверки:
- Создания новой сессии с временным ID
- Получения session_info чанка
- Продолжения диалога с реальным session_id
- Подключения к существующей сессии

Запуск тестов:
```bash
python test_auto_session.py ws://localhost:8001/api/v1
```

### Integration

Gateway теперь полностью интегрирован с:
- **Agent Runtime** - поддерживает автоматическое создание сессий
- **IDE** - обрабатывает session_info чанк и сохраняет реальный session_id

### Documentation

- `GATEWAY_AUTO_SESSION_SUPPORT.md` - полная документация по реализации
- `../codelab_ide/doc/AUTO_SESSION_CREATION_PROTOCOL.md` - описание протокола

### Logging

Добавлено детальное логирование:
```
INFO: [new_1234567890] Temporary session ID detected, will create new session
INFO: [new_1234567890] WebSocket connected (temp=True)
INFO: [new_1234567890] Temporary session - NOT sending session_id to Agent Runtime
INFO: [new_1234567890] 🆔 Received session_info chunk: session_id=abc-123
INFO: [new_1234567890] Session ID updated: new_1234567890 -> abc-123
```

## [Previous Versions]

История изменений до внедрения автоматического создания сессий не документирована.
