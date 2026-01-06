# Переключение на PostgreSQL - Пошаговая инструкция

## Текущая ситуация

Вы уже добавили PostgreSQL URL в `.env` файл, но сервисы все еще используют SQLite. Это происходит потому, что:

1. Docker образы не содержат драйверы PostgreSQL (нужна пересборка)
2. Сервисы не были перезапущены после изменения `.env`

## Шаги для переключения

### Шаг 1: Остановите все сервисы

```bash
cd codelab-ai-service
docker-compose down
```

### Шаг 2: Пересоберите образы с новыми зависимостями

Это необходимо для установки `psycopg2-binary` и `asyncpg`:

```bash
docker-compose build agent-runtime auth-service
```

Это займет несколько минут.

### Шаг 3: Удалите старый volume PostgreSQL (если нужно)

Если PostgreSQL уже запускался, но базы данных не были созданы правильно:

```bash
docker volume rm codelab-ai-service_postgres-data
```

**Внимание:** Это удалит все данные в PostgreSQL!

### Шаг 4: Запустите сервисы

```bash
docker-compose up -d
```

### Шаг 5: Проверьте логи

```bash
# Проверьте что PostgreSQL запустился
docker-compose logs postgres | tail -20

# Проверьте что auth-service подключился к PostgreSQL
docker-compose logs auth-service | grep -i "database\|postgres\|asyncpg"

# Проверьте что agent-runtime подключился к PostgreSQL  
docker-compose logs agent-runtime | grep -i "database\|postgres"
```

### Шаг 6: Создайте базы данных вручную (если скрипт не сработал)

Если базы данных не были созданы автоматически:

```bash
# Подключитесь к PostgreSQL
docker-compose exec postgres psql -U codelab -d codelab

# В psql выполните:
CREATE DATABASE agent_runtime;
CREATE DATABASE auth_db;
\l
\q
```

### Шаг 7: Перезапустите сервисы

```bash
docker-compose restart agent-runtime auth-service
```

### Шаг 8: Проверьте что все работает

```bash
# Проверьте healthcheck
curl http://localhost/api/auth/health
curl http://localhost/api/gateway/health

# Проверьте логи на ошибки
docker-compose logs -f agent-runtime auth-service
```

## Проверка успешного подключения

### auth-service должен показывать:

```
INFO - Database initialized
```

И в логах НЕ должно быть `aiosqlite`, должно быть `asyncpg`.

### agent-runtime должен показывать:

```
Database initialized with URL: postgresql://codelab:***@postgres:5432/agent_runtime
```

## Если что-то пошло не так

### Ошибка: "database does not exist"

Создайте базы данных вручную (см. Шаг 6).

### Ошибка: "could not connect to server"

Проверьте что PostgreSQL запущен:
```bash
docker-compose ps postgres
docker-compose logs postgres
```

### Ошибка: "ModuleNotFoundError: No module named 'asyncpg'"

Пересоберите образы (см. Шаг 2).

### Сервисы все еще используют SQLite

1. Проверьте `.env` файл - URL должны быть раскомментированы
2. Пересоберите образы
3. Полностью остановите и запустите заново:
```bash
docker-compose down
docker-compose up -d --build
```

## Возврат к SQLite

Если нужно вернуться к SQLite:

1. Отредактируйте `.env`:
```bash
# Закомментируйте PostgreSQL:
# AGENT_RUNTIME__DB_URL=postgresql://codelab:codelab_password@postgres:5432/agent_runtime
# AUTH_SERVICE__DB_URL=postgresql+asyncpg://codelab:codelab_password@postgres:5432/auth_db

# Раскомментируйте SQLite:
AGENT_RUNTIME__DB_URL=sqlite:///data/agent_runtime.db
AUTH_SERVICE__DB_URL=sqlite:///data/auth.db
```

2. Перезапустите:
```bash
docker-compose restart agent-runtime auth-service
```

## Полезные команды

```bash
# Посмотреть все переменные окружения сервиса
docker-compose exec auth-service env | grep DB_URL
docker-compose exec agent-runtime env | grep DB_URL

# Подключиться к PostgreSQL
docker-compose exec postgres psql -U codelab -d agent_runtime
docker-compose exec postgres psql -U codelab -d auth_db

# Посмотреть таблицы
docker-compose exec postgres psql -U codelab -d agent_runtime -c "\dt"
docker-compose exec postgres psql -U codelab -d auth_db -c "\dt"

# Полная пересборка и перезапуск
docker-compose down
docker-compose build --no-cache agent-runtime auth-service
docker-compose up -d
```
