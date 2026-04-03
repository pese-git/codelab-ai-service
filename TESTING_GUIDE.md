# Руководство по запуску и тестированию Event-Driven User Sync

## 1. Подготовка окружения

### 1.1 Клонирование и переход в директорию

```bash
cd /Users/sergey/Projects/OpenIdeaLab/codelab-ai-service
```

### 1.2 Обновление .env файлов

**Auth Service** (`codelab-auth-service/.env`):

```bash
cp codelab-auth-service/.env.example codelab-auth-service/.env
```

Убедитесь, что в файле установлены следующие значения:

```env
# Обязательные для event publisher и token blacklist
USE_EVENT_PUBLISHING=true
EVENTS_STREAM_KEY=user_events
EVENTS_STREAM_MAXLEN=100000
EVENTS_VERSION=1.0

USE_TOKEN_BLACKLIST=true
TOKEN_BLACKLIST_MIN_TTL=3600

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
```

**Core Service** (`codelab-core-service/.env`):

```bash
cp codelab-core-service/.env.example codelab-core-service/.env
```

Убедитесь, что в файле установлены следующие значения:

```env
# Обязательные для event consumer
USE_EVENT_CONSUMER=true
EVENTS_STREAM_KEY=user_events
EVENTS_CONSUMER_GROUP=core_service_consumer_group
EVENTS_CONSUMER_NAME=core_service_consumer_1
EVENTS_BATCH_SIZE=10
EVENTS_CONSUMER_TIMEOUT=1000
EVENTS_MAX_RETRIES=3
EVENTS_DLQ_STREAM_KEY=user_events_dlq

USE_TOKEN_BLACKLIST=true
TOKEN_BLACKLIST_MIN_TTL=3600

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
```

---

## 2. Запуск Docker Compose

### 2.1 Запуск всех сервисов

```bash
docker-compose up -d
```

Это запустит:
- **Redis** (6379) - для Streams и Token Blacklist
- **PostgreSQL** (5432) - для хранения данных
- **Auth Service** (8001) - управление пользователями
- **Core Service** (8000) - обработка событий и изоляция пользователей

### 2.2 Проверка статуса сервисов

```bash
docker-compose ps

# Должны увидеть:
# NAME                  STATUS      PORTS
# redis                 Up          6379
# postgres              Up          5432
# codelab-auth-service  Up          8001
# codelab-core-service  Up          8000
```

### 2.3 Проверка логов

```bash
# Все логи
docker-compose logs -f

# Только Auth Service
docker-compose logs -f codelab-auth-service

# Только Core Service
docker-compose logs -f codelab-core-service

# Только Redis
docker-compose logs -f redis
```

---

## 3. Тестирование функционала

### 3.1 Проверка здоровья сервисов

```bash
# Auth Service
curl -s http://localhost:8001/health | jq .

# Core Service
curl -s http://localhost:8000/health | jq .

# Должны вернуть:
# {
#   "status": "healthy",
#   "timestamp": "2026-03-31T20:56:11.000Z"
# }
```

### 3.2 Тестирование User Creation и Event Publishing

#### Шаг 1: Создать пользователя в Auth Service

```bash
curl -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePass123!"
  }'

# Ответ:
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "username": "testuser",
#   "email": "test@example.com"
# }
```

#### Шаг 2: Проверить событие в Redis Streams

```bash
redis-cli -h localhost -p 6379 << EOF
XREVRANGE user_events + COUNT 1
EOF

# Должен вернуть последнее событие user.created
```

#### Шаг 3: Проверить синхронизацию в Core Service

```bash
# Подождите 1-2 секунды, затем проверьте
psql -h localhost -U postgres -d codelab -c "
SELECT id, username, email, synced_from_auth_at FROM users 
WHERE username = 'testuser';
"

# Должен вернуть:
# id                                   | username  | email           | synced_from_auth_at
# 550e8400-e29b-41d4-a716-446655440000 | testuser  | test@example.com| 2026-03-31 20:56:11
```

### 3.3 Тестирование Token Blacklist

#### Шаг 1: Получить токен

```bash
curl -X POST http://localhost:8001/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "SecurePass123!"
  }'

# Ответ (сохранить токен):
# {
#   "access_token": "eyJhbGc...",
#   "token_type": "bearer"
# }

export TOKEN="eyJhbGc..."
```

#### Шаг 2: Использовать токен в запросе к Core Service

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/projects

# Должен вернуть успешный результат
```

#### Шаг 3: Отозвать токен (удалить пользователя)

```bash
curl -X DELETE http://localhost:8001/admin/users/550e8400-e29b-41d4-a716-446655440000

# Ответ:
# {
#   "user_id": "550e8400-e29b-41d4-a716-446655440000",
#   "tokens_revoked": 1,
#   "event_id": "1-0"
# }
```

#### Шаг 4: Попытаться использовать отозванный токен

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/projects

# Должен вернуть 401 Unauthorized
# {
#   "detail": "Token is revoked"
# }
```

### 3.4 Тестирование Event Consumer

#### Проверить обработанные события

```bash
# Информация о группе потребителей
redis-cli -h localhost -p 6379 << EOF
XINFO GROUPS user_events
EOF

# Должен показать:
# - Количество обработанных сообщений (delivered-messages)
# - Задержку (lag)
# - Last entry ID
```

#### Проверить DLQ (Dead Letter Queue)

```bash
# Если есть ошибки, сообщения будут в DLQ
redis-cli -h localhost -p 6379 XLEN user_events_dlq

# Должен вернуть 0 (нет ошибок)
```

### 3.5 Тестирование Cascade Deletion

#### Создать структуру данных

```bash
# 1. Создать пользователя (уже сделано выше)

# 2. Создать проект (примерный endpoint)
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Project",
    "workspace_path": "/test"
  }'
```

#### Удалить пользователя и проверить cascade

```bash
# Удалить пользователя
curl -X DELETE http://localhost:8001/admin/users/550e8400-e29b-41d4-a716-446655440000

# Проверить, что все данные пользователя удалены
psql -h localhost -U postgres -d codelab << EOF
SELECT COUNT(*) FROM users WHERE id = '550e8400-e29b-41d4-a716-446655440000';
SELECT COUNT(*) FROM user_projects WHERE user_id = '550e8400-e29b-41d4-a716-446655440000';
SELECT COUNT(*) FROM user_agents WHERE user_id = '550e8400-e29b-41d4-a716-446655440000';
EOF

# Все должны вернуть 0
```

---

## 4. Запуск Unit Tests

### 4.1 Auth Service Tests

```bash
cd codelab-auth-service

# Запустить все тесты
pytest tests/ -v

# Запустить конкретные тесты
pytest tests/test_token_blacklist_service.py -v
pytest tests/test_event_publisher.py -v
pytest tests/test_e2e_user_deletion_flow.py -v
```

### 4.2 Core Service Tests

```bash
cd codelab-core-service

# Запустить все тесты
pytest tests/ -v

# Запустить конкретные тесты
pytest tests/test_event_consumer.py -v
pytest tests/test_user_event_handlers.py -v
pytest tests/test_e2e_event_consumer_flow.py -v
```

---

## 5. Мониторинг в реальном времени

### 5.1 Наблюдение за Redis Streams

```bash
# В отдельном терминале
redis-cli -h localhost -p 6379

# Монитор всех команд
> MONITOR

# Или смотреть события
> XREAD COUNT 10 STREAMS user_events 0
```

### 5.2 Наблюдение за базой данных

```bash
# В отдельном терминале
psql -h localhost -U postgres -d codelab

# Периодические обновления
\watch [5]

-- Количество пользователей
SELECT COUNT(*) as total_users, 
       COUNT(CASE WHEN synced_from_auth_at IS NOT NULL THEN 1 END) as synced_users
FROM users;
```

### 5.3 Логи сервисов

```bash
# В отдельном терминале для каждого сервиса
docker-compose logs -f codelab-auth-service
docker-compose logs -f codelab-core-service
```

---

## 6. Scenario Testing

### Scenario 1: Полный цикл жизни пользователя

```bash
#!/bin/bash

# 1. Создать пользователя
USER_RESPONSE=$(curl -s -X POST http://localhost:8001/api/v1/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "lifecycle_user",
    "email": "lifecycle@example.com",
    "password": "SecurePass123!"
  }')

USER_ID=$(echo $USER_RESPONSE | jq -r '.id')
echo "✓ Created user: $USER_ID"

# 2. Проверить синхронизацию
sleep 2
SYNC_COUNT=$(psql -h localhost -U postgres -d codelab -t -c \
  "SELECT COUNT(*) FROM users WHERE id = '$USER_ID' AND synced_from_auth_at IS NOT NULL;")

if [ "$SYNC_COUNT" -eq 1 ]; then
  echo "✓ User synced to Core Service"
else
  echo "✗ User NOT synced"
fi

# 3. Получить токен
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8001/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "lifecycle_user",
    "password": "SecurePass123!"
  }')

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
echo "✓ Got token"

# 4. Использовать токен
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/projects > /dev/null

if [ $? -eq 0 ]; then
  echo "✓ Token valid for Core Service"
else
  echo "✗ Token invalid"
fi

# 5. Удалить пользователя
curl -s -X DELETE http://localhost:8001/admin/users/$USER_ID > /dev/null
echo "✓ User deleted"

# 6. Проверить, что токен отозван
sleep 1
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/projects 2>&1 | grep -q "401"

if [ $? -eq 0 ]; then
  echo "✓ Token revoked"
else
  echo "✗ Token NOT revoked"
fi

echo ""
echo "✅ Scenario completed successfully!"
```

### Scenario 2: Event Publisher & Consumer

```bash
#!/bin/bash

echo "Testing Event Publisher & Consumer..."

# 1. Проверить начальный размер потока
INITIAL_SIZE=$(redis-cli -h localhost -p 6379 XLEN user_events)
echo "Initial stream size: $INITIAL_SIZE"

# 2. Создать несколько пользователей
for i in {1..5}; do
  curl -s -X POST http://localhost:8001/api/v1/register \
    -H "Content-Type: application/json" \
    -d "{
      \"username\": \"user$i\",
      \"email\": \"user$i@example.com\",
      \"password\": \"SecurePass123!\"
    }" > /dev/null
  echo "✓ Created user$i"
done

# 3. Проверить, что события опубликованы
sleep 1
FINAL_SIZE=$(redis-cli -h localhost -p 6379 XLEN user_events)
EVENTS_COUNT=$((FINAL_SIZE - INITIAL_SIZE))
echo "✓ Published $EVENTS_COUNT events"

# 4. Проверить, что события обработаны
sleep 2
SYNCED_COUNT=$(psql -h localhost -U postgres -d codelab -t -c \
  "SELECT COUNT(*) FROM users WHERE username LIKE 'user%' AND synced_from_auth_at IS NOT NULL;")
echo "✓ Synced $SYNCED_COUNT users"

echo "✅ Event test completed!"
```

---

## 7. Debugging

### 7.1 Проверка Redis health

```bash
redis-cli -h localhost -p 6379 PING

# Должен вернуть: PONG
```

### 7.2 Проверка Database health

```bash
psql -h localhost -U postgres -d codelab -c "SELECT 1;"

# Должен вернуть: 1
```

### 7.3 Просмотр логов с фильтром

```bash
# Ошибки
docker-compose logs | grep -i error

# Events
docker-compose logs | grep -i event

# Token blacklist
docker-compose logs | grep -i blacklist

# Consumer
docker-compose logs | grep -i consumer
```

### 7.4 Остановка и очистка

```bash
# Остановить сервисы
docker-compose down

# Остановить и удалить все данные
docker-compose down -v

# Удалить неиспользуемые образы
docker system prune -a
```

---

## 8. Чек-лист тестирования

- [ ] Docker Compose сервисы запущены
- [ ] Health endpoints доступны
- [ ] User creation работает
- [ ] Events публикуются в Redis Streams
- [ ] Events потребляются и обрабатываются
- [ ] Users синхронизируются в Core Service
- [ ] Token Blacklist отзывает токены
- [ ] Deleted users блокируются в middleware
- [ ] DLQ пуст (нет ошибок обработки)
- [ ] Unit tests проходят
- [ ] E2E tests проходят

---

## 9. Полезные команды

```bash
# Redis CLI
docker-compose exec redis redis-cli

# PostgreSQL
docker-compose exec postgres psql -U postgres -d codelab

# Просмотр событий в потоке
redis-cli XREVRANGE user_events + COUNT 5

# Просмотр информации о consumer group
redis-cli XINFO GROUPS user_events

# Очистить все события (⚠️ осторожно!)
redis-cli FLUSHALL

# Просмотр размера базы данных
redis-cli DBSIZE
```

---

## 10. Troubleshooting

### Проблема: Events не обрабатываются

**Решение:**
```bash
# 1. Проверить consumer логи
docker-compose logs codelab-core-service | grep -i error

# 2. Пересоздать consumer group
redis-cli XGROUP DESTROY user_events core_service_consumer_group
docker-compose restart codelab-core-service
```

### Проблема: Token не отзывается

**Решение:**
```bash
# 1. Проверить Redis доступность
redis-cli PING

# 2. Проверить конфигурацию
docker-compose exec codelab-auth-service env | grep USE_TOKEN_BLACKLIST
```

### Проблема: User не синхронизируется

**Решение:**
```bash
# 1. Проверить логи consumer
docker-compose logs codelab-core-service | tail -50

# 2. Проверить размер потока
redis-cli XLEN user_events

# 3. Проверить DLQ
redis-cli XLEN user_events_dlq
```
