# МЕТРИКИ ПО SESSION_ID - PROPOSAL

**Дата:** 17 января 2026

---

## ТЕКУЩЕЕ СОСТОЯНИЕ

**MetricsCollector** собирает метрики **глобально** (для всех сессий):

```python
metrics = {
    "agent_switches": {"orchestrator_to_coder": 15},  # Всего
    "agent_processing": {"coder": {"count": 20}},     # Всего
    ...
}
```

**Нет группировки по session_id.**

---

## ПРЕДЛОЖЕНИЕ: SessionMetricsCollector

### Реализация

```python
# app/events/subscribers/session_metrics_collector.py

class SessionMetricsCollector:
    """Собирает метрики по каждой сессии отдельно."""
    
    def __init__(self):
        # Метрики по сессиям
        self._session_metrics: Dict[str, Dict] = {}
        
        event_bus.subscribe(
            event_category=EventCategory.AGENT,
            handler=self._collect_agent_metrics
        )
        event_bus.subscribe(
            event_category=EventCategory.TOOL,
            handler=self._collect_tool_metrics
        )
    
    async def _collect_agent_metrics(self, event):
        session_id = event.session_id
        if not session_id:
            return
        
        # Инициализировать метрики сессии
        if session_id not in self._session_metrics:
            self._session_metrics[session_id] = {
                "agent_switches": 0,
                "tool_calls": 0,
                "processing_duration_ms": 0,
                "errors": 0
            }
        
        metrics = self._session_metrics[session_id]
        
        if event.event_type == EventType.AGENT_SWITCHED:
            metrics["agent_switches"] += 1
        
        elif event.event_type == EventType.AGENT_PROCESSING_COMPLETED:
            metrics["processing_duration_ms"] += event.data["duration_ms"]
        
        elif event.event_type == EventType.AGENT_ERROR_OCCURRED:
            metrics["errors"] += 1
    
    async def _collect_tool_metrics(self, event):
        session_id = event.session_id
        if not session_id:
            return
        
        if session_id not in self._session_metrics:
            self._session_metrics[session_id] = {
                "agent_switches": 0,
                "tool_calls": 0,
                "processing_duration_ms": 0,
                "errors": 0
            }
        
        if event.event_type == EventType.TOOL_EXECUTION_REQUESTED:
            self._session_metrics[session_id]["tool_calls"] += 1
    
    def get_session_metrics(self, session_id: str) -> Dict:
        """Получить метрики конкретной сессии."""
        return self._session_metrics.get(session_id, {
            "agent_switches": 0,
            "tool_calls": 0,
            "processing_duration_ms": 0,
            "errors": 0
        })
    
    def get_all_sessions(self) -> Dict[str, Dict]:
        """Получить метрики всех сессий."""
        return self._session_metrics.copy()

# Singleton
session_metrics_collector = SessionMetricsCollector()
```

### API Endpoint

```python
# app/api/v1/endpoints.py

@router.get("/events/metrics/session/{session_id}")
async def get_session_metrics(session_id: str):
    """Получить метрики конкретной сессии."""
    from app.events.subscribers import session_metrics_collector
    
    metrics = session_metrics_collector.get_session_metrics(session_id)
    
    return {
        "session_id": session_id,
        "metrics": metrics,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
```

### Использование

```python
# Python API
from app.events.subscribers import session_metrics_collector

metrics = session_metrics_collector.get_session_metrics("session-123")

# REST API
curl http://localhost:8001/events/metrics/session/session-123

# Ответ:
{
  "session_id": "session-123",
  "metrics": {
    "agent_switches": 3,
    "tool_calls": 5,
    "processing_duration_ms": 4500,
    "errors": 0
  },
  "timestamp": "2026-01-17T15:00:00Z"
}
```

---

## АЛЬТЕРНАТИВА: Использовать Audit Log

**Текущее решение (уже работает):**

```python
from app.events.subscribers import audit_logger

# Получить все события сессии
log = audit_logger.get_audit_log(session_id="session-123")

# Вычислить метрики
agent_switches = len([e for e in log if e["event_type"] == "agent_switched"])
tool_approvals = len([e for e in log if e["event_type"] == "tool_approval_required"])
hitl_decisions = len([e for e in log if e["event_type"] == "hitl_decision_made"])

# Через REST API
curl "http://localhost:8001/events/audit-log?session_id=session-123"
```

**Преимущества:**
- ✅ Уже реализовано
- ✅ Работает сейчас
- ✅ Полная история событий

**Недостатки:**
- Нужно вычислять метрики вручную
- Нет готовых агрегаций

---

## РЕКОМЕНДАЦИЯ

### Для немедленного использования:

**Используйте Audit Log** - уже работает:

```bash
curl "http://localhost:8001/events/audit-log?session_id=session-123"
```

Затем вычислите нужные метрики из событий.

### Для удобства (опционально):

**Реализуйте SessionMetricsCollector** - если нужны готовые агрегации по сессиям.

**Оценка:** 0.5 дня

**Приоритет:** Низкий (audit log достаточен)

---

**Вывод:** Метрики по session_id можно получить через audit log (уже работает) или добавить SessionMetricsCollector для удобства (опционально).
