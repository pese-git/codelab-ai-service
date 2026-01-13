# Benchmark Integration Guide

Этот документ описывает два режима работы benchmark runner:
1. **Симуляция** (для тестирования инфраструктуры метрик)
2. **Реальная интеграция** (для полноценного POC эксперимента)

## Режим 1: Симуляция (run_poc_experiment.py)

### Назначение
Тестирование инфраструктуры сбора метрик без реального выполнения задач.

### Как работает
- Загружает задачи из `poc_benchmark_tasks.yaml`
- **Симулирует** выполнение задач (не вызывает реальные агенты)
- Генерирует случайные метрики (LLM calls, tool calls, tokens)
- Записывает метрики в базу данных
- Генерирует отчеты

### Преимущества
- ✅ Не требует запущенных сервисов (LLM proxy, agent runtime)
- ✅ Быстрое выполнение (секунды)
- ✅ Предсказуемые результаты
- ✅ Идеально для тестирования системы метрик

### Использование
```bash
cd codelab-ai-service/agent-runtime
uv run python ../benchmark/scripts/run_poc_experiment.py --mode both
```

### Когда использовать
- Тестирование инфраструктуры метрик
- Проверка работы базы данных
- Разработка системы отчетов
- CI/CD тесты

## Режим 2: Реальная интеграция (run_poc_experiment_integrated.py)

### Назначение
Полноценное выполнение benchmark задач через реальный multi-agent orchestrator.

### Как работает
- Загружает задачи из `poc_benchmark_tasks.yaml`
- Создает сессию для каждой задачи
- **Вызывает реальный** `multi_agent_orchestrator.process_message()`
- Собирает реальные метрики из ответов агентов
- Записывает метрики в базу данных

### Требования
- ✅ Запущенный LLM proxy сервис
- ✅ Настроенный agent runtime
- ✅ Доступ к LLM API (OpenRouter/OpenAI)
- ✅ Инициализированная база данных

### Использование

#### 1. Запустить LLM proxy
```bash
cd codelab-ai-service/llm-proxy
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

#### 2. Запустить benchmark
```bash
cd codelab-ai-service/agent-runtime
uv run python ../benchmark/scripts/run_poc_experiment_integrated.py --mode multi-agent --limit 5
```

### Параметры
- `--mode` - режим (single-agent, multi-agent, both)
- `--limit` - ограничить количество задач (для тестирования)
- `--tasks` - путь к файлу задач
- `--db-url` - URL базы данных

### Когда использовать
- Реальное тестирование multi-agent системы
- Сравнение single-agent vs multi-agent
- Измерение реальной производительности
- Оценка качества ответов агентов

## Сравнение режимов

| Аспект | Симуляция | Реальная интеграция |
|--------|-----------|---------------------|
| Скорость | Очень быстро (секунды) | Медленно (минуты/часы) |
| Требования | Только база данных | LLM proxy + API ключи |
| Стоимость | $0 | Реальная стоимость LLM |
| Метрики | Случайные | Реальные |
| Качество | Симулированное | Реальное |
| Использование | Тестирование инфраструктуры | Реальный POC |

## Архитектура интеграции

### Симуляция
```
run_poc_experiment.py
  └─> simulate_task_execution()
       ├─> Генерирует случайные метрики
       ├─> collector.record_llm_call()
       ├─> collector.record_tool_call()
       └─> collector.record_agent_switch()
```

### Реальная интеграция
```
run_poc_experiment_integrated.py
  └─> execute_task_real()
       ├─> session_manager.get_or_create()
       ├─> agent_context_manager.get_or_create()
       └─> multi_agent_orchestrator.process_message()
            ├─> Реальные LLM вызовы
            ├─> Реальные tool calls
            ├─> Реальные agent switches
            └─> Сбор метрик из StreamChunk
```

## Сбор метрик

### Из симуляции
```python
# Случайные значения
input_tokens = 500 + i * 100
output_tokens = 200 + i * 50
success_rate = 0.9 if category == 'simple' else 0.7
```

### Из реальных ответов
```python
# Из StreamChunk metadata
async for chunk in multi_agent_orchestrator.process_message(...):
    if chunk.type == "assistant_message":
        input_tokens = chunk.metadata.get('input_tokens', 0)
        output_tokens = chunk.metadata.get('output_tokens', 0)
    elif chunk.type == "tool_call":
        tool_name = chunk.metadata.get('tool_name')
    elif chunk.type == "agent_switched":
        from_agent = chunk.metadata.get('from_agent')
        to_agent = chunk.metadata.get('to_agent')
```

## Troubleshooting

### Ошибка: "All connection attempts failed"
**Причина:** LLM proxy не запущен

**Решение:**
```bash
cd codelab-ai-service/llm-proxy
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### Ошибка: "session_manager is None"
**Причина:** Менеджеры не инициализированы

**Решение:** Убедитесь, что вызваны:
```python
await init_session_manager()
await init_agent_context_manager()
```

### Ошибка: "No LLM API key"
**Причина:** Не настроен API ключ для LLM

**Решение:** Настройте `.env` файл:
```bash
OPENROUTER_API_KEY=your_key_here
```

## Рекомендации

### Для разработки
Используйте **симуляцию** (`run_poc_experiment.py`):
- Быстрая итерация
- Нет затрат на LLM
- Тестирование инфраструктуры

### Для POC эксперимента
Используйте **реальную интеграцию** (`run_poc_experiment_integrated.py`):
- Реальные метрики
- Валидация качества
- Сравнение режимов

### Гибридный подход
1. Разработка на симуляции
2. Тестирование на 5-10 задачах с реальной интеграцией
3. Полный эксперимент на всех 40 задачах

## Следующие шаги

1. ✅ Инфраструктура метрик готова (симуляция работает)
2. ⏳ Запустить LLM proxy для реальной интеграции
3. ⏳ Протестировать на малом наборе задач
4. ⏳ Запустить полный эксперимент на 40 задачах
5. ⏳ Сравнить результаты single-agent vs multi-agent
