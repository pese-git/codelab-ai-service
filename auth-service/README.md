# Auth Service - OAuth2 Authorization Server для CodeLab

## Обзор

Auth Service — это микросервис аутентификации и авторизации для платформы CodeLab, реализующий OAuth2 Authorization Server с поддержкой Password Grant и Refresh Token Grant.

## Основные возможности

- ✅ OAuth2 Password Grant для аутентификации пользователей
- ✅ Refresh Token Grant с автоматической ротацией
- ✅ JWT токены с RS256 подписью
- ✅ JWKS endpoint для валидации токенов
- ✅ Rate limiting и brute-force защита
- ✅ Аудит логирование всех операций
- ✅ Горизонтальное масштабирование (stateless)

## Технологический стек

- **Python 3.12**
- **FastAPI** — веб-фреймворк
- **SQLite** — база данных (с возможностью миграции на PostgreSQL)
- **Redis** — кэширование и rate limiting
- **SQLAlchemy** — ORM
- **Alembic** — миграции БД
- **bcrypt** — хэширование паролей
- **python-jose** — JWT токены

## Быстрый старт

### Требования

- Docker и Docker Compose
- Python 3.12+ (для локальной разработки)

### Запуск с Docker Compose

```bash
# Из корневой директории проекта
cd codelab-ai-service

# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps

# Проверить логи Auth Service
docker-compose logs -f auth-service
```

Auth Service будет доступен на `http://localhost:8003`

### Первый запуск

1. **Применить миграции:**
```bash
docker-compose exec auth-service alembic upgrade head
```

2. **Создать тестового пользователя:**
```bash
docker-compose exec auth-service python -m app.scripts.create_user \
  --username testuser \
  --email test@example.com \
  --password password123
```

3. **Проверить health check:**
```bash
curl http://localhost:8003/health
```

## API Endpoints

### OAuth2 Token Endpoint

**POST /oauth/token**

Получение access и refresh токенов.

#### Password Grant

```bash
curl -X POST http://localhost:8003/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "username=test@example.com" \
  -d "password=password123" \
  -d "client_id=codelab-flutter-app" \
  -d "scope=api:read api:write"
```

**Ответ:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900,
  "scope": "api:read api:write"
}
```

#### Refresh Token Grant

```bash
curl -X POST http://localhost:8003/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d "client_id=codelab-flutter-app"
```

### JWKS Endpoint

**GET /.well-known/jwks.json**

Публичные ключи для валидации JWT токенов.

```bash
curl http://localhost:8003/.well-known/jwks.json
```

**Ответ:**
```json
{
  "keys": [
    {
      "kty": "RSA",
      "use": "sig",
      "kid": "2024-01-key-1",
      "alg": "RS256",
      "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx...",
      "e": "AQAB"
    }
  ]
}
```

### Health Check

**GET /health**

```bash
curl http://localhost:8003/health
```

**Ответ:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "database": "connected",
  "redis": "connected"
}
```

## Документация

### Основные документы

- [**Техническое задание**](docs/TECHNICAL_SPECIFICATION.md) — полное ТЗ с требованиями
- [**План реализации**](docs/IMPLEMENTATION_PLAN.md) — пошаговый план разработки
- [**Интеграционные точки**](docs/INTEGRATION_POINTS.md) — интеграция с другими сервисами

### Дополнительные документы (будут созданы)

- API документация — OpenAPI/Swagger
- Руководство по развертыванию
- Руководство по интеграции для клиентов
- Troubleshooting guide

## Структура проекта

```
auth-service/
├── app/
│   ├── api/              # API endpoints
│   │   └── v1/
│   │       ├── oauth.py  # OAuth2 endpoints
│   │       └── jwks.py   # JWKS endpoint
│   ├── core/             # Конфигурация и безопасность
│   │   ├── config.py
│   │   └── security.py
│   ├── models/           # SQLAlchemy модели
│   │   ├── user.py
│   │   ├── oauth_client.py
│   │   └── refresh_token.py
│   ├── schemas/          # Pydantic схемы
│   ├── services/         # Бизнес-логика
│   │   ├── auth_service.py
│   │   ├── token_service.py
│   │   └── user_service.py
│   └── utils/            # Утилиты
├── alembic/              # Миграции БД
├── tests/                # Тесты
├── docs/                 # Документация
├── Dockerfile
├── pyproject.toml
└── README.md
```

## Разработка

### Локальная разработка

```bash
# Установить зависимости
uv sync

# Запустить сервер
uv run uvicorn app.main:app --reload --port 8003

# Запустить тесты
uv run pytest

# Проверить coverage
uv run pytest --cov=app --cov-report=html

# Линтинг
uv run ruff check app/
```

### Создание миграции

```bash
# Создать новую миграцию
alembic revision --autogenerate -m "Description"

# Применить миграции
alembic upgrade head

# Откатить миграцию
alembic downgrade -1
```

### Генерация RSA ключей

```bash
# Сгенерировать новую пару ключей
python -m app.scripts.generate_keys --output-dir ./keys
```

## Конфигурация

### Переменные окружения

```bash
# Основные настройки
ENVIRONMENT=development
PORT=8003

# База данных
AUTH_SERVICE__DB_URL=sqlite:///data/auth.db

# Redis
AUTH_SERVICE__REDIS_URL=redis://redis:6379/1

# JWT настройки
AUTH_SERVICE__JWT_ISSUER=https://auth.codelab.local
AUTH_SERVICE__JWT_AUDIENCE=codelab-api
AUTH_SERVICE__ACCESS_TOKEN_LIFETIME=900        # 15 минут
AUTH_SERVICE__REFRESH_TOKEN_LIFETIME=2592000   # 30 дней

# RSA ключи
AUTH_SERVICE__PRIVATE_KEY_PATH=/app/keys/private_key.pem
AUTH_SERVICE__PUBLIC_KEY_PATH=/app/keys/public_key.pem

# Логирование
AUTH_SERVICE__LOG_LEVEL=DEBUG
```

## Безопасность

### Требования к паролям

- Минимум 8 символов
- Хотя бы одна заглавная буква
- Хотя бы одна цифра
- Хотя бы один специальный символ

### Rate Limiting

- **IP-based:** 5 запросов в минуту на `/oauth/token`
- **Username-based:** 10 запросов в час на `/oauth/token`

### Brute-force защита

- После 5 неудачных попыток — временная блокировка на 15 минут
- Логирование всех неудачных попыток

### JWT токены

- **Access Token:** 15 минут, RS256, не хранится в БД
- **Refresh Token:** 30 дней, RS256, одноразовый (rotation)

## Мониторинг

### Prometheus метрики

Доступны на `/metrics`:

- `auth_token_requests_total` — количество запросов токенов
- `auth_token_request_duration_seconds` — время обработки
- `auth_failed_login_attempts_total` — неудачные попытки входа
- `auth_refresh_token_rotations_total` — ротации refresh токенов

### Health Check

```bash
# Проверка здоровья сервиса
curl http://localhost:8003/health

# Проверка готовности (readiness probe)
curl http://localhost:8003/ready
```

## Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# С coverage
pytest --cov=app --cov-report=html

# Только unit тесты
pytest tests/unit/

# Только integration тесты
pytest tests/integration/

# Security тесты
pytest tests/security/
```

### Тестовые данные

Предустановленные OAuth клиенты:

- **codelab-flutter-app** — Flutter приложение (public client)
- **codelab-internal** — Внутренние сервисы (confidential client)

## Производительность

### Требования

- Время ответа `/oauth/token` < 200ms (p95)
- Throughput: 100 RPS на инстанс
- Latency JWKS endpoint < 50ms

### Оптимизация

- JWKS кэшируется в Redis (TTL 1 час)
- OAuth clients кэшируются (TTL 5 минут)
- SQLite в WAL режиме
- Connection pooling

## Масштабирование

Auth Service поддерживает горизонтальное масштабирование:

```yaml
# docker-compose.yml
services:
  auth-service:
    deploy:
      replicas: 3
```

**Важно:**
- Access токены stateless (не требуют синхронизации)
- Refresh токены хранятся в общей БД
- Redis используется для rate limiting и кэширования

## Миграция на PostgreSQL

Для production окружения рекомендуется PostgreSQL:

```bash
# 1. Обновить connection string
AUTH_SERVICE__DB_URL=postgresql://user:pass@postgres:5432/auth_db

# 2. Обновить типы данных в моделях
# String(36) → UUID

# 3. Применить миграции
alembic upgrade head
```

## Troubleshooting

### Проблема: Auth Service не запускается

```bash
# Проверить логи
docker-compose logs auth-service

# Проверить БД
docker-compose exec auth-service ls -la /app/data/

# Проверить Redis
docker-compose exec redis redis-cli ping
```

### Проблема: JWT токены не валидируются

```bash
# Проверить JWKS endpoint
curl http://localhost:8003/.well-known/jwks.json

# Проверить RSA ключи
docker-compose exec auth-service ls -la /app/keys/
```

### Проблема: Rate limiting не работает

```bash
# Проверить Redis
docker-compose exec redis redis-cli
> KEYS rate_limit:*
```

## Roadmap

### MVP (текущая версия)
- ✅ OAuth2 Password Grant
- ✅ Refresh Token Grant
- ✅ JWT токены (RS256)
- ✅ JWKS endpoint
- ✅ Rate limiting
- ✅ Аудит логирование

### Post-MVP
- [ ] Authorization Code Flow + PKCE
- [ ] Client Credentials Grant
- [ ] RBAC (Role-Based Access Control)
- [ ] SSO с внешними провайдерами
- [ ] Admin UI
- [ ] Multi-factor authentication (MFA)

## Лицензия

MIT License

## Контакты

**Разработчик:** Sergey Penkovsky  
**Email:** sergey.penkovsky@gmail.com  
**Проект:** CodeLab  
**Версия:** 0.1.0 (MVP)
