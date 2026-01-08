# Сравнение архитектуры работы с базой данных

## Обзор

Этот документ описывает ключевые различия в подходах к работе с базой данных между `auth-service` и `agent-runtime` (до и после миграции).

## Сравнительная таблица

| Аспект | auth-service | agent-runtime (ДО) | agent-runtime (ПОСЛЕ) |
|--------|--------------|-------------------|----------------------|
| **SQLAlchemy** | Async (2.0+) | Sync (2.0+) | Async (2.0+) ✅ |
| **Engine** | `create_async_engine` | `create_engine` | `create_async_engine` ✅ |
| **Session** | `async_sessionmaker` | `sessionmaker` | `async_sessionmaker` ✅ |
| **DateTime** | `DateTime(timezone=True)` | `DateTime` | `DateTime(timezone=True)` ✅ |
| **Dependency Injection** | `Annotated[AsyncSession, Depends(get_db)]` | Прямое создание экземпляра | `Annotated[AsyncSession, Depends(get_db)]` ✅ |
| **Lifecycle** | `lifespan` context manager | Инициализация в конструкторе | `lifespan` context manager ✅ |
| **SQLite оптимизация** | WAL mode, pragmas | Базовая конфигурация | WAL mode, pragmas ✅ |
| **URL конвертация** | Автоматическая для async | Нет | Автоматическая для async ✅ |
| **Паттерн доступа** | Service layer с DI | Singleton Database класс | Service layer с DI ✅ |

## Детальное сравнение

### 1. Инициализация движка БД

#### auth-service
```python
# Автоматическая конвертация URL
if db_url.startswith("sqlite:///"):
    async_db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
else:
    async_db_url = db_url

engine = create_async_engine(
    async_db_url,
    echo=settings.is_development,
    future=True,
)
```

#### agent-runtime (ДО)
```python
# Синхронный движок
if "sqlite" in db_url:
    self.engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
```

#### agent-runtime (ПОСЛЕ)
```python
# Асинхронный движок с автоконвертацией
if db_url.startswith("sqlite:///"):
    async_db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
elif db_url.startswith("postgresql://"):
    async_db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    async_db_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)
```

### 2. Session Factory

#### auth-service
```python
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

#### agent-runtime (ДО)
```python
self.SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=self.engine
)
```

#### agent-runtime (ПОСЛЕ)
```python
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

### 3. Dependency для FastAPI

#### auth-service
```python
# app/models/database.py
async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# app/core/dependencies.py
DBSession = Annotated[AsyncSession, Depends(get_db)]
```

#### agent-runtime (ДО)
```python
# Нет dependency injection
# Прямое использование Database класса
db = Database()
with db.session_scope() as session:
    # операции
```

#### agent-runtime (ПОСЛЕ)
```python
# app/services/database.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# app/core/dependencies.py
DBSession = Annotated[AsyncSession, Depends(get_db)]
DBService = Annotated[DatabaseService, Depends(get_database_service)]
```

### 4. Модели данных

#### auth-service
```python
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),  # ✅ timezone-aware
        default=lambda: datetime.now(timezone.utc)
    )
```

#### agent-runtime (ДО)
```python
class SessionModel(Base):
    __tablename__ = "sessions"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,  # ❌ не timezone-aware
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
```

#### agent-runtime (ПОСЛЕ)
```python
class SessionModel(Base):
    __tablename__ = "sessions"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),  # ✅ timezone-aware
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
```

### 5. Service Layer

#### auth-service
```python
class UserService:
    async def create_user(
        self,
        db: AsyncSession,
        user_data: UserCreate,
    ) -> User:
        # Async операции
        existing_user = await self.get_by_username(db, user_data.username)
        
        user = User(...)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return user

# Singleton instance
user_service = UserService()
```

#### agent-runtime (ДО)
```python
class Database:
    def save_session(self, session_id: str, ...):
        # Синхронные операции
        with self.session_scope() as db:
            session = db.query(SessionModel).filter(...).first()
            # операции
```

#### agent-runtime (ПОСЛЕ)
```python
class DatabaseService:
    async def save_session(
        self,
        db: AsyncSession,
        session_id: str,
        ...
    ) -> None:
        # Async операции
        result = await db.execute(
            select(SessionModel).where(...)
        )
        session = result.scalar_one_or_none()
        # операции
        await db.commit()

# Singleton instance
_database_service = DatabaseService()
```

### 6. Использование в эндпоинтах

#### auth-service
```python
from app.core.dependencies import DBSession, UserServiceDep

@router.post("/users")
async def create_user(
    user_data: UserCreate,
    db: DBSession,
    user_service: UserServiceDep,
):
    user = await user_service.create_user(db, user_data)
    return user
```

#### agent-runtime (ДО)
```python
from app.services.database import Database

@router.post("/sessions/{session_id}")
async def save_session(session_id: str, messages: List[Dict]):
    db = Database()  # Создание экземпляра
    db.save_session(session_id, messages, datetime.now(timezone.utc))
    return {"status": "saved"}
```

#### agent-runtime (ПОСЛЕ)
```python
from app.core.dependencies import DBSession, DBService

@router.post("/sessions/{session_id}")
async def save_session(
    session_id: str,
    messages: List[Dict],
    db: DBSession,
    db_service: DBService,
):
    await db_service.save_session(db, session_id, messages, datetime.now(timezone.utc))
    return {"status": "saved"}
```

### 7. Lifecycle Management

#### auth-service
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Auth Service...")
    
    # Startup
    from app.models import init_db
    await init_db()
    
    yield
    
    # Shutdown
    from app.models import close_db
    await close_db()

app = FastAPI(lifespan=lifespan)
```

#### agent-runtime (ДО)
```python
# Нет lifecycle management
# Инициализация в конструкторе Database класса

app = FastAPI(...)
```

#### agent-runtime (ПОСЛЕ)
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Agent Runtime Service...")
    
    # Startup
    from app.services.database import init_database, init_db
    init_database(AppConfig.DB_URL)
    await init_db()
    
    yield
    
    # Shutdown
    from app.services.database import close_db
    await close_db()

app = FastAPI(lifespan=lifespan)
```

### 8. SQLite оптимизация

#### auth-service
```python
if "sqlite" in db_url:
    sync_engine = create_engine(db_url, echo=settings.is_development)

    @event.listens_for(sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
```

#### agent-runtime (ДО)
```python
# Нет специальной оптимизации для SQLite
```

#### agent-runtime (ПОСЛЕ)
```python
if db_url and "sqlite" in db_url:
    sync_engine = create_engine(db_url, echo=False)

    @event.listens_for(sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
```

## Ключевые преимущества миграции

### 1. Производительность
- **Неблокирующие операции**: Async позволяет обрабатывать другие запросы во время ожидания БД
- **Лучшая конкурентность**: WAL mode в SQLite позволяет одновременное чтение и запись
- **Оптимизация кэша**: 64MB кэш для SQLite улучшает производительность

### 2. Масштабируемость
- **Connection pooling**: Эффективное управление соединениями
- **Pool pre-ping**: Автоматическая проверка соединений перед использованием
- **Async I/O**: Лучшая утилизация ресурсов при высокой нагрузке

### 3. Согласованность
- **Единый подход**: Оба сервиса используют одинаковую архитектуру
- **Переиспользование кода**: Легче делиться паттернами между сервисами
- **Упрощенная поддержка**: Одна модель для изучения и поддержки

### 4. Типобезопасность
- **Annotated типы**: Явная типизация зависимостей
- **IDE поддержка**: Лучший autocomplete и проверка типов
- **Меньше ошибок**: Ошибки типов обнаруживаются на этапе разработки

### 5. Timezone support
- **Корректная работа с UTC**: Все timestamp'ы timezone-aware
- **Предотвращение багов**: Нет проблем с конвертацией временных зон
- **Совместимость с PostgreSQL**: Правильная работа с TIMESTAMP WITH TIME ZONE

## Рекомендации

### Для новых сервисов
1. Используйте async SQLAlchemy с самого начала
2. Применяйте dependency injection паттерн
3. Используйте `DateTime(timezone=True)` для всех timestamp полей
4. Настраивайте SQLite оптимизации для production

### Для существующих сервисов
1. Планируйте миграцию на async постепенно
2. Начните с новых эндпоинтов
3. Обновите тесты для поддержки async
4. Документируйте изменения для команды

### Общие best practices
1. Всегда используйте `pool_pre_ping=True` для production
2. Настраивайте размер connection pool в зависимости от нагрузки
3. Используйте soft delete для важных данных
4. Добавляйте индексы для часто используемых запросов
5. Логируйте медленные запросы для оптимизации

## Заключение

Миграция `agent-runtime` на асинхронную архитектуру работы с базой данных приводит его в соответствие с `auth-service` и современными best practices. Это обеспечивает:

- ✅ Лучшую производительность
- ✅ Большую масштабируемость
- ✅ Согласованность архитектуры
- ✅ Упрощенную поддержку
- ✅ Готовность к production нагрузкам

Все изменения обратно несовместимы, но обеспечивают прочную основу для дальнейшего развития сервиса.
