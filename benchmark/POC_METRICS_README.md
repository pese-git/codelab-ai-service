# POC Metrics Collection - Руководство по использованию

## Обзор

Система сбора метрик для POC эксперимента по сравнению single-agent и multi-agent режимов. Позволяет автоматически собирать и анализировать метрики производительности, качества и стоимости выполнения задач.

## Архитектура

### Компоненты

1. **SQLAlchemy модели** ([`app/models/metrics.py`](app/models/metrics.py))
   - `Experiment` - эксперимент (single-agent или multi-agent)
   - `TaskExecution` - выполнение отдельной задачи
   - `LLMCall` - вызов LLM API
   - `ToolCall` - вызов инструмента
   - `AgentSwitch` - переключение агента (multi-agent)
   - `QualityEvaluation` - оценка качества
   - `Hallucination` - обнаруженная галлюцинация

2. **MetricsCollector** ([`app/services/metrics_collector.py`](app/services/metrics_collector.py))
   - Сервис для сбора и хранения метрик
   - Async API для работы с базой данных
   - Автоматический расчет статистики

3. **POC Runner** ([`scripts/run_poc_experiment.py`](scripts/run_poc_experiment.py))
   - Автоматический запуск benchmark задач
   - Сбор метрик в процессе выполнения
   - Вывод базовой статистики

4. **Report Generator** ([`scripts/generate_metrics_report.py`](scripts/generate_metrics_report.py))
   - Генерация детальных Markdown отчетов
   - Сравнительный анализ single-agent vs multi-agent
   - Рекомендации на основе метрик

## Быстрый старт

### 1. Настройка окружения

Добавьте в `.env` файл:

```bash
# Включить сбор метрик
AGENT_RUNTIME__METRICS_ENABLED=true

# База данных (SQLite или PostgreSQL)
AGENT_RUNTIME__DB_URL=sqlite:///data/agent_runtime.db
# или для PostgreSQL:
# AGENT_RUNTIME__DB_URL=postgresql+asyncpg://user:password@localhost:5432/agent_runtime
```

### 2. Инициализация базы данных

При запуске agent-runtime с `METRICS_ENABLED=true` таблицы метрик создаются автоматически:

```bash
cd agent-runtime
python -m app.main
```

Вы увидите в логах:
```
✓ Database initialized
✓ Metrics tables initialized (METRICS_ENABLED=true)
```

### 3. Запуск POC эксперимента

#### Запуск в одном режиме:

```bash
# Single-agent режим
python scripts/run_poc_experiment.py --mode single-agent --tasks ../poc_benchmark_tasks.yaml

# Multi-agent режим
python scripts/run_poc_experiment.py --mode multi-agent --tasks ../poc_benchmark_tasks.yaml
```

#### Запуск в обоих режимах (рекомендуется):

```bash
python scripts/run_poc_experiment.py --mode both --tasks ../poc_benchmark_tasks.yaml
```

#### С кастомной базой данных:

```bash
python scripts/run_poc_experiment.py \
  --mode both \
  --tasks ../poc_benchmark_tasks.yaml \
  --db-url postgresql+asyncpg://user:password@localhost:5432/poc_metrics
```

### 4. Генерация отчета

После выполнения экспериментов сгенерируйте детальный Markdown отчет:

#### Использовать последние эксперименты (рекомендуется):

```bash
python scripts/generate_metrics_report.py --latest --output poc_report.md
```

Скрипт автоматически найдет последние эксперименты для single-agent и multi-agent режимов и создаст сравнительный отчет.

#### Использовать конкретный эксперимент:

```bash
python scripts/generate_metrics_report.py --experiment-id <uuid> --output report.md
```

#### С кастомной базой данных:

```bash
python scripts/generate_metrics_report.py \
  --latest \
  --output poc_report.md \
  --db-url postgresql+asyncpg://user:password@localhost:5432/poc_metrics
```

Отчет будет содержать:
- Executive Summary с ключевыми выводами
- Детальные метрики для каждого режима
- Сравнительные таблицы
- Анализ по категориям и типам задач
- Рекомендации на основе результатов

## Использование MetricsCollector в коде

### Базовый пример

```python
from app.services.database import get_db
from app.services.metrics_collector import MetricsCollector

async def run_experiment():
    async for db in get_db():
        collector = MetricsCollector(db)
        
        # Начать эксперимент
        exp_id = await collector.start_experiment(
            mode="multi-agent",
            config={"llm_model": "gpt-4", "temperature": 0.7}
        )
        
        # Начать задачу
        task_id = await collector.start_task(
            experiment_id=exp_id,
            task_id="task_001",
            task_category="simple",
            task_type="coding",
            mode="multi-agent"
        )
        
        # Записать LLM вызов
        await collector.record_llm_call(
            task_execution_id=task_id,
            agent_type="coder",
            input_tokens=500,
            output_tokens=200,
            model="gpt-4",
            duration_seconds=2.5
        )
        
        # Записать вызов инструмента
        await collector.record_tool_call(
            task_execution_id=task_id,
            tool_name="write_file",
            success=True,
            duration_seconds=0.1
        )
        
        # Записать переключение агента (multi-agent)
        await collector.record_agent_switch(
            task_execution_id=task_id,
            from_agent="orchestrator",
            to_agent="coder",
            reason="Coding task detected"
        )
        
        # Записать оценку качества
        await collector.record_quality_evaluation(
            task_execution_id=task_id,
            evaluation_type="syntax_check",
            score=0.95,
            passed=True,
            details={"checks_passed": 10, "checks_failed": 0}
        )
        
        # Завершить задачу
        await collector.complete_task(
            task_execution_id=task_id,
            success=True,
            metrics={"iterations": 3}
        )
        
        # Завершить эксперимент
        await collector.complete_experiment(exp_id)
        
        # Получить статистику
        summary = await collector.get_experiment_summary(exp_id)
        print(summary)
```

## Структура базы данных

### Таблицы

#### `poc_experiments`
- `id` - UUID эксперимента
- `mode` - режим ('single-agent' или 'multi-agent')
- `started_at` - время начала
- `completed_at` - время завершения
- `config` - конфигурация (JSON)

#### `poc_task_executions`
- `id` - UUID выполнения задачи
- `experiment_id` - ссылка на эксперимент
- `task_id` - ID задачи из benchmark
- `task_category` - категория ('simple', 'medium', 'complex', 'specialized')
- `task_type` - тип ('coding', 'architecture', 'debug', 'question', 'mixed')
- `mode` - режим выполнения
- `started_at` - время начала
- `completed_at` - время завершения
- `success` - успешность выполнения
- `failure_reason` - причина неудачи
- `metrics` - дополнительные метрики (JSON)

#### `poc_llm_calls`
- `id` - UUID вызова
- `task_execution_id` - ссылка на выполнение задачи
- `agent_type` - тип агента
- `input_tokens` - входные токены
- `output_tokens` - выходные токены
- `model` - модель LLM
- `duration_seconds` - длительность

#### `poc_tool_calls`
- `id` - UUID вызова
- `task_execution_id` - ссылка на выполнение задачи
- `tool_name` - имя инструмента
- `success` - успешность
- `duration_seconds` - длительность
- `error` - ошибка (если есть)

#### `poc_agent_switches`
- `id` - UUID переключения
- `task_execution_id` - ссылка на выполнение задачи
- `from_agent` - агент до переключения
- `to_agent` - агент после переключения
- `reason` - причина переключения
- `timestamp` - время переключения

#### `poc_quality_evaluations`
- `id` - UUID оценки
- `task_execution_id` - ссылка на выполнение задачи
- `evaluation_type` - тип оценки
- `score` - оценка (0.0-1.0)
- `passed` - пройдена ли оценка
- `details` - детали (JSON)
- `evaluated_at` - время оценки

#### `poc_hallucinations`
- `id` - UUID галлюцинации
- `task_execution_id` - ссылка на выполнение задачи
- `hallucination_type` - тип ('import', 'api', 'file', 'parameter')
- `description` - описание
- `detected_at` - время обнаружения

## Анализ результатов

### SQL запросы для анализа

#### Сравнение success rate:

```sql
SELECT 
    mode,
    COUNT(*) as total_tasks,
    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_tasks,
    ROUND(AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) * 100, 2) as success_rate_percent
FROM poc_task_executions
GROUP BY mode;
```

#### Сравнение стоимости:

```sql
SELECT 
    te.mode,
    SUM(lc.input_tokens) as total_input_tokens,
    SUM(lc.output_tokens) as total_output_tokens,
    ROUND((SUM(lc.input_tokens) * 0.003 + SUM(lc.output_tokens) * 0.015) / 1000, 4) as estimated_cost_usd
FROM poc_task_executions te
JOIN poc_llm_calls lc ON te.id = lc.task_execution_id
GROUP BY te.mode;
```

#### Анализ переключений агентов:

```sql
SELECT 
    from_agent,
    to_agent,
    COUNT(*) as switch_count,
    AVG(CASE WHEN te.success = 1 THEN 1.0 ELSE 0.0 END) as success_rate
FROM poc_agent_switches ags
JOIN poc_task_executions te ON ags.task_execution_id = te.id
GROUP BY from_agent, to_agent
ORDER BY switch_count DESC;
```

#### Hallucination rate:

```sql
SELECT 
    te.mode,
    COUNT(DISTINCT te.id) as total_tasks,
    COUNT(DISTINCT h.task_execution_id) as tasks_with_hallucinations,
    ROUND(COUNT(DISTINCT h.task_execution_id) * 100.0 / COUNT(DISTINCT te.id), 2) as hallucination_rate_percent
FROM poc_task_executions te
LEFT JOIN poc_hallucinations h ON te.id = h.task_execution_id
GROUP BY te.mode;
```

### Python анализ

```python
import pandas as pd
from sqlalchemy import create_engine

# Подключение к базе
engine = create_engine("sqlite:///data/agent_runtime.db")

# Загрузка данных
tasks_df = pd.read_sql("SELECT * FROM poc_task_executions", engine)
llm_calls_df = pd.read_sql("SELECT * FROM poc_llm_calls", engine)

# Анализ по категориям
category_analysis = tasks_df.groupby(['mode', 'task_category']).agg({
    'success': ['count', 'sum', 'mean']
}).round(3)

print(category_analysis)

# Анализ токенов
token_analysis = llm_calls_df.merge(
    tasks_df[['id', 'mode']], 
    left_on='task_execution_id', 
    right_on='id'
).groupby('mode').agg({
    'input_tokens': 'sum',
    'output_tokens': 'sum',
    'duration_seconds': 'mean'
})

print(token_analysis)
```

## Troubleshooting

### Таблицы не создаются

Проверьте:
1. `METRICS_ENABLED=true` в `.env`
2. Права доступа к базе данных
3. Логи при запуске agent-runtime

### Ошибки при записи метрик

Проверьте:
1. Существование task_execution_id перед записью метрик
2. Валидность параметров (например, score должен быть 0.0-1.0)
3. Логи в `MetricsCollector`

### Медленная работа с большим количеством метрик

Рекомендации:
1. Используйте PostgreSQL вместо SQLite для больших объемов
2. Добавьте индексы (уже созданы в моделях)
3. Используйте batch операции где возможно

## Следующие шаги

1. **Запустите тестовый эксперимент** с 10 задачами из `poc_benchmark_tasks.yaml`
2. **Проверьте данные** в базе данных
3. **Проанализируйте результаты** с помощью SQL или Python
4. **Расширьте benchmark** до полных 40 задач из `MULTI_AGENT_POC_BENCHMARK.md`
5. **Создайте визуализации** результатов (Jupyter Notebook, Grafana)

## Ссылки

- [MULTI_AGENT_POC_METRICS.md](../MULTI_AGENT_POC_METRICS.md) - детальное описание метрик
- [MULTI_AGENT_POC_BENCHMARK.md](../MULTI_AGENT_POC_BENCHMARK.md) - полный набор задач
- [MULTI_AGENT_POC_PLAN.md](../MULTI_AGENT_POC_PLAN.md) - план POC эксперимента

## Поддержка

При возникновении проблем:
1. Проверьте логи agent-runtime
2. Проверьте структуру базы данных
3. Убедитесь, что все зависимости установлены
4. Обратитесь к документации SQLAlchemy для сложных запросов

---

**Создано:** 2026-01-12  
**Версия:** 1.0  
**Статус:** Готово к использованию
