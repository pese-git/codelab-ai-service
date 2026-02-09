# Gateway: Поддержка автоматического создания сессий

## Обзор

Gateway обновлен для поддержки нового протокола автоматического создания сессий. Теперь IDE может открывать WebSocket соединения как с существующими session_id, так и с временными ID для новых диалогов.

## Архитектура

```
IDE (WebSocket) ←→ Gateway (WebSocket→SSE) ←→ Agent Runtime (SSE)
```

### Поток данных

#### Новая сессия (с временным ID)
```
1. IDE → Gateway: WebSocket /ws/new_1234567890
2. IDE → Gateway: user_message через WebSocket
3. Gateway → Agent Runtime: POST /agent/message/stream БЕЗ session_id
4. Agent Runtime → Gateway: SSE stream с session_info чанком
5. Gateway → IDE: Проксирует session_info через WebSocket
6. Gateway: Обновляет внутренний session_id
7. IDE → Gateway: Следующее сообщение
8. Gateway → Agent Runtime: POST /agent/message/stream С session_id
```

#### Существующая сессия
```
1. IDE → Gateway: WebSocket /ws/abc-123
2. IDE → Gateway: user_message через WebSocket
3. Gateway → Agent Runtime: POST /agent/message/stream С session_id
4. Agent Runtime → Gateway: SSE stream БЕЗ session_info
5. Gateway → IDE: Проксирует события через WebSocket
```

## Реализованные изменения

### 1. WebSocket Endpoint (`endpoints.py`)

**Изменения:**
- Принимает временные session_id с префиксом `new_`
- Определяет тип сессии (временная/существующая)
- Передает флаг `is_temp_session` в WebSocketHandler

**Код:**
```python
@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    ...
):
    # Проверяем, является ли это временным session_id
    is_temp_session = session_id.startswith("new_")
    
    if is_temp_session:
        logger.info(f"[{session_id}] Temporary session ID detected")
    
    # Регистрируем сессию (даже временную)
    await session_manager.add(session_id, websocket)
    
    try:
        await ws_handler.handle_connection(websocket, session_id, is_temp_session)
    finally:
        # Очистка ресурсов
        await token_buffer_manager.remove(session_id)
        await session_manager.remove(session_id)
```

### 2. WebSocketHandler (`websocket_handler.py`)

**Изменения:**
- Принимает флаг `is_temp_session`
- Отслеживает обновление session_id
- Условно передает session_id в Agent Runtime

**Ключевые методы:**

#### `handle_connection()`
```python
async def handle_connection(
    self,
    websocket: WebSocket,
    session_id: str,
    is_temp_session: bool = False
) -> None:
    # Храним реальный session_id после получения session_info
    actual_session_id = session_id
    
    async with httpx.AsyncClient(timeout=self._stream_timeout) as client:
        while True:
            raw_msg = await websocket.receive_text()
            message = self._parser.parse(raw_msg)
            
            # Пересылаем в Agent Runtime
            new_session_id = await self._forward_to_agent(
                client, websocket, actual_session_id, 
                message, raw_msg, is_temp_session
            )
            
            # Обновляем session_id если получили новый
            if new_session_id and new_session_id != actual_session_id:
                logger.info(f"Session ID updated: {actual_session_id} -> {new_session_id}")
                actual_session_id = new_session_id
                is_temp_session = False  # Больше не временная
```

#### `_forward_to_agent()`
```python
async def _forward_to_agent(
    self,
    client: httpx.AsyncClient,
    websocket: WebSocket,
    session_id: str,
    message: WSMessage,
    raw_msg: str,
    is_temp_session: bool = False
) -> str | None:
    ide_msg = json.loads(raw_msg)
    
    # Формируем payload для Agent Runtime
    if is_temp_session:
        # Для временных сессий НЕ передаем session_id
        payload = {"message": ide_msg}
        logger.info(f"[{session_id}] NOT sending session_id to Agent Runtime")
    else:
        # Для существующих сессий передаем session_id
        payload = {"session_id": session_id, "message": ide_msg}
    
    async with client.stream(
        "POST",
        f"{self._agent_runtime_url}/agent/message/stream",
        json=payload,
        headers={"X-Internal-Auth": self._internal_api_key},
    ) as response:
        # Обрабатываем SSE stream
        new_session_id = await self._sse_handler.process_stream(
            response, websocket, session_id
        )
        return new_session_id
```

### 3. SSEStreamHandler (`sse_stream_handler.py`)

**Изменения:**
- Обрабатывает `session_info` чанк
- Проксирует `session_info` в IDE
- Возвращает новый session_id

**Ключевые методы:**

#### `process_stream()`
```python
async def process_stream(
    self,
    response: httpx.Response,
    websocket: WebSocket,
    session_id: str
) -> str | None:
    new_session_id = None
    
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            data_str = line[6:]
            
            # Может вернуть session_id если это session_info чанк
            session_info_id = await self._forward_data(
                data_str, current_event_type, websocket, session_id
            )
            
            if session_info_id:
                new_session_id = session_info_id
    
    return new_session_id
```

#### `_forward_data()`
```python
async def _forward_data(
    self,
    data_str: str,
    event_type: str,
    websocket: WebSocket,
    session_id: str
) -> str | None:
    data = json.loads(data_str)
    msg_type = data.get('type')
    
    # Обрабатываем session_info чанк
    if msg_type == "session_info":
        new_session_id = data.get('session_id')
        logger.info(f"[{session_id}] 🆔 Received session_info: {new_session_id}")
        
        # Пересылаем session_info в IDE
        await websocket.send_json(filtered_data)
        
        # Возвращаем новый session_id
        return new_session_id
    
    # Пересылаем другие события
    await websocket.send_json(filtered_data)
    return None
```

## Логирование

### Новая сессия
```
INFO: [new_1234567890] Temporary session ID detected, will create new session
INFO: [new_1234567890] WebSocket connected (temp=True)
INFO: [new_1234567890] Temporary session - NOT sending session_id to Agent Runtime
INFO: [new_1234567890] 🆔 Received session_info chunk: session_id=abc-123
INFO: [new_1234567890] Session ID updated: new_1234567890 -> abc-123
INFO: [abc-123] Sending session_id to Agent Runtime
```

### Существующая сессия
```
INFO: [abc-123] WebSocket connected (temp=False)
INFO: [abc-123] Sending session_id to Agent Runtime
```

## Тестирование

### Тест 1: Создание новой сессии

**Шаги:**
1. Открыть WebSocket: `ws://gateway/ws/new_1234567890`
2. Отправить user_message
3. Проверить получение session_info чанка
4. Отправить второе сообщение
5. Проверить использование реального session_id

**Ожидаемый результат:**
- Первый запрос к Agent Runtime БЕЗ session_id
- Получен session_info чанк с реальным session_id
- Второй запрос к Agent Runtime С реальным session_id

### Тест 2: Продолжение существующей сессии

**Шаги:**
1. Открыть WebSocket: `ws://gateway/ws/abc-123`
2. Отправить user_message
3. Проверить отсутствие session_info чанка

**Ожидаемый результат:**
- Запрос к Agent Runtime С session_id
- НЕТ session_info чанка в ответе

### Тест 3: Переключение между сообщениями

**Шаги:**
1. Открыть WebSocket с временным ID
2. Отправить 3 сообщения подряд
3. Проверить логи Gateway

**Ожидаемый результат:**
- Первое сообщение: БЕЗ session_id → получен session_info
- Второе сообщение: С реальным session_id
- Третье сообщение: С реальным session_id

## Обратная совместимость

✅ **Полная обратная совместимость**

Старый код, который открывает WebSocket с реальным session_id, продолжит работать без изменений:

```python
# Это все еще работает
websocket = await connect("ws://gateway/ws/abc-123")
await websocket.send(user_message)
```

## Интеграция с другими компонентами

### IDE
- ✅ Генерирует временные ID (`new_*`)
- ✅ Обрабатывает `session_info` чанк
- ✅ Сохраняет реальный session_id

### Agent Runtime
- ✅ Принимает запросы БЕЗ session_id
- ✅ Создает сессию автоматически
- ✅ Отправляет `session_info` чанк

### Gateway
- ✅ Принимает временные session_id
- ✅ Условно передает session_id
- ✅ Проксирует `session_info` чанк

## Статус

✅ **Gateway обновлен и готов к работе**

### Реализовано
- [x] Обработка временных session_id (`new_*`)
- [x] Условная передача session_id в Agent Runtime
- [x] Проксирование `session_info` чанка
- [x] Обновление внутреннего session_id
- [x] Логирование для отладки
- [x] Документация

### Следующие шаги
1. Развернуть обновленный Gateway
2. Провести интеграционное тестирование
3. Мониторинг логов в production

## Примеры использования

### Python (IDE клиент)
```python
import websockets
import json

# Создание новой сессии
async with websockets.connect("ws://gateway/ws/new_1234567890") as ws:
    # Отправляем первое сообщение
    await ws.send(json.dumps({
        "type": "user_message",
        "role": "user",
        "content": "Привет!"
    }))
    
    # Получаем session_info
    response = await ws.recv()
    data = json.loads(response)
    if data["type"] == "session_info":
        real_session_id = data["session_id"]
        print(f"Получен реальный session_id: {real_session_id}")
    
    # Отправляем второе сообщение (Gateway автоматически использует реальный ID)
    await ws.send(json.dumps({
        "type": "user_message",
        "role": "user",
        "content": "Как дела?"
    }))
```

### Dart (IDE)
```dart
// Создание новой сессии
final tempSessionId = 'new_${DateTime.now().millisecondsSinceEpoch}';
final channel = WebSocketChannel.connect(
  Uri.parse('ws://gateway/ws/$tempSessionId'),
);

// Отправляем первое сообщение
channel.sink.add(jsonEncode({
  'type': 'user_message',
  'role': 'user',
  'content': 'Привет!',
}));

// Слушаем session_info
channel.stream.listen((message) {
  final data = jsonDecode(message);
  if (data['type'] == 'session_info') {
    final realSessionId = data['session_id'];
    print('Получен реальный session_id: $realSessionId');
  }
});
```

## Диагностика проблем

### Проблема: session_info не приходит

**Причины:**
1. Agent Runtime не отправляет session_info
2. SSEStreamHandler не проксирует чанк
3. IDE не обрабатывает session_info

**Решение:**
```bash
# Проверить логи Gateway
docker logs gateway | grep "session_info"

# Проверить логи Agent Runtime
docker logs agent-runtime | grep "session_info"
```

### Проблема: session_id не обновляется

**Причины:**
1. WebSocketHandler не получает новый session_id от SSEStreamHandler
2. Логика обновления не срабатывает

**Решение:**
```bash
# Проверить логи Gateway
docker logs gateway | grep "Session ID updated"
```

### Проблема: Второе сообщение отправляется без session_id

**Причины:**
1. Флаг `is_temp_session` не обновляется после получения session_info
2. Логика условной передачи работает неправильно

**Решение:**
```bash
# Проверить логи Gateway
docker logs gateway | grep "sending session_id"
```

## Ссылки

- [AUTO_SESSION_CREATION_PROTOCOL.md](../../codelab_ide/doc/AUTO_SESSION_CREATION_PROTOCOL.md) - Полное описание протокола
- [Agent Runtime Implementation](../agent-runtime/app/domain/services/message_processor.py) - Реализация в Agent Runtime
- [IDE Implementation](../../codelab_ide/packages/codelab_ai_assistant/) - Реализация в IDE
