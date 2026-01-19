# Исправление ошибки "No tool call found" после переключения агента

## Проблема

При обработке запросов после переключения агента возникала ошибка от OpenRouter API:

```
No tool call found for function call output with call_id call_CYlqP7oYfGPEqxFNbhUgri8Y
```

## Реальная причина

Проблема была в том, что при вызове tool `switch_mode` агенты **добавляли tool_result в историю**:

1. Пользователь отправляет запрос "вызови flutter analyze"
2. **Ask agent** понимает, что не может выполнить команду
3. Ask agent **вызывает LLM tool `switch_mode(mode="coder")`**
4. LLM возвращает **assistant message с tool_call** для switch_mode
5. Ask agent **добавляет tool message в историю** ← **ВОТ ПРОБЛЕМА!**
6. Ask agent отправляет `switch_agent` chunk
7. MessageOrchestrationService переключает на **Coder** агента
8. Coder agent продолжает обработку и отправляет историю в OpenRouter API:
   ```
   [
     {"role": "user", "content": "вызови flutter analyze"},
     {"role": "assistant", "tool_calls": [{"id": "call_CYl...", "function": {"name": "switch_mode"}}]},
     {"role": "tool", "tool_call_id": "call_CYl...", "content": "Switching to coder agent"}
     // ❌ ПРОБЛЕМА: tool_call и tool_result от ПРЕДЫДУЩЕГО агента!
   ]
   ```
9. OpenRouter API видит tool_result, но **не может найти соответствующий tool_call в текущем запросе**, потому что это был tool_call от **другого агента** в **предыдущем запросе**

## Корневая причина

Когда агент вызывает `switch_mode` tool:
- LLM генерирует assistant message с tool_call
- Агент добавляет tool_result в историю
- Затем переключается на нового агента
- Новый агент отправляет историю с tool_call и tool_result в OpenRouter API
- Но OpenRouter API ожидает, что tool_call и tool_result будут в **одном conversation turn**, а не разделены переключением агента

## Решение

**НЕ добавлять tool_result в историю** при вызове `switch_mode` tool!

### 1. Исправить обработку switch_mode в Ask agent

**Файл:** `app/agents/ask_agent.py`

**Было:**
```python
if chunk.type == "tool_call" and chunk.tool_name == "switch_mode":
    # ...
    # Add tool result to session
    await session_service.add_message(
        session_id=session_id,
        role="tool",
        content=f"Switching to {target_mode} agent",
        name="switch_mode",
        tool_call_id=chunk.call_id  # ❌ Это создавало проблему!
    )
    # ...
```

**Стало:**
```python
if chunk.type == "tool_call" and chunk.tool_name == "switch_mode":
    # ...
    # ВАЖНО: НЕ добавляем tool_result в историю!
    # Это предотвращает ошибку "No tool call found" от OpenRouter API
    # Просто отправляем switch_agent chunk
    
    yield StreamChunk(
        type="switch_agent",
        content=f"Switching to {target_mode} agent",
        metadata={"target_agent": target_mode, "reason": reason},
        is_final=True
    )
    return
```

### 2. Исправить обработку switch_mode в Architect agent

**Файл:** `app/agents/architect_agent.py`

Аналогичные изменения - НЕ добавляем tool_result в историю при switch_mode.

### 3. Исправить обработку switch_mode в Debug agent

**Файл:** `app/agents/debug_agent.py`

Аналогичные изменения - НЕ добавляем tool_result в историю при switch_mode.

### 4. Улучшения в `message_orchestration.py`

**Файл:** `app/domain/services/message_orchestration.py`

Дополнительно улучшена обработка `message=None` для корректной работы после tool_result:

```python
# В process_message()
if message is not None and message != "":
    await self._session_service.add_message(...)
elif message is None:
    logger.debug("Skipping user message addition (message=None)")

# В process_tool_result()
async for chunk in current_agent.process(
    session_id=session_id,
    message=None,  # None означает "не добавлять user message"
    ...
):
```

## Результат

Теперь при переключении агента через `switch_mode`:

1. LLM генерирует assistant message с tool_call для switch_mode
2. Агент **НЕ добавляет** tool_result в историю
3. Агент отправляет `switch_agent` chunk
4. MessageOrchestrationService переключает на нового агента
5. Новый агент получает историю **БЕЗ tool_result** для switch_mode:
   ```
   [
     {"role": "user", "content": "вызови flutter analyze"},
     {"role": "assistant", "tool_calls": [{"id": "call_CYl...", "function": {"name": "switch_mode"}}]}
     // ✅ Нет tool_result! История остается корректной
   ]
   ```
6. Новый агент продолжает обработку с чистой историей
7. OpenRouter API **НЕ видит** orphan tool_result и работает корректно

## Почему это работает

- **switch_mode** - это специальный tool для переключения агентов
- Он **НЕ требует** tool_result, потому что переключение происходит **внутри системы**
- Tool_call для switch_mode остается в истории (это нормально)
- Но tool_result **НЕ добавляется**, потому что новый агент начинает с чистого состояния
- OpenRouter API видит assistant message с tool_call, но **не видит** tool_result, что корректно для switch_mode

## Архитектура переключения агентов

Теперь есть **два механизма** переключения:

### 1. Через Orchestrator (начало сессии)
```
User Request → Orchestrator (LLM classification) → switch_agent chunk → Specialized Agent
```

### 2. Через switch_mode tool (из специализированного агента)
```
Specialized Agent → LLM calls switch_mode → switch_agent chunk (БЕЗ tool_result!) → New Agent
```

**Оба механизма работают корректно!**

## Связанные файлы

- `app/agents/ask_agent.py` - исправлена обработка switch_mode
- `app/agents/architect_agent.py` - исправлена обработка switch_mode
- `app/agents/debug_agent.py` - исправлена обработка switch_mode
- `app/domain/services/message_orchestration.py` - улучшена обработка message=None
- `app/services/tool_registry.py` - switch_mode tool (теперь работает корректно)

## Дата исправления

2026-01-19
