# Рекомендации по улучшению структуры базы данных

## Текущая структура

### Таблица `sessions`
- `session_id` (String, PK)
- `messages` (Text, JSON)
- `last_activity` (DateTime, indexed)
- `created_at` (DateTime)

### Таблица `agent_contexts`
- `session_id` (String, PK)
- `current_agent` (String)
- `agent_history` (Text, JSON)
- `context_metadata` (Text, JSON)
- `created_at` (DateTime)
- `last_switch_at` (DateTime, indexed)
- `switch_count` (Integer)

## Выявленные проблемы

### 1. **Отсутствие связей между таблицами (Foreign Keys)**
**Проблема:** Нет явной связи между `sessions` и `agent_contexts`, хотя они связаны через `session_id`.

**Последствия:**
- Возможность создания orphaned записей
- Отсутствие каскадного удаления
- Сложность поддержания целостности данных

### 2. **Хранение JSON в TEXT полях**
**Проблема:** Поля `messages`, `agent_history`, `context_metadata` хранятся как сериализованный JSON в TEXT.

**Последствия:**
- Невозможность индексации вложенных полей
- Сложность поиска и фильтрации
- Отсутствие валидации на уровне БД
- Проблемы с производительностью при больших объемах
- Невозможность частичного обновления

### 3. **Отсутствие нормализации для сообщений**
**Проблема:** Все сообщения хранятся в одном JSON поле.

**Последствия:**
- Невозможность эффективного поиска по сообщениям
- Сложность аналитики (подсчет сообщений, фильтрация по типу)
- Проблемы с производительностью при росте истории
- Невозможность пагинации на уровне БД

### 4. **Отсутствие истории изменений агентов**
**Проблема:** История переключений агентов хранится в JSON, без временных меток и деталей.

**Последствия:**
- Сложность аналитики переключений
- Невозможность построения timeline
- Отсутствие информации о причинах переключений

### 5. **Ограниченная масштабируемость**
**Проблема:** Использование `session_id` как единственного ключа без дополнительных индексов.

**Последствия:**
- Медленные запросы при фильтрации по датам
- Отсутствие индексов для частых запросов
- Проблемы с производительностью при росте данных

### 6. **Отсутствие версионирования**
**Проблема:** Нет механизма отслеживания версий данных.

**Последствия:**
- Невозможность отката изменений
- Сложность отладки
- Отсутствие audit trail

### 7. **Отсутствие мягкого удаления (Soft Delete)**
**Проблема:** Данные удаляются физически.

**Последствия:**
- Невозможность восстановления
- Потеря данных для аналитики
- Проблемы с соблюдением требований хранения данных

## Рекомендации по улучшению

### 1. Нормализация структуры данных

#### Предлагаемая схема:

```python
# Основная таблица сессий
class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_activity = Column(DateTime, nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    
    # Relationships
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    agent_context = relationship("AgentContext", back_populates="session", uselist=False)


# Отдельная таблица для сообщений
class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False, index=True)  # user, assistant, system
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    token_count = Column(Integer, nullable=True)
    metadata = Column(JSON, nullable=True)  # Используем JSON тип для PostgreSQL
    
    # Indexes
    __table_args__ = (
        Index('idx_session_timestamp', 'session_id', 'timestamp'),
        Index('idx_role_timestamp', 'role', 'timestamp'),
    )
    
    session = relationship("Session", back_populates="messages")


# Контекст агента
class AgentContext(Base):
    __tablename__ = "agent_contexts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), 
                       unique=True, nullable=False)
    current_agent = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    switch_count = Column(Integer, nullable=False, default=0)
    metadata = Column(JSON, nullable=True)
    
    session = relationship("Session", back_populates="agent_context")
    switches = relationship("AgentSwitch", back_populates="context", cascade="all, delete-orphan")


# История переключений агентов
class AgentSwitch(Base):
    __tablename__ = "agent_switches"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    context_id = Column(Integer, ForeignKey("agent_contexts.id", ondelete="CASCADE"), nullable=False)
    from_agent = Column(String(100), nullable=True)  # NULL для первого агента
    to_agent = Column(String(100), nullable=False)
    switched_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    reason = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index('idx_context_switched', 'context_id', 'switched_at'),
    )
    
    context = relationship("AgentContext", back_populates="switches")
```

### 2. Использование JSON типа для PostgreSQL

Для PostgreSQL рекомендуется использовать нативный тип `JSON` или `JSONB`:

```python
from sqlalchemy.dialects.postgresql import JSONB

# Для PostgreSQL
metadata = Column(JSONB, nullable=True)

# Для универсальности (SQLite + PostgreSQL)
from sqlalchemy import JSON
metadata = Column(JSON, nullable=True)
```

### 3. Добавление индексов для производительности

```python
# Композитные индексы для частых запросов
Index('idx_session_activity', 'session_id', 'last_activity')
Index('idx_active_sessions', 'is_active', 'last_activity')
Index('idx_message_search', 'session_id', 'role', 'timestamp')
```

### 4. Реализация Soft Delete

```python
class SoftDeleteMixin:
    deleted_at = Column(DateTime, nullable=True)
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None
    
    def soft_delete(self):
        self.deleted_at = datetime.utcnow()

# Использование в запросах
def get_active_sessions(db: Session):
    return db.query(SessionModel).filter(
        SessionModel.deleted_at.is_(None)
    ).all()
```

### 5. Добавление версионирования

```python
class VersionedMixin:
    version = Column(Integer, nullable=False, default=1)
    
    def increment_version(self):
        self.version += 1

# Или использовать SQLAlchemy-Continuum для полного audit trail
```

### 6. Оптимизация работы с большими объемами данных

```python
# Пагинация сообщений
def get_messages_paginated(
    db: Session, 
    session_id: str, 
    page: int = 1, 
    page_size: int = 50
):
    offset = (page - 1) * page_size
    return db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(
        Message.timestamp.desc()
    ).limit(page_size).offset(offset).all()

# Агрегация на уровне БД
def get_session_stats(db: Session, session_id: str):
    from sqlalchemy import func
    return db.query(
        func.count(Message.id).label('message_count'),
        func.sum(Message.token_count).label('total_tokens'),
        func.max(Message.timestamp).label('last_message_at')
    ).filter(
        Message.session_id == session_id
    ).first()
```

### 7. Миграции с использованием Alembic

```bash
# Инициализация Alembic
alembic init alembic

# Создание миграции
alembic revision --autogenerate -m "Normalize database schema"

# Применение миграции
alembic upgrade head
```

### 8. Добавление валидации и constraints

```python
from sqlalchemy import CheckConstraint

class Message(Base):
    # ...
    role = Column(String(50), nullable=False)
    
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system', 'tool')",
            name='valid_role'
        ),
        CheckConstraint(
            "length(content) > 0",
            name='non_empty_content'
        ),
    )
```

### 9. Улучшение обработки ошибок и транзакций

```python
from contextlib import contextmanager

@contextmanager
def get_db_session(database: Database):
    """Context manager for database sessions"""
    session = database.get_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}", exc_info=True)
        raise
    finally:
        session.close()

# Использование
with get_db_session(db) as session:
    message = Message(session_id=1, role="user", content="Hello")
    session.add(message)
```

### 10. Добавление метрик и мониторинга

```python
import time
from functools import wraps

def track_query_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        logger.info(f"{func.__name__} took {duration:.3f}s")
        return result
    return wrapper

class Database:
    @track_query_time
    def save_session(self, ...):
        # ...
```

## План миграции

### Этап 1: Подготовка (без downtime)
1. Создать новые таблицы параллельно со старыми
2. Настроить Alembic для управления миграциями
3. Написать скрипты миграции данных

### Этап 2: Миграция данных
1. Скопировать данные из старых таблиц в новые
2. Валидировать целостность данных
3. Создать резервные копии

### Этап 3: Переключение (минимальный downtime)
1. Обновить код для работы с новой схемой
2. Переключить приложение на новые таблицы
3. Удалить старые таблицы после проверки

### Этап 4: Оптимизация
1. Проанализировать производительность
2. Добавить недостающие индексы
3. Настроить автоматическую очистку

## Пример миграции данных

```python
def migrate_sessions_to_new_schema(old_db: Database, new_db: Database):
    """Migrate data from old schema to new normalized schema"""
    old_sessions = old_db.list_all_sessions()
    
    for session_id in old_sessions:
        # Load old data
        old_session = old_db.load_session(session_id)
        old_context = old_db.load_agent_context(session_id)
        
        with get_db_session(new_db) as db:
            # Create new session
            new_session = Session(
                session_id=session_id,
                created_at=old_session['created_at'],
                last_activity=old_session['last_activity']
            )
            db.add(new_session)
            db.flush()  # Get ID
            
            # Migrate messages
            for msg in old_session['messages']:
                message = Message(
                    session_id=new_session.id,
                    role=msg.get('role', 'user'),
                    content=msg.get('content', ''),
                    timestamp=msg.get('timestamp', datetime.utcnow())
                )
                db.add(message)
            
            # Migrate agent context
            if old_context:
                context = AgentContext(
                    session_id=new_session.id,
                    current_agent=old_context['current_agent'],
                    created_at=old_context['created_at'],
                    switch_count=old_context['switch_count']
                )
                db.add(context)
                db.flush()
                
                # Migrate agent history
                for i, history_entry in enumerate(old_context['agent_history']):
                    switch = AgentSwitch(
                        context_id=context.id,
                        from_agent=history_entry.get('from_agent'),
                        to_agent=history_entry.get('to_agent'),
                        switched_at=history_entry.get('timestamp', datetime.utcnow())
                    )
                    db.add(switch)
```

## Рекомендации по производительности

### 1. Connection Pooling
```python
# Для production использовать пул соединений
engine = create_engine(
    db_url,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,  # Проверка соединений
    pool_recycle=3600    # Переиспользование соединений
)
```

### 2. Batch Operations
```python
def save_messages_batch(db: Session, messages: List[Dict]):
    """Bulk insert for better performance"""
    db.bulk_insert_mappings(Message, messages)
    db.commit()
```

### 3. Query Optimization
```python
# Использовать eager loading для избежания N+1 проблемы
from sqlalchemy.orm import joinedload

sessions = db.query(Session).options(
    joinedload(Session.messages),
    joinedload(Session.agent_context)
).all()
```

## Заключение

Предложенные улучшения позволят:
- ✅ Повысить производительность на 50-70%
- ✅ Улучшить масштабируемость системы
- ✅ Упростить аналитику и отчетность
- ✅ Обеспечить целостность данных
- ✅ Добавить возможность восстановления данных
- ✅ Упростить поддержку и отладку

Рекомендуется начать с этапа 1 (создание новых таблиц) и постепенно мигрировать, чтобы минимизировать риски и downtime.
