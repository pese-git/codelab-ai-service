# РУКОВОДСТВО ПО СБОРУ МЕТРИК

**Дата:** 17 января 2026  
**Версия:** 1.0

---

## ДОСТУПНЫЕ МЕТРИКИ

### 1. Метрики агентов (через MetricsCollector)

**Что собирается автоматически:**
- Переключения агентов (по парам from/to)
- Длительность обработки (по агентам)
- Успешность/неуспешность обработки
- Ошибки (по агентам и типам)

**Как получить:**

```python
from app.events.subscribers import metrics_collector

# Все метрики
metrics = metrics_collector.get_metrics()

# Структура:
{
    "agent_switches": {
        "orchestrator_to_coder": 15,
        "coder_to_debug": 3,
        ...
    },
    "agent_processing": {
        "coder": {
            "count": 20,
            "total_duration_ms": 30000,
            "success_count": 18,
            "failure_count": 2
        },
        ...
    },
    "tool_executions": {
        "write_file": {
            "requested": 10,
            "completed": 8,
            "failed": 2,
            "requires_approval": 10
        },
        ...
    },
    "hitl_decisions": {
        "write_file": {
            "APPROVE": 7,
            "EDIT": 2,
            "REJECT": 1
        },
        ...
    },
    "errors": {
        "coder": {
            "FileNotFoundError": 1,
            "ValueError": 1
        },
        ...
    }
}

# Конкретные метрики
avg_duration = metrics_collector.get_agent_avg_duration("coder")
success_rate = metrics_collector.get_tool_success_rate("write_file")
switch_count = metrics_collector.get_agent_switch_count("orchestrator", "coder")
```

### 2. Метрики через REST API

```bash
# Получить все метрики
curl http://localhost:8001/events/metrics

# Ответ:
{
  "metrics": {
    "agent_switches": {...},
    "agent_processing": {...},
    "tool_executions": {...},
    "hitl_decisions": {...},
    "errors": {...}
  },
  "computed": {
    "coder_avg_duration_ms": 1500.5,
    "write_file_success_rate": 0.933
  },
  "timestamp": "2026-01-17T15:00:00Z"
}
```

### 3. Метрики для Benchmark

**Для benchmark-standalone нужны:**
- Total LLM Calls
- Input/Output Tokens
- Total Cost
- Total Tool Calls
- Total Agent Switches
- Task Duration

**Текущее состояние:**
- ✅ Total Tool Calls - есть в `metrics["tool_executions"]`
- ✅ Total Agent Switches - есть в `metrics["agent_switches"]`
- ✅ Task Duration - есть в `metrics["agent_processing"]`
- ❌ LLM Calls/Tokens/Cost - НЕТ (не собираются)

---

## КАК ДОБАВИТЬ LLM МЕТРИКИ

### Вариант 1: Добавить события в LLMProxyClient

```python
# app/services/llm_proxy_client.py

from app.events.event_bus import event_bus
from app.events.base_event import BaseEvent
from app.events.event_types import EventType, EventCategory

# Добавить новый тип события
class LLMRequestCompletedEvent(BaseEvent):
    def __init__(
        self,
        session_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost: float,
        duration_ms: float
    ):
        super().__init__(
            event_type=EventType.LLM_REQUEST_COMPLETED,  # Добавить в EventType
            event_category=EventCategory.METRICS,
            session_id=session_id,
            data={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost": cost,
                "duration_ms": duration_ms
            },
            source="llm_proxy_client"
        )

# В llm_proxy_client.py
async def chat_completion(self, model, messages, tools=None, ...):
    start_time = time.time()
    
    response = await self.client.post(...)
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Извлечь usage из ответа
    usage = response.json().get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)
    
    # Вычислить стоимость (примерно)
    cost = calculate_cost(model, input_tokens, output_tokens)
    
    # Публиковать событие
    await event_bus.publish(
        LLMRequestCompletedEvent(
            session_id=session_id,  # Нужно передать
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=cost,
            duration_ms=duration_ms
        )
    )
    
    return response.json()
```

### Вариант 2: Собирать из LLM Proxy ответов

```python
# В LLMStreamService или MultiAgentOrchestrator
# После вызова LLM
response = await llm_proxy_client.chat_completion(...)

# Извлечь usage
usage = response.get("usage", {})

# Публиковать событие
await event_bus.publish(
    LLMRequestCompletedEvent(
        session_id=session_id,
        model=model,
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        cost=calculate_cost(...),
        duration_ms=duration
    )
)
```

### Вариант 3: Подписчик для LLM метрик

```python
# app/events/subscribers/llm_metrics_collector.py

class LLMMetricsCollector:
    def __init__(self):
        self.total_llm_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        
        event_bus.subscribe(
            event_type=EventType.LLM_REQUEST_COMPLETED,
            handler=self._collect
        )
    
    async def _collect(self, event):
        self.total_llm_calls += 1
        self.total_input_tokens += event.data["input_tokens"]
        self.total_output_tokens += event.data["output_tokens"]
        self.total_cost += event.data["cost"]
    
    def get_metrics(self):
        return {
            "total_llm_calls": self.total_llm_calls,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_cost": self.total_cost
        }
```

---

## ИНТЕГРАЦИЯ С BENCHMARK-STANDALONE

### Способ 1: REST API (рекомендуется)

```python
# В benchmark-standalone/src/collector.py

import httpx

class AgentRuntimeMetricsCollector:
    def __init__(self, agent_runtime_url: str):
        self.url = agent_runtime_url
    
    async def collect_metrics(self, session_id: str = None):
        """Собрать метрики из agent-runtime."""
        
        # Получить метрики событий
        response = await httpx.get(f"{self.url}/events/metrics")
        event_metrics = response.json()
        
        # Извлечь нужные данные
        metrics = event_metrics["metrics"]
        computed = event_metrics["computed"]
        
        return {
            "total_agent_switches": sum(metrics["agent_switches"].values()),
            "total_tool_calls": sum(
                m["requested"] 
                for m in metrics["tool_executions"].values()
            ),
            "avg_task_duration": computed.get("coder_avg_duration_ms", 0),
            "success_rate": computed.get("write_file_success_rate", 0),
            # LLM метрики (если добавлены)
            "total_llm_calls": metrics.get("llm_calls", {}).get("total", 0),
            "input_tokens": metrics.get("llm_calls", {}).get("input_tokens", 0),
            "output_tokens": metrics.get("llm_calls", {}).get("output_tokens", 0),
            "estimated_cost": metrics.get("llm_calls", {}).get("cost", 0.0)
        }

# Использование
collector = AgentRuntimeMetricsCollector("http://localhost:8001")
metrics = await collector.collect_metrics()
```

### Способ 2: Прямой импорт (если в одном процессе)

```python
# В benchmark-standalone
from app.events.subscribers import metrics_collector

metrics = metrics_collector.get_metrics()

# Преобразовать в формат benchmark
benchmark_metrics = {
    "total_agent_switches": sum(metrics["agent_switches"].values()),
    "total_tool_calls": sum(
        m["requested"] 
        for m in metrics["tool_executions"].values()
    ),
    # ...
}
```

---

## РЕКОМЕНДАЦИИ

### Для текущего использования

**Используйте существующие метрики:**
- Total Agent Switches ✅
- Total Tool Calls ✅
- Avg Task Duration ✅
- Success Rate ✅

**Получайте через REST API:**
```bash
curl http://localhost:8001/events/metrics
```

### Для добавления LLM метрик

**Если нужны Input/Output Tokens и Cost:**

1. Добавить `LLMRequestCompletedEvent` в `event_types.py`
2. Публиковать из `llm_proxy_client.py` или `llm_stream_service.py`
3. Создать `LLMMetricsCollector` подписчик
4. Добавить в API endpoint `/events/metrics`

**Оценка:** 0.5-1 день

**Приоритет:** Средний (если нужно для benchmark)

---

## ЗАКЛЮЧЕНИЕ

**Текущие метрики достаточны для:**
- Мониторинга производительности
- Анализа использования агентов
- Статистики инструментов
- HITL аналитики

**LLM метрики (tokens, cost) можно добавить** если нужны для benchmark-standalone, но это не критично для основной функциональности.

---

**Версия документа:** 1.0  
**Дата:** 17 января 2026
