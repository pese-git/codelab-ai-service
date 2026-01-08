# Резюме: Поддержка PostgreSQL в codelab-ai-service

## Обзор изменений

Проект теперь поддерживает работу как с **SQLite** (для разработки), так и с **PostgreSQL** (для production). Переключение между СУБД осуществляется через переменные окружения.

## Что было сделано

### 1. Обновлена конфигурация agent-runtime

**Файлы:**
- [`agent-runtime/app/core/config.py`](./agent-runtime/app/core/config.py) - добавлена переменная `DB_URL`
- [`agent-runtime/app/services/database.py`](./agent-runtime/app/services/database.py) - использование `AppConfig.DB_URL`
- [`agent-runtime/.env.example`](./agent-runtime/.env.example) - примеры конфигурации для обеих БД

**Изменения:**
```python
# Добавлено в AppConfig
DB_URL: str = os.getenv(
    "AGENT_RUNTIME__DB_URL",
    "sqlite:///data/agent_runtime.db"  # По умолчанию SQLite
)
```

### 2. Обновлена конфигурация auth-service

**Файлы:**
- [`auth-service/.env.example`](./auth-service/.env.example) - примеры конфигурации для обеих БД

**Примечание:** `auth-service` уже имел поддержку переменной `db_url` в настройках, поэтому требовалось только обновить документацию.

### 3. Добавлен PostgreSQL в Docker Compose

**Файл:** [`docker-compose.yml`](./docker-compose.yml)

**Добавлено:**
- Сервис `postgres` с PostgreSQL 16
- Volume `postgres-data` для персистентности данных
- Healthcheck для проверки готовности PostgreSQL
- Скрипт инициализации для создания баз данных

### 4. Создан скрипт инициализации PostgreSQL

**Файл:** [`scripts/init-postgres.sh`](./scripts/init-postgres.sh)

**Функционал:**
- Автоматическое создание базы данных `agent_runtime`
- Автоматическое создание базы данных `auth_db`
- Выполняется при первом запуске PostgreSQL контейнера

### 5. Обновлены переменные окружения

**Файл:** [`.env`](./env)

**Добавлено:**
```bash
# PostgreSQL настройки
POSTGRES_USER=codelab
POSTGRES_PASSWORD=codelab_password
POSTGRES_DB=codelab

# Примеры для agent-runtime (закомментированы)
# AGENT_RUNTIME__DB_URL=postgresql://codelab:codelab_password@postgres:5432/agent_runtime

# Примеры для auth-service (закомментированы)
# AUTH_SERVICE__DB_URL=postgresql+asyncpg://codelab:codelab_password@postgres:5432/auth_db
```

### 6. Добавлены зависимости для PostgreSQL

**agent-runtime** ([`pyproject.toml`](./agent-runtime/pyproject.toml)):
- ✅ Добавлен `psycopg2-binary>=2.9.9` для синхронного подключения к PostgreSQL

**auth-service** ([`pyproject.toml`](./auth-service/pyproject.toml)):
- ✅ Добавлен `asyncpg>=0.29.0` для асинхронного подключения к PostgreSQL

### 7. Создана документация

**Файлы:**
- [`DATABASE_CONFIGURATION.md`](./DATABASE_CONFIGURATION.md) - полная документация по конфигурации БД
- [`POSTGRES_QUICKSTART.md`](./POSTGRES_QUICKSTART.md) - краткое руководство по быстрому старту

## Как использовать

### Разработка (SQLite) - по умолчанию

Ничего менять не нужно:

```bash
docker-compose up -d
```

### Production (PostgreSQL)

1. Пересоберите Docker образы (для установки новых зависимостей):
```bash
docker-compose build agent-runtime auth-service
```

2. Отредактируйте `.env`:
```bash
AGENT_RUNTIME__DB_URL=postgresql://codelab:codelab_password@postgres:5432/agent_runtime
AUTH_SERVICE__DB_URL=postgresql+asyncpg://codelab:codelab_password@postgres:5432/auth_db
```

3. Запустите сервисы:
```bash
docker-compose up -d
```

## Ключевые особенности

### Гибкость
- ✅ Каждый сервис может использовать свою СУБД независимо
- ✅ Переключение через переменные окружения
- ✅ Без изменения кода

### Совместимость
- ✅ SQLite для разработки и тестирования
- ✅ PostgreSQL для production
- ✅ Обратная совместимость с существующими настройками

### Автоматизация
- ✅ Автоматическое создание таблиц при старте
- ✅ Автоматическая инициализация баз данных PostgreSQL
- ✅ Healthcheck для PostgreSQL

## Важные замечания

### Драйверы

**agent-runtime** использует синхронный драйвер:
```bash
postgresql://user:password@host:port/database
```

**auth-service** использует асинхронный драйвер `asyncpg`:
```bash
postgresql+asyncpg://user:password@host:port/database
```

### Зависимости

Для работы с PostgreSQL необходимо добавить в зависимости:

**agent-runtime:**
```toml
psycopg2-binary = "^2.9.9"  # или asyncpg для async
```

**auth-service:**
```toml
asyncpg = "^0.29.0"  # уже должен быть установлен
```

### Миграция данных

При переключении с SQLite на PostgreSQL:
1. Таблицы создаются автоматически
2. Данные НЕ мигрируются автоматически
3. Для миграции данных используйте инструменты экспорта/импорта

## Структура баз данных

### agent-runtime (agent_runtime)

Таблицы:
- `sessions` - сессии агентов
- `messages` - история сообщений
- `agent_contexts` - контексты агентов
- `agent_switches` - история переключений агентов
- `pending_approvals` - ожидающие подтверждения (HITL)

### auth-service (auth_db)

Таблицы:
- `users` - пользователи
- `oauth_clients` - OAuth клиенты
- `refresh_tokens` - refresh токены
- `audit_logs` - логи аудита

## Проверка работы

### Проверка подключения к PostgreSQL

```bash
# Проверить что PostgreSQL запущен
docker-compose ps postgres

# Подключиться к базе agent_runtime
docker-compose exec postgres psql -U codelab -d agent_runtime

# Подключиться к базе auth_db
docker-compose exec postgres psql -U codelab -d auth_db

# Посмотреть таблицы
\dt
```

### Проверка логов сервисов

```bash
# agent-runtime
docker-compose logs agent-runtime | grep -i database

# auth-service
docker-compose logs auth-service | grep -i database
```

Должны увидеть строки типа:
```
Database initialized with URL: postgresql://codelab:***@postgres:5432/agent_runtime
```

## Резервное копирование

### SQLite
```bash
cp agent-runtime/data/agent_runtime.db backup/
cp auth-service/data/auth.db backup/
```

### PostgreSQL
```bash
docker-compose exec postgres pg_dump -U codelab agent_runtime > backup/agent_runtime.sql
docker-compose exec postgres pg_dump -U codelab auth_db > backup/auth_db.sql
```

## Дополнительные ресурсы

- [DATABASE_CONFIGURATION.md](./DATABASE_CONFIGURATION.md) - полная документация
- [POSTGRES_QUICKSTART.md](./POSTGRES_QUICKSTART.md) - быстрый старт
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

## Поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs postgres agent-runtime auth-service`
2. Проверьте переменные окружения в `.env`
3. Убедитесь что PostgreSQL контейнер запущен: `docker-compose ps postgres`
4. См. раздел Troubleshooting в [DATABASE_CONFIGURATION.md](./DATABASE_CONFIGURATION.md)
