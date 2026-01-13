# Tool Execution Integration Plan

## Проблема

Текущая реализация `run_poc_experiment_integrated.py`:
- ✅ Обнаруживает tool_call chunks
- ✅ Выполняет tools через mock_tool_executor
- ❌ НЕ отправляет результаты обратно агенту
- ❌ Агент не может продолжить работу после tool call

## Решение

Нужно реализовать полный цикл tool execution:

```
1. Agent генерирует tool_call
2. Mock executor выполняет tool
3. Результат отправляется обратно агенту
4. Агент продолжает работу с результатом
5. Повторяется до завершения задачи
```

## Архитектура

### Текущая (неполная):
```python
async for chunk in multi_agent_orchestrator.process_message(session_id, message):
    if chunk.type == "tool_call":
        result = await tool_executor.execute_tool(...)
        # ❌ Результат не используется
```

### Требуемая (полная):
```python
while not task_completed:
    async for chunk in multi_agent_orchestrator.process_message(session_id, message):
        if chunk.type == "tool_call":
            # Execute tool
            result = await tool_executor.execute_tool(...)
            
            # Add tool result to session history
            await session_manager.append_tool_result(
                session_id,
                call_id=chunk.metadata['call_id'],
                tool_name=tool_name,
                result=json.dumps(result)
            )
            
            # Continue with empty message (agent will process tool result)
            message = ""
            break  # Exit inner loop to restart with tool result
        
        elif chunk.is_final:
            task_completed = True
```

## Реализация

### Шаг 1: Модифицировать execute_task_real()

Добавить цикл обработки tool calls:

```python
async def execute_task_real(self, ...):
    task_completed = False
    message = task_description
    max_iterations = 10  # Prevent infinite loops
    iteration = 0
    
    while not task_completed and iteration < max_iterations:
        iteration += 1
        tool_call_detected = False
        
        async for chunk in multi_agent_orchestrator.process_message(session_id, message):
            if chunk.type == "tool_call":
                # Execute and send result back
                await self._handle_tool_call(chunk, session_id, ...)
                tool_call_detected = True
                message = ""  # Continue with empty message
                break
            
            elif chunk.is_final:
                task_completed = True
        
        if not tool_call_detected and not task_completed:
            # No tool calls and not final - something wrong
            break
```

### Шаг 2: Реализовать _handle_tool_call()

```python
async def _handle_tool_call(self, chunk, session_id, collector, task_execution_id):
    tool_name = chunk.metadata.get('tool_name')
    call_id = chunk.metadata.get('call_id')
    arguments = chunk.metadata.get('arguments', {})
    
    # Execute tool
    result = await self.tool_executor.execute_tool(tool_name, arguments)
    
    # Add to session history
    from app.services.session_manager_async import session_manager as async_session_mgr
    await async_session_mgr.append_tool_result(
        session_id,
        call_id=call_id,
        tool_name=tool_name,
        result=json.dumps(result)
    )
    
    # Record metrics
    await collector.record_tool_call(...)
```

### Шаг 3: Обработка HITL approvals

Если tool требует approval:
```python
if chunk.metadata.get('requires_approval'):
    # Auto-approve for benchmark
    await hitl_manager.log_decision(
        session_id=session_id,
        call_id=call_id,
        tool_name=tool_name,
        original_arguments=arguments,
        decision=HITLDecision.APPROVE,
        modified_arguments=None,
        feedback="Auto-approved for benchmark"
    )
```

## Преимущества

После реализации:
- ✅ Агенты смогут создавать файлы
- ✅ Агенты смогут читать созданные файлы
- ✅ Агенты смогут итеративно работать над задачей
- ✅ Валидация будет проверять реальные результаты
- ✅ Метрики будут отражать реальную работу

## Оценка сложности

- **Время реализации**: 2-3 часа
- **Сложность**: Средняя
- **Риски**: Возможны бесконечные циклы tool calls
- **Тестирование**: Требуется тщательное тестирование

## Альтернативы

### Вариант 1: Полная интеграция (описано выше)
- Сложно, но даст реальные результаты

### Вариант 2: Упрощенная версия
- Выполнять только первый tool call
- Не продолжать conversation
- Проще, но менее реалистично

### Вариант 3: Текущая (без tool execution)
- Оценка только по ответам агентов
- Без реального создания файлов
- Работает сейчас

## Рекомендация

Для POC достаточно **Варианта 3** (текущий):
- Метрики собираются корректно
- Можно оценить routing и agent switches
- Можно измерить token usage и cost
- Валидация файлов - опциональна

Для production benchmark нужен **Вариант 1** (полная интеграция).