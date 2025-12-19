# Расширенный протокол обмена с AI-агентом через WebSocket

Документ описывает **расширенный протокол** для сложных кейсов: многошаговое планирование, reasoning (chain-of-thought), chain- и multi-agent-ориентированных сценариев в IDE.

## Зачем это нужно
- Поддержка многошагового reasoning (План + пошаговое выполнение)
- Возможность визуализировать размышления/шаги агента в клиенте
- Расширенная обратная связь, статус прогресса reasoning, контроль цепочек инструментов
- Мгновенное стриминг-обновление прогресса, поддержка мультиагентов

---

## Поддержка Human-in-the-Loop (HITL)

### Зачем нужен режим HITL
Human-in-the-Loop (HITL) позволяет реализовать безопасное выполнение потенциально опасных или критичных действий (записи в файл, выполнение кода, run SQL и др.) с обязательным ручным подтверждением на стороне пользователя.

- Агенты/сервер могут помечать tool_call как требующие HITL (requires_approval: true)
- Клиент (IDE) показывает диалог-подтверждение для действия — утверждение/редактирование/отклонение
- Сервис reasoning блокируется до ответа человека
- Действие продолжается только после hitl_response

### Пример flow

1. Сервер/агент присылает tool_call с requires_approval:
```json
{
  "type": "tool_call",
  "call_id": "call_999",
  "tool_name": "write_file",
  "arguments": { "path": "main.py", "content": "..." },
  "requires_approval": true,
  "plan_id": "plan-abc",
  "step_id": "3"
}
```
2. IDE показывает пользователю подтверждение:
   "Вы уверены?"
   - [Approve]  [Edit/Change params]  [Reject]
3. Пользователь выбирает действие. IDE отправляет hitl_response:
```json
{
  "type": "hitl_response",
  "call_id": "call_999",
  "action": "approve",  // или "edit", "reject"
  "edited_arguments": { "content": "новый вариант кода" }, // только для edit
  "feedback": "Отредактировано, дополнил комментариями"
}
```
4. Сервер продолжает reasoning на основании решения (approve/edit/reject)

### Обработка статусов/журнал
- Можно выставлять статусы: waiting_human, approved, rejected, edited_by_human
- Все действия пользователя логируются

### Best practice
- Какую политику и список инструментов отправлять на HITL — решает backend
- IDE может выводить более заметное предупреждение для самых критичных action (например run/install)
- Можно сохранять историю решений для аудита

---

## Расширенные типы сообщений

### 1. Сообщение пользователя
```json
{
  "type": "user_message",
  "session_id": "UUID",
  "content": "Пожалуйста, рефактори main.py и напиши тесты",
  "role": "user"
}
```

### 2. Сообщение ассистента (потоковое/частичное)
```json
{
  "type": "assistant_message",
  "token": "Планирую шаги...",
  "is_final": false
}
```

### 3. План (Plan update)  ❗️**НОВЫЙ**
*Визуализируется как текущий высокоуровневый план агента или шаги рассуждения (COT).* 
```json
{
  "type": "plan_update",
  "plan_id": "plan-6ca1",
  "steps": [
     { "id": "1", "desc": "Анализ main.py", "status": "pending" },
     { "id": "2", "desc": "Сгенерировать рефакторинг", "status": "blocked" },
     { "id": "3", "desc": "Написать тесты", "status": "blocked" }
  ],
  "current_step": "1"
}
```
- `status`: [pending, running, blocked, error, done]

### 4. Прогресс по плану / результат  ❗️**НОВЫЙ**
*Промежуточный статус выбранного шага плана.*
```json
{
  "type": "plan_progress",
  "plan_id": "plan-6ca1",
  "step_id": "1",
  "result": "main.py прочитан. Готов рефакторинг.",
  "status": "done"
}
```

### 5. Tool Call (как и прежде, с привязкой к plan/step)
```json
{
  "type": "tool_call",
  "call_id": "c1",
  "tool_name": "read_file",
  "arguments": { "path": "main.py" },
  "plan_id": "plan-6ca1",
  "step_id": "1"
}
```

### 6. Tool Result (тоже с plan/step)
```json
{
  "type": "tool_result",
  "call_id": "c1",
  "result": { "content": "...содержимое файла..." },
  "plan_id": "plan-6ca1",
  "step_id": "1"
}
```

### 7. Обновление multi-agent/цепочки задач  ❗️**НОВЫЙ**
*Для multi-agent или сквозных американских сценарием*
```json
{
  "type": "agent_chain_update",
  "chain_id": "chain-xyz",
  "agents": [
    { "agent_id": "refactorer", "role": "refactor", "status": "done" },
    { "agent_id": "tester", "role": "test", "status": "pending" },
    { "agent_id": "explainer", "role": "docs", "status": "blocked" }
  ],
  "current_agent": "tester"
}
```

### 8. Ошибка/предупреждение (с контекстом)
```json
{
  "type": "error",
  "context": { "plan_id": "plan-6ca1", "step_id": "2" },
  "content": "Синтаксическая ошибка в строке 42"
}
```

---

## Пример сценария (рефакторинг)
1. user_message("Рефактори main.py и напиши тесты")
2. assistant_message(token: "Планирую...", is_final: false)
3. plan_update: [Анализ main.py → Рефакторинг → Тестирование]
4. Для шага 1 (Анализ): tool_call(read_file)
5. tool_result (read_file)
6. plan_progress (step 1, status: done)
7. plan_update (теперь step2 в работе)
8. tool_call(refactor_code)
9. tool_result (refactor_code)
10. plan_progress (step 2, status: done)
(и т.д.)

---

## Концептуальные моменты
- Все сообщения по плану/инструментам содержат plan_id, step_id, agent_id для отслеживания reasoning
- Клиент может визуализировать reasoning/план по шагам (UI reasoning panel)
- Протокол можно расширять для совместной работы, мультимодальности, вложенных задач

---

## JSON-схемы (псевдо)
- (см. примеры выше; для продакшена рекомендуется использовать openapi/json-schema для строгой валидации)
