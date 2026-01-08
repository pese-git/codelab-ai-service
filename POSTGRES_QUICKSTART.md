# PostgreSQL Quick Start Guide

Быстрое руководство по переключению с SQLite на PostgreSQL.

## Для разработки (SQLite) - по умолчанию

Ничего делать не нужно! Проект уже настроен на использование SQLite:

```bash
docker-compose up -d
```

## Для production (PostgreSQL)

### Шаг 1: Пересоберите Docker образы

Необходимо пересобрать образы для установки драйверов PostgreSQL (`psycopg2-binary` и `asyncpg`):

```bash
docker-compose build agent-runtime auth-service
```

### Шаг 2: Отредактируйте `.env` файл

Раскомментируйте строки с PostgreSQL и закомментируйте SQLite:

```bash
# Agent Runtime - закомментируйте SQLite:
# AGENT_RUNTIME__DB_URL=sqlite:///data/agent_runtime.db

# Agent Runtime - раскомментируйте PostgreSQL:
AGENT_RUNTIME__DB_URL=postgresql://codelab:codelab_password@postgres:5432/agent_runtime

# Auth Service - закомментируйте SQLite:
# AUTH_SERVICE__DB_URL=sqlite:///data/auth.db

# Auth Service - раскомментируйте PostgreSQL:
AUTH_SERVICE__DB_URL=postgresql+asyncpg://codelab:codelab_password@postgres:5432/auth_db
```

### Шаг 3: Запустите сервисы

```bash
# Запустить все сервисы включая PostgreSQL
docker-compose up -d

# Проверить статус
docker-compose ps

# Проверить логи
docker-compose logs -f agent-runtime auth-service postgres
```

### Шаг 4: Проверка

```bash
# Проверить что PostgreSQL работает
docker-compose exec postgres psql -U codelab -d agent_runtime -c "\dt"
docker-compose exec postgres psql -U codelab -d auth_db -c "\dt"
```

## Переключение обратно на SQLite

Отредактируйте `.env`:

```bash
# Раскомментируйте SQLite:
AGENT_RUNTIME__DB_URL=sqlite:///data/agent_runtime.db
AUTH_SERVICE__DB_URL=sqlite:///data/auth.db

# Закомментируйте PostgreSQL:
# AGENT_RUNTIME__DB_URL=postgresql://codelab:codelab_password@postgres:5432/agent_runtime
# AUTH_SERVICE__DB_URL=postgresql+asyncpg://codelab:codelab_password@postgres:5432/auth_db
```

Перезапустите сервисы:

```bash
docker-compose restart agent-runtime auth-service
```

## Смешанная конфигурация

Можно использовать разные БД для разных сервисов:

```bash
# agent-runtime на SQLite
AGENT_RUNTIME__DB_URL=sqlite:///data/agent_runtime.db

# auth-service на PostgreSQL
AUTH_SERVICE__DB_URL=postgresql+asyncpg://codelab:codelab_password@postgres:5432/auth_db
```

## Важные замечания

1. **auth-service** требует драйвер `asyncpg`: `postgresql+asyncpg://...`
2. **agent-runtime** использует синхронный драйвер: `postgresql://...`
3. Базы данных создаются автоматически при первом запуске PostgreSQL
4. Данные PostgreSQL хранятся в Docker volume `postgres-data`

## Полная документация

См. [DATABASE_CONFIGURATION.md](./DATABASE_CONFIGURATION.md) для подробной информации.
