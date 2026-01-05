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

### 3. HITL (Human-in-the-Loop) - Одобрение инструментов

#### Tool Call с требованием одобрения (от Gateway к IDE)

Когда агент хочет выполнить опасную операцию (запись файла, выполнение команды), он отправляет tool_call с флагом `requires_approval`:

```json
{
  "type": "tool_call",
  "call_id": "call_abc123",
  "tool_name": "write_file",
  "arguments": { "path": "/src/main.py", "content": "..." },
  "requires_approval": true
}
```

#### Решение пользователя (от IDE к Gateway)

IDE должна показать пользователю запрос на одобрение и отправить решение:

**Одобрить (approve):**
```json
{
  "type": "hitl_decision",
  "call_id": "call_abc123",
  "decision": "approve"
}
```

**Редактировать и одобрить (edit):**
```json
{
  "type": "hitl_decision",
  "call_id": "call_abc123",
  "decision": "edit",
  "modified_arguments": { "path": "/src/main_v2.py", "content": "..." }
}
```

**Отклонить (reject):**
```json
{
  "type": "hitl_decision",
  "call_id": "call_abc123",
  "decision": "reject",
  "feedback": "This operation is too risky"
}
```

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
- `WSToolCall` — запрос на вызов инструмента (с поддержкой `requires_approval`)
- `WSToolResult` — ответ от инструмента
- `WSHITLDecision` — решение пользователя по HITL (approve/edit/reject)
- `WSErrorResponse` — сообщение об ошибке
- `WSAgentSwitched` — уведомление о переключении агента
- `WSSwitchAgent` — запрос на переключение агента

---

## Требования
- Все сообщения только в формате JSON (валидные по Pydantic-схемам)
- Поле `type` обязательно для любого сообщения
- Неизвестные или некорректные типы сообщений будут отвергнуты сервисом
- Tool-цепочка поддерживает несколько одновременных вызовов (correlation по call_id)

---

## Примеры полных диалогов

### Обычный диалог (без HITL)

1. IDE → Gateway:
```json
{ "type": "user_message", "content": "Открой файл main.py", "role": "user" }
```
2. Gateway → IDE:
```json
{ "type": "assistant_message", "token": "Открываю ", "is_final": false }
{ "type": "assistant_message", "token": "main.py...", "is_final": true }
{ "type": "tool_call", "call_id": "call_abc123", "tool_name": "read_file", "arguments": { "path": "main.py" }, "requires_approval": false }
```
3. IDE → Gateway:
```json
{ "type": "tool_result", "call_id": "call_abc123", "result": { "content": "// file content here" } }
```
4. Gateway → IDE:
```json
{ "type": "assistant_message", "token": "Файл прочитан", "is_final": true }
```

### Диалог с HITL (пользователь одобрил)

1. IDE → Gateway:
```json
{ "type": "user_message", "content": "Создай файл test.py с кодом", "role": "user" }
```
2. Gateway → IDE (tool_call требует одобрения):
```json
{ "type": "assistant_message", "token": "Создаю файл...", "is_final": true }
{ "type": "tool_call", "call_id": "call_xyz789", "tool_name": "write_file", "arguments": { "path": "test.py", "content": "print('hello')" }, "requires_approval": true }
```
3. IDE показывает пользователю запрос на одобрение
4. IDE → Gateway (пользователь одобрил):
```json
{ "type": "hitl_decision", "call_id": "call_xyz789", "decision": "approve" }
```
5. Gateway → IDE (продолжение после одобрения):
```json
{ "type": "assistant_message", "token": "Файл создан успешно", "is_final": true }
```

### Диалог с HITL (пользователь отредактировал)

1-2. (аналогично предыдущему примеру)
3. IDE → Gateway (пользователь изменил параметры):
```json
{ "type": "hitl_decision", "call_id": "call_xyz789", "decision": "edit", "modified_arguments": { "path": "test_modified.py", "content": "print('hello world')" } }
```
4. Gateway → IDE:
```json
{ "type": "assistant_message", "token": "Файл test_modified.py создан с вашими изменениями", "is_final": true }
```

### Диалог с HITL (пользователь отклонил)

1-2. (аналогично предыдущему примеру)
3. IDE → Gateway (пользователь отклонил):
```json
{ "type": "hitl_decision", "call_id": "call_xyz789", "decision": "reject", "feedback": "Не хочу создавать этот файл" }
```
4. Gateway → IDE:
```json
{ "type": "assistant_message", "token": "Понял, не буду создавать файл. Что-то еще?", "is_final": true }
```
