# Конфигурация базы данных

Проект `codelab-ai-service` поддерживает работу как с **SQLite**, так и с **PostgreSQL**.

## Обзор

- **SQLite** - рекомендуется для разработки и тестирования (по умолчанию)
- **PostgreSQL** - рекомендуется для production окружения

Оба сервиса (`agent-runtime` и `auth-service`) могут работать с обеими СУБД независимо друг от друга.

## Конфигурация для разработки (SQLite)

### По умолчанию

По умолчанию оба сервиса используют SQLite. Никаких дополнительных настроек не требуется.

**agent-runtime:**
```bash
AGENT_RUNTIME__DB_URL=sqlite:///data/agent_runtime.db
```

**auth-service:**
```bash
AUTH_SERVICE__DB_URL=sqlite:///data/auth.db
```

### Преимущества SQLite для разработки

- ✅ Не требует установки отдельного сервера БД
- ✅ Простая настройка
- ✅ Быстрый старт
- ✅ Файловое хранилище (легко удалить/пересоздать)
- ✅ Подходит для тестирования

## Конфигурация для production (PostgreSQL)

### 1. Запуск PostgreSQL через Docker Compose

PostgreSQL сервис уже настроен в `docker-compose.yml`. Для его запуска:

```bash
# Запустить все сервисы включая PostgreSQL
docker-compose up -d

# Или только PostgreSQL
docker-compose up -d postgres
```

### 2. Настройка переменных окружения

Отредактируйте файл `.env` в корне проекта:

```bash
# PostgreSQL настройки (для контейнера postgres)
POSTGRES_USER=codelab
POSTGRES_PASSWORD=codelab_password
POSTGRES_DB=codelab
```

### 3. Настройка подключения для agent-runtime

В файле `.env` раскомментируйте и настройте:

```bash
# Закомментируйте SQLite:
# AGENT_RUNTIME__DB_URL=sqlite:///data/agent_runtime.db

# Раскомментируйте PostgreSQL:
AGENT_RUNTIME__DB_URL=postgresql://codelab:codelab_password@postgres:5432/agent_runtime
```

Или в `docker-compose.yml` для сервиса `agent-runtime`:

```yaml
environment:
  - AGENT_RUNTIME__DB_URL=postgresql://codelab:codelab_password@postgres:5432/agent_runtime
```

### 4. Настройка подключения для auth-service

В файле `.env` раскомментируйте и настройте:

```bash
# Закомментируйте SQLite:
# AUTH_SERVICE__DB_URL=sqlite:///data/auth.db

# Раскомментируйте PostgreSQL (с asyncpg драйвером):
AUTH_SERVICE__DB_URL=postgresql+asyncpg://codelab:codelab_password@postgres:5432/auth_db
```

Или в `docker-compose.yml` для сервиса `auth-service`:

```yaml
environment:
  - AUTH_SERVICE__DB_URL=postgresql+asyncpg://codelab:codelab_password@postgres:5432/auth_db
```

**Важно:** `auth-service` использует асинхронный драйвер `asyncpg`, поэтому URL должен содержать `postgresql+asyncpg://`

### 5. Инициализация баз данных

При первом запуске PostgreSQL автоматически создаст две базы данных:
- `agent_runtime` - для agent-runtime сервиса
- `auth_db` - для auth-service

Это происходит благодаря скрипту [`scripts/init-postgres.sh`](./scripts/init-postgres.sh).

### 6. Перезапуск сервисов

После изменения конфигурации перезапустите сервисы:

```bash
docker-compose restart agent-runtime auth-service
```

### Преимущества PostgreSQL для production

- ✅ Высокая производительность
- ✅ ACID транзакции
- ✅ Поддержка репликации
- ✅ Расширенные возможности индексирования
- ✅ Лучшая поддержка конкурентного доступа
- ✅ JSON/JSONB типы данных

## Форматы URL подключения

### SQLite

```bash
sqlite:///path/to/database.db
sqlite:///data/agent_runtime.db  # Относительный путь
sqlite:////absolute/path/to/db.db  # Абсолютный путь
```

### PostgreSQL

**Синхронный драйвер (для agent-runtime):**
```bash
postgresql://username:password@host:port/database
postgresql://codelab:codelab_password@localhost:5432/agent_runtime
postgresql://codelab:codelab_password@postgres:5432/agent_runtime  # В Docker
```

**Асинхронный драйвер (для auth-service):**
```bash
postgresql+asyncpg://username:password@host:port/database
postgresql+asyncpg://codelab:codelab_password@localhost:5432/auth_db
postgresql+asyncpg://codelab:codelab_password@postgres:5432/auth_db  # В Docker
```

## Миграция данных

### Из SQLite в PostgreSQL

1. Экспортируйте данные из SQLite (если необходимо сохранить существующие данные)
2. Настройте PostgreSQL подключение
3. Перезапустите сервисы - таблицы будут созданы автоматически
4. Импортируйте данные (если необходимо)

### Из PostgreSQL в SQLite

1. Экспортируйте данные из PostgreSQL (если необходимо)
2. Измените `DB_URL` обратно на SQLite
3. Перезапустите сервисы
4. Импортируйте данные (если необходимо)

## Смешанная конфигурация

Вы можете использовать разные СУБД для разных сервисов:

```bash
# agent-runtime использует SQLite
AGENT_RUNTIME__DB_URL=sqlite:///data/agent_runtime.db

# auth-service использует PostgreSQL
AUTH_SERVICE__DB_URL=postgresql+asyncpg://codelab:codelab_password@postgres:5432/auth_db
```

## Подключение к PostgreSQL извне Docker

Если нужно подключиться к PostgreSQL из хост-машины (например, через pgAdmin или psql):

1. Раскомментируйте порты в `docker-compose.yml`:

```yaml
postgres:
  ports:
    - "5432:5432"  # Раскомментируйте эту строку
```

2. Перезапустите PostgreSQL:

```bash
docker-compose restart postgres
```

3. Подключитесь:

```bash
psql -h localhost -p 5432 -U codelab -d agent_runtime
# Пароль: codelab_password
```

## Требования к зависимостям

### agent-runtime

**SQLite** (по умолчанию):
- `sqlalchemy>=2.0.0` - ✅ установлен

**PostgreSQL**:
- `psycopg2-binary>=2.9.9` - ✅ установлен

### auth-service

**SQLite** (по умолчанию):
- `sqlalchemy==2.0.23` - ✅ установлен
- `aiosqlite==0.19.0` - ✅ установлен

**PostgreSQL**:
- `asyncpg>=0.29.0` - ✅ установлен

Все необходимые зависимости уже добавлены в [`pyproject.toml`](./agent-runtime/pyproject.toml) файлы обоих сервисов.

## Проверка подключения

### agent-runtime

```bash
# Проверьте логи при старте
docker-compose logs agent-runtime | grep -i database

# Должно быть:
# Database initialized with URL: sqlite:///data/agent_runtime.db
# или
# Database initialized with URL: postgresql://codelab:***@postgres:5432/agent_runtime
```

### auth-service

```bash
# Проверьте логи при старте
docker-compose logs auth-service | grep -i database
```

## Резервное копирование

### SQLite

```bash
# Копирование файла базы данных
cp agent-runtime/data/agent_runtime.db agent_runtime.db.backup
cp auth-service/data/auth.db auth.db.backup
```

### PostgreSQL

```bash
# Через docker-compose
docker-compose exec postgres pg_dump -U codelab agent_runtime > agent_runtime_backup.sql
docker-compose exec postgres pg_dump -U codelab auth_db > auth_db_backup.sql

# Восстановление
docker-compose exec -T postgres psql -U codelab agent_runtime < agent_runtime_backup.sql
docker-compose exec -T postgres psql -U codelab auth_db < auth_db_backup.sql
```

## Troubleshooting

### Ошибка: "could not connect to server"

Убедитесь, что PostgreSQL контейнер запущен:
```bash
docker-compose ps postgres
docker-compose logs postgres
```

### Ошибка: "database does not exist"

Пересоздайте PostgreSQL контейнер:
```bash
docker-compose down postgres
docker-compose up -d postgres
```

### Ошибка: "password authentication failed"

Проверьте переменные окружения `POSTGRES_USER` и `POSTGRES_PASSWORD` в `.env` файле.

### Медленная работа SQLite в Docker

Это нормально для SQLite в Docker volumes. Для production используйте PostgreSQL.

## Рекомендации

1. **Разработка**: используйте SQLite для быстрого старта
2. **CI/CD**: используйте SQLite для тестов
3. **Staging**: используйте PostgreSQL для проверки production конфигурации
4. **Production**: используйте PostgreSQL для надежности и производительности

## Дополнительная информация

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
