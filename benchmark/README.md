# Benchmark Directory

Эта директория содержит все файлы, связанные с benchmark для POC экспериментов multi-agent системы.

## Структура

```
benchmark/
├── README.md                           # Этот файл
├── poc_benchmark_tasks.yaml            # 40 задач для тестирования
├── MULTI_AGENT_POC_BENCHMARK.md        # Спецификация benchmark
├── MULTI_AGENT_POC_METRICS.md          # Описание метрик
├── POC_METRICS_README.md               # Документация по метрикам
├── scripts/                            # Скрипты для запуска
│   ├── run_poc_experiment.py           # Запуск экспериментов
│   ├── generate_metrics_report.py      # Генерация отчетов
│   └── test_metrics.py                 # Тестирование метрик
└── reports/                            # Сгенерированные отчеты
```

## Быстрый старт

### 1. Запуск тестов метрик

```bash
cd codelab-ai-service/benchmark
python scripts/test_metrics.py
```

### 2. Запуск POC эксперимента

```bash
# Single-agent режим
python scripts/run_poc_experiment.py --mode single-agent

# Multi-agent режим
python scripts/run_poc_experiment.py --mode multi-agent

# Оба режима
python scripts/run_poc_experiment.py --mode both
```

### 3. Генерация отчета

```bash
# Последние эксперименты
python scripts/generate_metrics_report.py --latest --output reports/poc_report.md

# Конкретный эксперимент
python scripts/generate_metrics_report.py --experiment-id <uuid> --output reports/report.md
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

### run_poc_experiment.py

Автоматический запуск benchmark задач с сбором метрик.

**Параметры:**
- `--mode` - режим выполнения (single-agent, multi-agent, both)
- `--tasks` - путь к файлу с задачами (по умолчанию: poc_benchmark_tasks.yaml)
- `--db-url` - URL базы данных (по умолчанию: из конфига)

**Пример:**
```bash
python scripts/run_poc_experiment.py --mode both --tasks poc_benchmark_tasks.yaml
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