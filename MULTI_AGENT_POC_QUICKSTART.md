# MULTI_AGENT_POC_QUICKSTART

## 1. Предварительные требования

### 1.1 Системные требования
- **ОС:** macOS 11+, Linux Ubuntu 20.04+, Windows 10+ (WSL2)
- **CPU:** 4+ ядер (рекомендуется 8+ для комфортной работы)
- **RAM:** 16GB+ (рекомендуется 32GB для одновременного запуска нескольких моделей)
- **Диск:** 50GB+ свободного места (для Docker образов и моделей)
- **Сеть:** Стабильное интернет-соединение (для загрузки моделей и API вызовов)

### 1.2 Установленное ПО
- **Docker:** Версия 24.0+ с Docker Compose V2
- **Python:** 3.12+ (для локального запуска)
- **uv:** Быстрый менеджер пакетов Python (опционально, но рекомендуется)
- **Git:** Для клонирования репозитория

### 1.3 API ключи
- **OpenAI API Key:** Для доступа к GPT моделям
- **Anthropic API Key:** Для доступа к Claude моделям (опционально)
- **OpenRouter API Key:** Для доступа к альтернативным моделям (опционально)

### 1.4 Знания и навыки
- Базовые знания командной строки
- Понимание Docker и контейнеризации
- Знакомство с Python и REST API (желательно)

## 2. Подготовка окружения

### 2.1 Клонирование репозитория

```bash
git clone https://github.com/pese-git/codelab-ai-service.git
cd codelab-ai-service
```

### 2.2 Настройка переменных окружения

```bash
# Копируем шаблон конфигурации
cp .env.example .env

# Редактируем .env файл (обязательные настройки)
nano .env
```

Минимально необходимые настройки в `.env`:

```bash
# Общие настройки
ENVIRONMENT=development

# API ключи (минимум один)
OPENAI_API_KEY=sk-your-openai-key-here
# ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here  # опционально

# Режим работы LLM (используем litellm для доступа к различным провайдерам)
LLM_PROXY__LLM_MODE=litellm
LLM_PROXY__DEFAULT_MODEL=gpt-4

# Модель для агентов
AGENT_RUNTIME__LLM_MODEL=gpt-4

# Режим мультиагентной системы (изменяем для экспериментов)
MULTI_AGENT_MODE=true  # или false для single-agent
```

### 2.3 Запуск инфраструктуры

```bash
# Запуск всех сервисов через Docker Compose
docker compose up -d

# Проверка статуса сервисов
docker compose ps

# Просмотр логов для диагностики
docker compose logs -f
```

### 2.4 Загрузка моделей (опционально)

Если планируете использовать локальные модели через Ollama:

```bash
# Загрузка компактной модели для тестов
./pull_model_docker.sh qwen3:0.6b

# Или более мощной модели
./pull_model_docker.sh mistral:7b
```

### 2.5 Проверка работоспособности

```bash
# Проверка health-check всех сервисов
curl http://localhost/nginx-health
curl http://localhost/auth-health
curl http://localhost/gateway-health

# Проверка доступных агентов (если MULTI_AGENT_MODE=true)
curl http://localhost/api/v1/agents \
  -H "X-Internal-Auth: GATEWAY__INTERNAL_API_KEY"
```

## 3. Запуск Single-Agent режима (Baseline)

### 3.1 Настройка Single-Agent режима

```bash
# Останавливаем сервисы
docker compose down

# Меняем настройку в .env файле
echo "MULTI_AGENT_MODE=false" >> .env

# Перезапускаем сервисы
docker compose up -d
```

### 3.2 Создание скрипта эксперимента

Создайте файл `run_poc_experiment.py` в корне проекта:

```python
#!/usr/bin/env python3
"""
POC Experiment Runner для сравнения Single-Agent vs Multi-Agent режимов
"""

import asyncio
import json
import time
import aiohttp
from typing import List, Dict, Any
import yaml
import os

class POCExperiment:
    def __init__(self, base_url: str = "http://localhost", api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key or os.getenv("GATEWAY__INTERNAL_API_KEY", "change-me-in-production")
        self.session = None

    async def setup(self):
        self.session = aiohttp.ClientSession(headers={
            "X-Internal-Auth": self.api_key,
            "Content-Type": "application/json"
        })

    async def run_task(self, task: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Запуск одной задачи и сбор метрик"""
        start_time = time.time()

        # Формируем сообщение
        message = {
            "session_id": session_id,
            "type": "user_message",
            "content": task["description"],
            "role": "user"
        }

        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/agent/message/stream",
                json={"message": message}
            ) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: {await response.text()}")

                # Читаем потоковый ответ
                result = await self._process_stream(response)
                end_time = time.time()

                return {
                    "task_id": task["id"],
                    "session_id": session_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": end_time - start_time,
                    "result": result,
                    "success": self._check_success(task, result)
                }

        except Exception as e:
            end_time = time.time()
            return {
                "task_id": task["id"],
                "session_id": session_id,
                "start_time": start_time,
                "end_time": end_time,
                "duration": end_time - start_time,
                "error": str(e),
                "success": False
            }

    async def _process_stream(self, response):
        """Обработка SSE потока"""
        result = {"messages": [], "tool_calls": [], "final_answer": None}

        async for line in response.content:
            line = line.decode('utf-8').strip()
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    result["messages"].append(data)

                    if data.get("type") == "tool_call":
                        result["tool_calls"].append(data)
                    elif data.get("type") == "assistant_message" and data.get("final"):
                        result["final_answer"] = data.get("content")

                except json.JSONDecodeError:
                    continue

        return result

    def _check_success(self, task: Dict, result: Dict) -> bool:
        """Проверка успешности выполнения задачи"""
        # Реализуйте логику проверки на основе success_criteria
        return len(result.get("tool_calls", [])) > 0

async def main():
    # Загрузка задач
    with open("MULTI_AGENT_POC_BENCHMARK.md", "r", encoding="utf-8") as f:
        # Парсинг задач из markdown (упрощенная версия)
        tasks = []  # TODO: реализовать парсинг

    experiment = POCExperiment()
    await experiment.setup()

    results = []

    for i, task in enumerate(tasks[:5]):  # Тестируем на первых 5 задачах
        session_id = f"single_agent_exp_{i}"
        result = await experiment.run_task(task, session_id)
        results.append(result)
        print(f"Task {task['id']}: {'✅' if result['success'] else '❌'} ({result['duration']:.2f}s)")

    # Сохранение результатов
    with open("single_agent_results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(main())
```

### 3.3 Запуск эксперимента

```bash
# Делаем скрипт исполняемым
chmod +x run_poc_experiment.py

# Запуск single-agent эксперимента
python run_poc_experiment.py

# Мониторинг в отдельном терминале
docker compose logs -f agent-runtime
```

### 3.4 Мониторинг прогресса

```bash
# Просмотр логов агента
docker compose logs -f agent-runtime | grep "session_"

# Проверка использования ресурсов
docker stats

# Мониторинг API вызовов (если есть доступ к метрикам)
curl http://localhost/gateway-health
```

## 4. Запуск Multi-Agent режима

### 4.1 Настройка Multi-Agent режима

```bash
# Останавливаем сервисы
docker compose down

# Меняем настройку в .env файле
sed -i 's/MULTI_AGENT_MODE=false/MULTI_AGENT_MODE=true/' .env

# Перезапускаем сервисы
docker compose up -d
```

### 4.2 Запуск эксперимента

```bash
# Запуск multi-agent эксперимента (используем тот же скрипт)
python run_poc_experiment.py

# Результаты сохранятся в multi_agent_results.json
```

### 4.3 Мониторинг переключений агентов

```bash
# Просмотр переключений агентов в логах
docker compose logs agent-runtime | grep "Switched to agent"

# Проверка текущего агента для сессии
curl "http://localhost/api/v1/agents/session_123/current" \
  -H "X-Internal-Auth: GATEWAY__INTERNAL_API_KEY"
```

## 5. Сбор и анализ результатов

### 5.1 Экспорт метрик

Создайте скрипт для экспорта метрик:

```python
#!/usr/bin/env python3
"""
Экспорт метрик POC эксперимента
"""

import json
import csv
from datetime import datetime

def export_metrics(experiment_id: str, results_file: str, output_format: str = "csv"):
    """Экспорт метрик в CSV или JSON"""

    with open(results_file, "r") as f:
        results = json.load(f)

    metrics = []
    for result in results:
        metric = {
            "experiment_id": experiment_id,
            "task_id": result["task_id"],
            "success": result["success"],
            "duration": result["duration"],
            "tool_calls": len(result.get("result", {}).get("tool_calls", [])),
            "timestamp": datetime.fromtimestamp(result["start_time"]).isoformat()
        }
        metrics.append(metric)

    if output_format == "csv":
        with open(f"{experiment_id}_metrics.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=metrics[0].keys())
            writer.writeheader()
            writer.writerows(metrics)
    else:
        with open(f"{experiment_id}_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)

    return metrics

if __name__ == "__main__":
    # Экспорт single-agent метрик
    export_metrics("single_agent_exp_001", "single_agent_results.json")

    # Экспорт multi-agent метрик
    export_metrics("multi_agent_exp_001", "multi_agent_results.json")
```

```bash
# Экспорт метрик
python export_metrics.py
```

### 5.2 Генерация отчета

Создайте скрипт сравнительного анализа:

```python
#!/usr/bin/env python3
"""
Генерация сравнительного отчета Single vs Multi-Agent
"""

import json
import pandas as pd
from datetime import datetime

def generate_comparison_report(single_results: str, multi_results: str):
    """Генерация сравнительного отчета"""

    with open(single_results, "r") as f:
        single = json.load(f)

    with open(multi_results, "r") as f:
        multi = json.load(f)

    # Расчет метрик
    single_metrics = calculate_metrics(single)
    multi_metrics = calculate_metrics(multi)

    # Вывод сравнения
    print("## Сравнительный отчет POC эксперимента")
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"Single-Agent задач: {len(single)}")
    print(f"Multi-Agent задач: {len(multi)}")
    print()

    print("### Основные метрики:")
    print(f"Task Success Rate - Single: {single_metrics['success_rate']:.1%}")
    print(f"Task Success Rate - Multi: {multi_metrics['success_rate']:.1%}")
    print(f"Time To Useful Answer - Single: {single_metrics['avg_time']:.2f}s")
    print(f"Time To Useful Answer - Multi: {multi_metrics['avg_time']:.2f}s")
    print()

    # Сохранение детального отчета
    report = {
        "experiment_date": datetime.now().isoformat(),
        "single_agent": single_metrics,
        "multi_agent": multi_metrics,
        "comparison": {
            "success_rate_diff": multi_metrics["success_rate"] - single_metrics["success_rate"],
            "time_diff": multi_metrics["avg_time"] - single_metrics["avg_time"]
        }
    }

    with open("poc_comparison_report.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

def calculate_metrics(results):
    """Расчет метрик из результатов"""
    if not results:
        return {"success_rate": 0, "avg_time": 0, "total_tasks": 0}

    successful = sum(1 for r in results if r.get("success", False))
    total_time = sum(r.get("duration", 0) for r in results)

    return {
        "success_rate": successful / len(results),
        "avg_time": total_time / len(results),
        "total_tasks": len(results)
    }

if __name__ == "__main__":
    generate_comparison_report("single_agent_results.json", "multi_agent_results.json")
```

```bash
# Генерация отчета
python generate_report.py
```

### 5.3 Визуализация

Для создания dashboard можно использовать Streamlit:

```python
#!/usr/bin/env python3
"""
POC Dashboard для визуализации результатов
"""

import streamlit as st
import json
import pandas as pd
import plotly.express as px

def load_results(file_path):
    """Загрузка результатов эксперимента"""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def create_dashboard():
    st.title("POC Multi-Agent Experiment Dashboard")

    # Загрузка данных
    single_results = load_results("single_agent_results.json")
    multi_results = load_results("multi_agent_results.json")

    if not single_results and not multi_results:
        st.error("Результаты экспериментов не найдены")
        return

    # Метрики
    col1, col2, col3 = st.columns(3)

    with col1:
        single_success = sum(1 for r in single_results if r.get("success")) / len(single_results) if single_results else 0
        st.metric("Single-Agent TSR", ".1%")

    with col2:
        multi_success = sum(1 for r in multi_results if r.get("success")) / len(multi_results) if multi_results else 0
        st.metric("Multi-Agent TSR", ".1%")

    with col3:
        improvement = multi_success - single_success
        st.metric("Улучшение TSR", "+.1%", delta="good" if improvement > 0 else "bad")

    # Графики
    if single_results and multi_results:
        # Сравнение времени выполнения
        fig = px.box(
            x=["Single-Agent"] * len(single_results) + ["Multi-Agent"] * len(multi_results),
            y=[r["duration"] for r in single_results] + [r["duration"] for r in multi_results],
            title="Сравнение времени выполнения задач"
        )
        st.plotly_chart(fig)

if __name__ == "__main__":
    create_dashboard()
```

```bash
# Запуск dashboard
pip install streamlit plotly
streamlit run poc_dashboard.py
```

## 6. Troubleshooting

### 6.1 Распространенные проблемы

#### Сервисы не запускаются
```bash
# Проверить логи
docker compose logs

# Проверить конфигурацию
docker compose config

# Пересоздать контейнеры
docker compose down -v
docker compose up -d --build
```

#### API ключ не работает
```bash
# Проверить переменные окружения
docker compose exec agent-runtime env | grep API

# Проверить доступность API
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models
```

#### Недостаточно ресурсов
```bash
# Проверить использование RAM/CPU
docker stats

# Ограничить ресурсы в docker-compose.yml
services:
  agent-runtime:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
```

#### Медленная работа
```bash
# Использовать локальную модель вместо API
# В .env: LLM_PROXY__DEFAULT_MODEL=ollama/qwen3:0.6b

# Проверить сетевые задержки
time curl http://localhost/api/v1/agents
```

### 6.2 Перезапуск эксперимента

```bash
# Очистка данных предыдущего эксперимента
rm -f *_results.json *_metrics.*

# Очистка логов (опционально)
docker compose down
docker compose up -d

# Перезапуск эксперимента
python run_poc_experiment.py
```

### 6.3 Очистка окружения

```bash
# Остановка сервисов
docker compose down

# Удаление volumes (включая модели и БД)
docker compose down -v

# Удаление образов (для полной очистки)
docker compose down --rmi all

# Очистка результатов экспериментов
rm -f *_results.json *_metrics.* poc_comparison_report.json
```

## 7. Чеклист проведения POC

### Подготовка
- [ ] Репозиторий склонирован
- [ ] Переменные окружения настроены (.env файл)
- [ ] API ключи добавлены (минимум OpenAI)
- [ ] Docker сервисы запущены (`docker compose up -d`)
- [ ] Работоспособность проверена (health-check endpoints)

### Single-Agent эксперимент (Baseline)
- [ ] MULTI_AGENT_MODE=false в .env
- [ ] Сервисы перезапущены
- [ ] Скрипт run_poc_experiment.py создан
- [ ] Эксперимент запущен (`python run_poc_experiment.py`)
- [ ] Результаты сохранены (single_agent_results.json)
- [ ] Метрики экспортированы

### Multi-Agent эксперимент
- [ ] MULTI_AGENT_MODE=true в .env
- [ ] Сервисы перезапущены
- [ ] Эксперимент запущен (`python run_poc_experiment.py`)
- [ ] Результаты сохранены (multi_agent_results.json)
- [ ] Метрики экспортированы

### Анализ результатов
- [ ] Сравнительный отчет сгенерирован
- [ ] Метрики рассчитаны (TSR, TTUA, etc.)
- [ ] Визуализация создана (dashboard)
- [ ] Результаты по категориям проанализированы
- [ ] Гипотезы проверены

### Документация
- [ ] Результаты заполнены в шаблон MULTI_AGENT_POC_RESULTS_TEMPLATE.md
- [ ] Executive Summary написан
- [ ] Рекомендации сформулированы
- [ ] Следующие шаги определены

---

**Примечание:** Эта инструкция предполагает использование существующей инфраструктуры CodeLab AI Service. Для полноценного POC может потребоваться адаптация скриптов под специфику benchmark suite.