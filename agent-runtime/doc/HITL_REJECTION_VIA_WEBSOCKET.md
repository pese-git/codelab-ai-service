# HITL Rejection через WebSocket - Бэклог

## Обзор

Этот документ описывает правильный архитектурный подход для обработки HITL (Human-in-the-Loop) отклонений через WebSocket сообщения вместо ошибок tool_result.

## Текущая реализация (Временное решение)

В настоящее время, когда пользователь отклоняет tool call в IDE:
1. IDE отправляет сообщение `tool_result` с ошибкой: `"Error: Операция отклонена: execute_command"`
2. Backend определяет отклонение по проверке текста ошибки в `process_tool_result()`
3. Pending approval удаляется из базы данных на основе совпадения текста ошибки

**Проблемы текущего подхода:**
- ❌ Зависит от совпадения текста ошибки (хрупкое решение)
- ❌ Смешивает ошибки выполнения инструментов с решениями пользователя
- ❌ Семантически некорректно (отклонение - это не ошибка выполнения инструмента)

## Предлагаемое решение (Вариант 1)

### Архитектура

Использовать выделенный тип WebSocket сообщения `hitl_decision` для решений пользователя:

```
Пользователь нажимает reject → IDE отправляет hitl_decision → Backend обрабатывает через process_hitl_decision() → Pending approval удаляется
```

### Детали реализации

#### 1. Изменения в IDE

**Файл:** `codelab_ide/packages/codelab_ai_assistant/lib/features/tool_execution/data/services/tool_approval_service_impl.dart`

**Добавить метод для отправки HITL решения:**
```dart
/// Отправить HITL решение на сервер через WebSocket
Future<void> _sendHitlDecision(
  String callId,
  String decision,
  String? feedback,
) async {
  final message = {
    'type': 'hitl_decision',
    'call_id': callId,
    'decision': decision,  // 'approve', 'reject', 'edit'
    'feedback': feedback,
  };
  
  // Отправить через WebSocket соединение
  await _websocketService.send(message);
}
```

**Обновить обработку отклонения (строка 189-196):**
```dart
// Текущий код:
if (onRejectRestoredTool != null) {
  final rejectReason = reason?.fold(() => 'User rejected', (r) => r) ?? 'User rejected';
  await onRejectRestoredTool!(toolCall, rejectReason);
}

// Новый код:
final rejectReason = reason?.fold(() => 'User rejected', (r) => r) ?? 'User rejected';
_logger.i('Отправка HITL отклонения для восстановленного tool: ${toolCall.toolName}');
await _sendHitlDecision(toolCall.id, 'reject', rejectReason);
```

**Файл:** `codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart`

**Обновить метод _rejectRestoredTool (строка 132-159):**
```dart
Future<void> _rejectRestoredTool(ToolCall toolCall, String reason) async {
  _logger.i('Отклонение восстановленного tool: ${toolCall.toolName}, причина: $reason');

  // Отправляем HITL decision вместо tool_result
  final hitlMessage = {
    'type': 'hitl_decision',
    'call_id': toolCall.id,
    'decision': 'reject',
    'feedback': reason,
  };
  
  // Отправить через WebSocket (требуется доступ к WebSocket соединению)
  await _websocketService.send(hitlMessage);
  
  // Добавить сообщение об отклонении в UI
  final rejectionMessage = Message(
    id: DateTime.now().millisecondsSinceEpoch.toString(),
    role: MessageRole.assistant,
    content: MessageContent.text(
      text: 'Операция отклонена: $reason',
      isFinal: true,
    ),
    timestamp: DateTime.now(),
    metadata: none(),
  );
  
  add(AgentChatEvent.messageReceived(rejectionMessage));
}
```

#### 2. Изменения в Backend

**Файл:** `codelab-ai-service/agent-runtime/app/domain/services/message_orchestration.py`

**Изменения НЕ требуются!** Метод `process_hitl_decision()` уже корректно обрабатывает отклонения:
- Строка 743-750: Обрабатывает решение REJECT
- Строка 753: Удаляет pending approval из базы данных
- Строка 756-763: Добавляет tool result в историю сессии

### Преимущества

✅ **Семантически корректно:** Решения пользователя отделены от ошибок выполнения инструментов
✅ **Надежно:** Нет зависимости от совпадения текста ошибки
✅ **Чистая архитектура:** Правильное разделение ответственности
✅ **Типобезопасно:** Использует выделенный тип сообщения с валидацией
✅ **Поддерживаемо:** Четкое намерение и проще отлаживать

### План миграции

1. **Фаза 1:** Сохранить текущую реализацию (Вариант 2) для обратной совместимости
2. **Фаза 2:** Реализовать HITL решения через WebSocket в IDE
3. **Фаза 3:** Пометить подход с проверкой текста ошибки как deprecated
4. **Фаза 4:** Удалить временное решение после полной миграции

### Чеклист тестирования

- [ ] Пользователь отклоняет tool call → pending approval удаляется из БД
- [ ] Пользователь отклоняет tool call → нет дублирующих tool_result сообщений
- [ ] Переподключение к сессии → отклоненный tool не появляется снова
- [ ] Пользователь approve после reject → tool выполняется только один раз
- [ ] Несколько pending approvals → каждый обрабатывается независимо
- [ ] Отклонение с feedback → feedback передается в LLM
- [ ] Отклонение без feedback → используется дефолтное сообщение

### Связанные файлы

**Backend:**
- [`message_orchestration.py:641`](../app/domain/services/message_orchestration.py) - `process_hitl_decision()`
- [`hitl_management.py:172`](../app/domain/services/hitl_management.py) - `remove_pending()`
- [`messages_router.py:214`](../app/api/v1/routers/messages_router.py) - HITL decision endpoint
- [`hitl.py:77`](../app/domain/entities/hitl.py) - `HITLUserDecision` entity

**Frontend:**
- `tool_approval_service_impl.dart` - Сервис подтверждений
- `agent_chat_bloc.dart` - Bloc чата с обработкой подтверждений
- `gateway_api.dart` - WebSocket коммуникация
- `websocket_service.dart` - Сервис WebSocket соединения

### Приоритет

**Средний** - Текущее решение функционально, но не идеально для долгосрочной поддержки.

### Оценка трудозатрат

- Backend: 0 часов (уже реализовано)
- Frontend: 4-6 часов (рефакторинг обработки WebSocket сообщений)
- Тестирование: 2 часа
- **Итого: 6-8 часов**

### Дополнительные улучшения

После реализации основного функционала можно добавить:

1. **Поддержка modified decision:**
   - Пользователь может изменить аргументы перед выполнением
   - IDE отправляет `decision: 'edit'` с `modified_arguments`

2. **Таймауты для pending approvals:**
   - Автоматическое отклонение после истечения времени
   - Уведомление пользователя о истекших запросах

3. **Batch operations:**
   - Approve/reject нескольких pending approvals одновременно
   - Полезно при восстановлении множества запросов

### Примеры WebSocket сообщений

**Отклонение:**
```json
{
  "type": "hitl_decision",
  "call_id": "call_abc123",
  "decision": "reject",
  "feedback": "Эта операция слишком рискованная"
}
```

**Одобрение:**
```json
{
  "type": "hitl_decision",
  "call_id": "call_abc123",
  "decision": "approve"
}
```

**Изменение:**
```json
{
  "type": "hitl_decision",
  "call_id": "call_abc123",
  "decision": "edit",
  "modified_arguments": {
    "path": "/src/main_v2.py",
    "content": "..."
  }
}
```

### Ссылки

- [HITL Implementation Documentation](HITL_IMPLEMENTATION.md)
- [WebSocket Protocol](../../doc/websocket-protocol.md)
- [Agent Extended Protocol](../../doc/agent_extended_protocol.md)
