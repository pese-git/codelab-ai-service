# Benchmark Directory

Эта директория содержит все файлы, связанные с benchmark для POC экспериментов multi-agent системы.

## Структура

```
benchmark/
├── README.md                              # Этот файл
├── INTEGRATION_GUIDE.md                   # Руководство по интеграции
├── poc_benchmark_tasks.yaml               # 40 задач для тестирования
├── MULTI_AGENT_POC_BENCHMARK.md           # Спецификация benchmark
├── MULTI_AGENT_POC_METRICS.md             # Описание метрик
├── POC_METRICS_README.md                  # Документация по метрикам
├── scripts/                               # Скрипты для запуска
│   ├── run_poc_experiment.py              # Симуляция (для тестирования)
│   ├── run_poc_experiment_integrated.py   # Реальная интеграция (для POC)
│   ├── generate_metrics_report.py         # Генерация отчетов
│   └── test_metrics.py                    # Тестирование метрик
└── reports/                               # Сгенерированные отчеты
```

## Два режима работы

### 🔧 Режим 1: Симуляция (для разработки)
**Скрипт:** `run_poc_experiment.py`

- Симулирует выполнение задач
- Не требует LLM proxy
- Быстрое выполнение
- Для тестирования инфраструктуры метрик

### 🚀 Режим 2: Реальная интеграция (для POC)
**Скрипт:** `run_poc_experiment_integrated.py`

- Реальное выполнение через multi-agent orchestrator
- Требует запущенный LLM proxy
- Реальные метрики и стоимость
- Для полноценного POC эксперимента

**См. подробности в:** [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md)

## Быстрый старт

### 1. Тестирование инфраструктуры метрик

```bash
cd codelab-ai-service/agent-runtime
uv run python ../benchmark/scripts/test_metrics.py
```

### 2. Запуск симуляции (быстрое тестирование)

```bash
cd codelab-ai-service/agent-runtime

# Все задачи, оба режима
uv run python ../benchmark/scripts/run_poc_experiment.py --mode both

# Одна задача
uv run python ../benchmark/scripts/run_poc_experiment.py --mode single-agent --task-id task_001

# Несколько задач
uv run python ../benchmark/scripts/run_poc_experiment.py --mode single-agent --task-ids task_001,task_005,task_010

# Диапазон задач
uv run python ../benchmark/scripts/run_poc_experiment.py --mode single-agent --task-range 1-10

# По категории
uv run python ../benchmark/scripts/run_poc_experiment.py --mode single-agent --category simple

# По типу
uv run python ../benchmark/scripts/run_poc_experiment.py --mode single-agent --type coding

# Ограничить количество
uv run python ../benchmark/scripts/run_poc_experiment.py --mode single-agent --limit 5
```

### 3. Запуск реальной интеграции (требует LLM proxy)

```bash
# Терминал 1: Запустить LLM proxy
cd codelab-ai-service/llm-proxy
uv run uvicorn app.main:app --host 0.0.0.0 --port 8002

# Терминал 2: Запустить benchmark с различными фильтрами
cd codelab-ai-service/agent-runtime

# Одна задача
uv run python ../benchmark/scripts/run_poc_experiment_integrated.py --mode multi-agent --task-id task_001

# Диапазон задач
uv run python ../benchmark/scripts/run_poc_experiment_integrated.py --mode multi-agent --task-range 1-5

# По категории
uv run python ../benchmark/scripts/run_poc_experiment_integrated.py --mode multi-agent --category simple

# По типу
uv run python ../benchmark/scripts/run_poc_experiment_integrated.py --mode multi-agent --type coding

# Ограничить количество
uv run python ../benchmark/scripts/run_poc_experiment_integrated.py --mode multi-agent --limit 5
```

### 4. Генерация отчета

```bash
cd codelab-ai-service/agent-runtime

# Последние эксперименты
uv run python ../benchmark/scripts/generate_metrics_report.py --latest --output ../benchmark/reports/poc_report.md

# Конкретный эксперимент
uv run python ../benchmark/scripts/generate_metrics_report.py --experiment-id <uuid> --output ../benchmark/reports/report.md
```

## Файлы

### poc_benchmark_tasks.yaml

Полный набор из 40 задач для тестирования:
- 10 простых задач (категория A)
- 15 средних задач (категория B)
- 10 сложных задач (категория C)
- 5 специализированных задач (категория D)

Распределение по типам:
- 16 coding задач
- 8 architecture задач
- 8 debug задач
- 4 question задач
- 4 mixed задач

### MULTI_AGENT_POC_BENCHMARK.md

Полная спецификация benchmark:
- Методология тестирования
- Описание категорий задач
- Критерии оценки
- Ожидаемые результаты

### MULTI_AGENT_POC_METRICS.md

Описание системы метрик:
- Типы собираемых метрик
- Формулы расчета
- Критерии сравнения

### POC_METRICS_README.md

Техническая документация:
- Архитектура системы метрик
- API MetricsCollector
- Схема базы данных
- Примеры использования

## Скрипты

### run_poc_experiment.py (Симуляция)

Автоматический запуск benchmark задач с **симуляцией** выполнения.

**Назначение:** Тестирование инфраструктуры метрик без реальных LLM вызовов.

**Параметры:**
- `--mode` - режим выполнения (single-agent, multi-agent, both)
- `--tasks` - путь к файлу с задачами
- `--db-url` - URL базы данных

**Пример:**
```bash
cd codelab-ai-service/agent-runtime
uv run python ../benchmark/scripts/run_poc_experiment.py --mode both
```

### run_poc_experiment_integrated.py (Реальная интеграция)

Запуск benchmark задач через **реальный** multi-agent orchestrator.

**Назначение:** Полноценный POC эксперимент с реальными агентами.

**Требования:**
- Запущенный LLM proxy на порту 8001
- Настроенный API ключ для LLM
- Инициализированная база данных

**Параметры:**
- `--mode` - режим выполнения (single-agent, multi-agent, both)
- `--tasks` - путь к файлу с задачами
- `--limit` - ограничить количество задач (для тестирования)
- `--db-url` - URL базы данных

**Пример:**
```bash
cd codelab-ai-service/agent-runtime
uv run python ../benchmark/scripts/run_poc_experiment_integrated.py --mode multi-agent --limit 5
```

### generate_metrics_report.py

Генерация детального отчета по результатам экспериментов.

**Параметры:**
- `--latest` - использовать последние эксперименты
- `--experiment-id` - ID конкретного эксперимента
- `--output` - путь к выходному файлу
- `--db-url` - URL базы данных

**Пример:**
```bash
python scripts/generate_metrics_report.py --latest --output reports/poc_report.md
```

### test_metrics.py

Тестирование инфраструктуры метрик.

**Тесты:**
1. Инициализация базы данных
2. Создание таблиц
3. Операции MetricsCollector
4. Персистентность данных

**Пример:**
```bash
python scripts/test_metrics.py
```

## Отчеты

Сгенерированные отчеты сохраняются в директории `reports/` в формате Markdown.

Отчет включает:
- Executive Summary
- Детальные метрики для каждого режима
- Сравнительный анализ
- Выводы и рекомендации

## Требования

Скрипты требуют доступа к agent-runtime модулю:
- `app.core.config`
- `app.services.database`
- `app.services.metrics_collector`
- `app.models.metrics`

Убедитесь, что agent-runtime настроен и база данных инициализирована.

## Дополнительная информация

Для подробной информации см.:
- [MULTI_AGENT_POC_BENCHMARK.md](MULTI_AGENT_POC_BENCHMARK.md) - полная спецификация
- [POC_METRICS_README.md](POC_METRICS_README.md) - техническая документация
- [MULTI_AGENT_POC_METRICS.md](MULTI_AGENT_POC_METRICS.md) - описание метрик