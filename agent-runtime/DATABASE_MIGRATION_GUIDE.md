# Руководство по миграции базы данных

## Что изменилось

Структура базы данных была полностью переработана с улучшенной нормализацией и новыми возможностями.

### Старая структура (2 таблицы)
- `sessions` - хранила session_id и JSON с сообщениями
- `agent_contexts` - хранила контекст агента и JSON с историей

### Новая структура (4 таблицы)
- `sessions` - основная информация о сессии
- `messages` - отдельная таблица для каждого сообщения
- `agent_contexts` - контекст агента
- `agent_switches` - история переключений агентов

## Ключевые улучшения

### 1. Нормализация данных
- Сообщения теперь хранятся в отдельной таблице
- История переключений агентов в отдельной таблице
- Foreign Keys с каскадным удалением

### 2. Новые возможности
- **Пагинация сообщений**: `get_messages_paginated()`
- **Статистика сессий**: `get_session_stats()`
- **История переключений**: `get_agent_switch_history()`
- **Soft delete**: возможность мягкого удаления с восстановлением

### 3. Производительность
- Композитные индексы для частых запросов
- Оптимизированные запросы с JOIN
- Connection pooling для production

## API (обратная совместимость)

Все существующие методы работают без изменений:

```python
from app.services.database import Database

db = Database()

# Сохранение сессии (как раньше)
db.save_session(session_id, messages, last_activity)

# Загрузка сессии (как раньше)
session = db.load_session(session_id)

# Сохранение контекста агента (как раньше)
db.save_agent_context(session_id, current_agent, agent_history, ...)

# Загрузка контекста агента (как раньше)
context = db.load_agent_context(session_id)
```

## Новые методы

### Пагинация сообщений
```python
# Получить первую страницу (20 сообщений)
messages = db.get_messages_paginated(session_id, page=1, page_size=20)

# Получить вторую страницу
messages = db.get_messages_paginated(session_id, page=2, page_size=20)
```

### Статистика сессии
```python
stats = db.get_session_stats(session_id)
# {
#     "session_id": "...",
#     "message_count": 100,
#     "total_tokens": 5000,
#     "last_message_at": datetime(...),
#     "created_at": datetime(...),
#     "last_activity": datetime(...)
# }
```

### История переключений агентов
```python
switches = db.get_agent_switch_history(session_id, limit=100)
# [
#     {
#         "id": 1,
#         "from_agent": "orchestrator",
#         "to_agent": "coder",
#         "switched_at": datetime(...),
#         "reason": "User requested code changes",
#         "metadata": {}
#     },
#     ...
# ]
```

### Soft Delete
```python
# Мягкое удаление (по умолчанию)
db.delete_session(session_id, soft=True)

# Жесткое удаление
db.delete_session(session_id, soft=False)

# Список активных сессий (без удаленных)
sessions = db.list_all_sessions(include_deleted=False)

# Список всех сессий (включая удаленные)
all_sessions = db.list_all_sessions(include_deleted=True)
```

### Очистка старых данных
```python
# Мягкое удаление сессий старше 24 часов
cleaned = db.cleanup_old_sessions(max_age_hours=24)

# Жесткое удаление сессий, удаленных более 30 дней назад
deleted = db.hard_delete_old_sessions(days_old=30)
```

## Context Manager для транзакций

```python
# Использование context manager для безопасных транзакций
with db.session_scope() as session:
    # Выполнение операций
    session.query(...)
    # Автоматический commit при успехе
    # Автоматический rollback при ошибке
```

## Миграция данных

Поскольку структура полностью изменилась, рекомендуется:

1. **Для разработки**: Удалить старую БД и создать новую
   ```bash
   rm data/agent_runtime.db
   # БД будет создана автоматически при первом запуске
   ```

2. **Для production**: Если нужно сохранить данные, используйте скрипт миграции из `DATABASE_IMPROVEMENT_RECOMMENDATIONS.md`

## Тестирование

Запустите тесты для проверки новой структуры:

```bash
cd codelab-ai-service/agent-runtime
uv run python test_database_improvements.py
```

Тесты проверяют:
- ✓ Создание и загрузку сессий
- ✓ Пагинацию сообщений
- ✓ Статистику сессий
- ✓ Контекст агентов
- ✓ Историю переключений
- ✓ Soft delete
- ✓ Очистку старых данных
- ✓ Обратную совместимость

## Схема базы данных

```
sessions
├── id (PK, autoincrement)
├── session_id (unique, indexed)
├── created_at
├── last_activity (indexed)
├── is_active (indexed)
└── deleted_at (soft delete)

messages
├── id (PK, autoincrement)
├── session_db_id (FK -> sessions.id)
├── role (indexed)
├── content
├── timestamp (indexed)
├── name
├── tool_call_id
├── tool_calls (JSON)
├── token_count
└── metadata_json (JSON)

agent_contexts
├── id (PK, autoincrement)
├── session_db_id (FK -> sessions.id, unique)
├── current_agent (indexed)
├── created_at
├── updated_at
├── switch_count
└── metadata_json (JSON)

agent_switches
├── id (PK, autoincrement)
├── context_db_id (FK -> agent_contexts.id)
├── from_agent
├── to_agent
├── switched_at (indexed)
├── reason
└── metadata_json (JSON)
```

## Индексы

Созданы следующие индексы для оптимизации:

- `idx_session_activity` - (session_id, last_activity)
- `idx_active_sessions` - (is_active, last_activity)
- `idx_session_timestamp` - (session_db_id, timestamp)
- `idx_role_timestamp` - (role, timestamp)
- `idx_context_switched` - (context_db_id, switched_at)

## Производительность

Ожидаемые улучшения:
- **Поиск сообщений**: 50-70% быстрее благодаря индексам
- **Пагинация**: эффективная работа с большими историями
- **Аналитика**: быстрые агрегации на уровне БД
- **Масштабируемость**: готовность к росту данных

## Поддержка PostgreSQL

Для использования PostgreSQL вместо SQLite:

```python
db = Database(db_url="postgresql://user:password@localhost/dbname")
```

PostgreSQL предоставляет дополнительные возможности:
- Нативный тип JSONB для метаданных
- Лучшая производительность для больших объемов
- Полнотекстовый поиск
- Расширенные индексы (GIN, GiST)

## Troubleshooting

### Ошибка "no such column"
Удалите старую БД и создайте новую:
```bash
rm data/agent_runtime.db
```

### Медленные запросы
Проверьте индексы:
```python
# Включите логирование SQL
db = Database(db_url="sqlite:///data/agent_runtime.db")
db.engine.echo = True
```

### Проблемы с миграцией
Используйте Alembic для управления миграциями (см. `DATABASE_IMPROVEMENT_RECOMMENDATIONS.md`)

## Дополнительная информация

Подробный анализ и рекомендации см. в `DATABASE_IMPROVEMENT_RECOMMENDATIONS.md`
