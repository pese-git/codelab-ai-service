# Протокол WebSocket взаимодействия Gateway ↔ IDE

Документ описывает формат сообщений и логику обмена данными между сервисом Gateway и клиентом (IDE) по протоколу WebSocket. Используется для интеграции IDE с агентом посредством Gateway.

## Эндпоинт

- `ws://<gateway_host>/ws/{session_id}`

Где `session_id` — уникальный идентификатор сессии пользователя.

## Основные типы сообщений

### 1. Сообщение пользователя (от IDE к Gateway)

```json
{
  "type": "user_message",
  "content": "Текст сообщения пользователя",
  "role": "user" // Возможные значения: "user", "assistant", "system", "tool"
}
```

### 2. Ответ агента (от Gateway к IDE)

Пример стримингового ответа ассистента:
```json
{ "type": "assistant_message", "token": "Текст", "is_final": false }
{ "type": "assistant_message", "token": " завершён.", "is_final": true }
```

#### Типы ответов:
- `type: "assistant_message"` — сообщение ассистента. Может передаваться чанками ("is_final": false/true).
- `type: "tool_call"` — команда от ассистента на вызов инструмента в IDE (см. ниже).

---

### 3. Tool Calls (интеграция с инструментами IDE)

#### Запрос на вызов инструмента (от Gateway к IDE)

```json
{
  "type": "tool_call",
  "call_id": "call_abc123",
  "tool_name": "read_file",
  "arguments": { "path": "/src/main.py" }
}
```
- `call_id` — уникальный идентификатор вызова (correlation id)
- `tool_name` — имя инструмента (определено на стороне IDE)
- `arguments` — параметры вызова (структура зависит от инструмента)

#### Ответ на вызов инструмента (от IDE к Gateway)

```json
{
  "type": "tool_result",
  "call_id": "call_abc123",
  "result": { "content": "file content here" }
}
```
или, в случае ошибки:
```json
{
  "type": "tool_result",
  "call_id": "call_abc123",
  "error": "File not found"
}
```

---

### 4. Сообщения об ошибках
Если отправленное сообщение некорректно или что-то пошло не так:
```json
{
  "type": "error",
  "content": "Описание ошибки"
}
```

---

## Сценарий работы WebSocket-сессии
1. Клиент (IDE) устанавливает соединение на `/ws/{session_id}`.
2. Отправляет WSUserMessage (например, вопрос пользователя или команду).
3. Получает стриминговые ответы (`assistant_message`), а также, при необходимости, команды на tool call (`tool_call`).
4. На каждый `tool_call` IDE должна отправить `tool_result` с тем же `call_id`.
5. В случае ошибок — IDE или Gateway возвращает сообщение с `type: "error"`.

---

## Pydantic-схемы сообщений

В кодовой базе все схемы для WebSocket находятся в файле `gateway/app/models/websocket.py`.

- `WSUserMessage` — пользовательское сообщение
- `WSToolCall` — запрос на вызов инструмента
- `WSToolResult` — ответ от инструмента
- `WSErrorResponse` — сообщение об ошибке

---

## Требования
- Все сообщения только в формате JSON (валидные по Pydantic-схемам)
- Поле `type` обязательно для любого сообщения
- Неизвестные или некорректные типы сообщений будут отвергнуты сервисом
- Tool-цепочка поддерживает несколько одновременных вызовов (correlation по call_id)

---

## Пример полного диалога

1. IDE → Gateway:
```json
{ "type": "user_message", "content": "Открой файл main.py", "role": "user" }
```
2. Gateway → IDE:
```json
{ "type": "assistant_message", "token": "Открываю ", "is_final": false }
{ "type": "assistant_message", "token": "main.py...", "is_final": true }
{ "type": "tool_call", "call_id": "call_abc123", "tool_name": "read_file", "arguments": { "path": "main.py" } }
```
3. IDE → Gateway:
```json
{ "type": "tool_result", "call_id": "call_abc123", "result": { "content": "// file content here" } }
```
4. Gateway → IDE:
```json
{ "type": "assistant_message", "token": "Файл прочитан", "is_final": true }
```
