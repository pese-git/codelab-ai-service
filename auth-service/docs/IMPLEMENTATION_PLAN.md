# План реализации Auth Service

**Версия:** 1.0.0
**Дата:** 20 января 2026
**Статус:** ✅ Реализовано

---

## Обзор

Данный документ описывает пошаговый план реализации Auth Service для платформы CodeLab. План разбит на итерации с четкими задачами и критериями приемки.

**Важно:** В процессе разработки используется SQLite для разработки и PostgreSQL для production.

---

## Итерация 0: Подготовка инфраструктуры ✅ ЗАВЕРШЕНО

### Задачи

#### 0.1 Создание структуры проекта
- [x] Создать директорию `auth-service/`
- [x] Настроить `pyproject.toml` с зависимостями
- [x] Создать `Dockerfile`
- [x] Создать `.env.example`
- [x] Создать базовую структуру директорий

**Файлы:**
- `auth-service/pyproject.toml`
- `auth-service/Dockerfile`
- `auth-service/.env.example`
- `auth-service/.dockerignore`
- `auth-service/.gitignore`

#### 0.2 Настройка Docker Compose
- [x] Добавить Redis сервис
- [x] Добавить auth-service в docker-compose.yml
- [x] Настроить сеть и зависимости
- [x] Настроить volumes для SQLite БД

**Файлы:**
- `docker-compose.yml` (обновить)
- `.env.example` (обновить)

#### 0.3 Базовая конфигурация приложения
- [x] Создать `app/core/config.py` с настройками
- [x] Создать `app/main.py` с FastAPI приложением
- [x] Добавить health check endpoint
- [x] Настроить логирование

**Файлы:**
- `auth-service/app/core/config.py`
- `auth-service/app/main.py`
- `auth-service/app/__init__.py`

#### 0.4 Настройка базы данных
- [x] Настроить SQLAlchemy для SQLite/PostgreSQL
- [x] Настроить Alembic для миграций
- [x] Создать базовую модель `Base`
- [x] Настроить путь к БД в volume

**Файлы:**
- `auth-service/app/models/database.py`
- `auth-service/alembic.ini`
- `auth-service/alembic/env.py`

### Критерии приемки
- ✅ `docker-compose up` запускает все сервисы
- ✅ Auth Service отвечает на `/health`
- ✅ SQLite БД создается в volume
- ✅ Redis доступен
- ✅ Alembic готов к созданию миграций

### Время: 1-2 дня

---

## Итерация 1: Модели данных и миграции ✅ ЗАВЕРШЕНО

### Задачи

#### 1.1 Модель User
- [x] Создать SQLAlchemy модель `User`
- [x] Добавить валидацию полей
- [x] Создать индексы
- [x] Создать Alembic миграцию

**Файлы:**
- `auth-service/app/models/user.py`
- `auth-service/alembic/versions/001_create_users_table.py`

#### 1.2 Модель OAuth Client
- [x] Создать SQLAlchemy модель `OAuthClient`
- [x] Добавить валидацию полей
- [x] Создать индексы
- [x] Создать Alembic миграцию
- [x] Добавить seed данные для тестовых клиентов

**Файлы:**
- `auth-service/app/models/oauth_client.py`
- `auth-service/alembic/versions/002_create_oauth_clients_table.py`
- `auth-service/alembic/versions/003_seed_oauth_clients.py`

#### 1.3 Модель Refresh Token
- [x] Создать SQLAlchemy модель `RefreshToken`
- [x] Добавить валидацию полей
- [x] Создать индексы
- [x] Создать Alembic миграцию

**Файлы:**
- `auth-service/app/models/refresh_token.py`
- `auth-service/alembic/versions/004_create_refresh_tokens_table.py`

#### 1.4 Модель Audit Log
- [x] Создать SQLAlchemy модель `AuditLog`
- [x] Создать индексы
- [x] Создать Alembic миграцию

**Файлы:**
- `auth-service/app/models/audit_log.py`
- `auth-service/alembic/versions/005_create_audit_logs_table.py`

#### 1.5 Pydantic схемы
- [x] Создать схемы для User
- [x] Создать схемы для OAuth Client
- [x] Создать схемы для Token Response
- [x] Создать схемы для OAuth Request

**Файлы:**
- `auth-service/app/schemas/user.py`
- `auth-service/app/schemas/oauth.py`
- `auth-service/app/schemas/token.py`

### Критерии приемки
- ✅ Все миграции применяются без ошибок
- ✅ Таблицы созданы с правильными индексами
- ✅ Seed данные загружены
- ✅ Pydantic схемы валидируют данные корректно

### Время: 2-3 дня

---

## Итерация 2: Криптография и безопасность ✅ ЗАВЕРШЕНО

### Задачи

#### 2.1 Генерация RSA ключей
- [x] Создать утилиту для генерации RSA ключей
- [x] Реализовать хранение ключей (файловая система)
- [x] Реализовать загрузку ключей при старте
- [x] Поддержка множественных ключей (key rotation)

**Файлы:**
- `auth-service/app/core/security.py`
- `auth-service/app/utils/crypto.py`
- `auth-service/scripts/generate_keys.py`

#### 2.2 JWT сервис
- [x] Реализовать создание access token
- [x] Реализовать создание refresh token
- [x] Реализовать валидацию JWT
- [x] Реализовать извлечение payload из JWT
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/services/token_service.py`
- `auth-service/tests/test_token_service.py`

#### 2.3 Password hashing
- [x] Реализовать хэширование паролей (bcrypt)
- [x] Реализовать проверку паролей (constant-time)
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/utils/crypto.py`
- `auth-service/tests/test_crypto.py`

#### 2.4 JWKS endpoint
- [x] Реализовать сервис для генерации JWKS
- [x] Реализовать кэширование JWKS в Redis
- [x] Создать endpoint `GET /.well-known/jwks.json`
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/services/jwks_service.py`
- `auth-service/app/api/v1/jwks.py`
- `auth-service/tests/test_jwks.py`

### Критерии приемки
- ✅ RSA ключи генерируются корректно (2048 bit)
- ✅ JWT токены создаются и валидируются
- ✅ Пароли хэшируются с bcrypt (cost 12)
- ✅ JWKS endpoint возвращает публичные ключи
- ✅ Все тесты проходят

### Время: 2-3 дня

---

## Итерация 3: User Service и аутентификация ✅ ЗАВЕРШЕНО

### Задачи

#### 3.1 User Service
- [x] Реализовать создание пользователя
- [x] Реализовать поиск пользователя по username/email
- [x] Реализовать проверку пароля
- [x] Реализовать обновление last_login_at
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/services/user_service.py`
- `auth-service/tests/test_user_service.py`

#### 3.2 OAuth Client Service
- [x] Реализовать поиск клиента по client_id
- [x] Реализовать проверку client_secret
- [x] Реализовать валидацию allowed_scopes
- [x] Реализовать валидацию allowed_grant_types
- [x] Добавить кэширование в Redis
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/services/oauth_client_service.py`
- `auth-service/tests/test_oauth_client_service.py`

#### 3.3 Auth Service
- [x] Реализовать аутентификацию пользователя
- [x] Реализовать создание токенов
- [x] Реализовать валидацию scope
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/services/auth_service.py`
- `auth-service/tests/test_auth_service.py`

### Критерии приемки
- ✅ Пользователь создается с хэшированным паролем
- ✅ Аутентификация работает корректно
- ✅ Scope валидируется
- ✅ Все тесты проходят

### Время: 2-3 дня

---

## Итерация 4: OAuth2 Password Grant ✅ ЗАВЕРШЕНО

### Задачи

#### 4.1 Refresh Token Service
- [x] Реализовать создание refresh token
- [x] Реализовать сохранение в БД (хэш jti)
- [x] Реализовать валидацию refresh token
- [x] Реализовать ротацию refresh token
- [x] Реализовать отзыв refresh token
- [x] Реализовать обнаружение reuse
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/services/refresh_token_service.py`
- `auth-service/tests/test_refresh_token_service.py`

#### 4.2 OAuth Token Endpoint - Password Grant
- [x] Создать endpoint `POST /oauth/token`
- [x] Реализовать обработку password grant
- [x] Валидация входных параметров
- [x] Обработка ошибок (OAuth2 compliant)
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/api/v1/oauth.py`
- `auth-service/tests/test_oauth_password_grant.py`

#### 4.3 OAuth Token Endpoint - Refresh Token Grant
- [x] Реализовать обработку refresh_token grant
- [x] Валидация refresh token
- [x] Ротация refresh token
- [x] Обработка ошибок
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/api/v1/oauth.py` (обновить)
- `auth-service/tests/test_oauth_refresh_grant.py`

#### 4.4 Интеграционные тесты
- [x] Полный flow: login → access token → refresh → new tokens
- [x] Тест на reuse detection
- [x] Тест на истекшие токены
- [x] Тест на невалидные credentials

**Файлы:**
- `auth-service/tests/test_oauth_integration.py`

### Критерии приемки
- ✅ Password grant работает корректно
- ✅ Refresh token grant работает корректно
- ✅ Refresh token ротируется
- ✅ Reuse detection работает
- ✅ Все тесты проходят

### Время: 3-4 дня

---

## Итерация 5: Rate Limiting и защита ✅ ЗАВЕРШЕНО

### Задачи

#### 5.1 Rate Limiter Service
- [x] Реализовать rate limiting на IP
- [x] Реализовать rate limiting на username
- [x] Использовать Redis для счетчиков
- [x] Настроить лимиты (5/min на IP, 10/hour на username)
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/services/rate_limiter.py`
- `auth-service/tests/test_rate_limiter.py`

#### 5.2 Brute-force защита
- [x] Реализовать подсчет неудачных попыток
- [x] Реализовать временную блокировку
- [x] Интегрировать с Auth Service
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/services/brute_force_protection.py`
- `auth-service/tests/test_brute_force.py`

#### 5.3 Middleware для rate limiting
- [x] Создать middleware для применения rate limiting
- [x] Интегрировать в FastAPI приложение
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/middleware/rate_limit.py`
- `auth-service/tests/test_rate_limit_middleware.py`

#### 5.4 Валидация входных данных
- [x] Реализовать валидацию email
- [x] Реализовать валидацию пароля (сложность)
- [x] Реализовать валидацию scope
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/utils/validators.py`
- `auth-service/tests/test_validators.py`

### Критерии приемки
- ✅ Rate limiting работает на IP и username
- ✅ Brute-force защита блокирует атаки
- ✅ Валидация входных данных работает
- ✅ Все тесты проходят

### Время: 2-3 дня

---

## Итерация 6: Аудит и логирование ✅ ЗАВЕРШЕНО

### Задачи

#### 6.1 Audit Service
- [x] Реализовать логирование событий в БД
- [x] Реализовать логирование в structured logs
- [x] Добавить события: login, token_refresh, token_revoke
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/services/audit_service.py`
- `auth-service/tests/test_audit_service.py`

#### 6.2 Интеграция аудита
- [x] Интегрировать аудит в Auth Service
- [x] Интегрировать аудит в OAuth endpoints
- [x] Логировать IP и User-Agent
- [x] Добавить тесты

**Файлы:**
- `auth-service/app/services/auth_service.py` (обновить)
- `auth-service/app/api/v1/oauth.py` (обновить)

#### 6.3 Structured logging
- [x] Настроить JSON логирование
- [x] Добавить correlation ID
- [x] Настроить уровни логирования
- [x] Добавить логирование ошибок

**Файлы:**
- `auth-service/app/core/logging.py`
- `auth-service/app/middleware/logging.py`

### Критерии приемки
- ✅ События логируются в БД
- ✅ Structured logs в JSON формате
- ✅ Correlation ID прослеживается
- ✅ Все тесты проходят

### Время: 1-2 дня

---

## Итерация 7: Интеграция с Gateway ✅ ЗАВЕРШЕНО

### Задачи

#### 7.1 JWT Auth Middleware для Gateway
- [x] Создать `JWTAuthMiddleware`
- [x] Реализовать получение JWKS
- [x] Реализовать кэширование JWKS
- [x] Реализовать валидацию JWT
- [x] Добавить извлечение user_id и scope
- [x] Добавить тесты

**Файлы:**
- `gateway/app/middleware/jwt_auth.py`
- `gateway/tests/test_jwt_auth.py`

#### 7.2 Обновление Gateway
- [x] Добавить зависимость `python-jose[cryptography]`
- [x] Интегрировать `JWTAuthMiddleware`
- [x] Обновить конфигурацию
- [x] Добавить fallback на старую аутентификацию (переходный период)
- [x] Обновить тесты

**Файлы:**
- `gateway/pyproject.toml` (обновить)
- `gateway/app/main.py` (обновить)
- `gateway/app/core/config.py` (обновить)

#### 7.3 Интеграционные тесты
- [x] Тест полного flow: Auth Service → Gateway → Agent Runtime
- [x] Тест с невалидным токеном
- [x] Тест с истекшим токеном
- [x] Тест с отсутствующим токеном

**Файлы:**
- `tests/integration/test_auth_flow.py`

### Критерии приемки
- ✅ Gateway валидирует JWT токены
- ✅ JWKS кэшируется корректно
- ✅ User ID извлекается из токена
- ✅ Все тесты проходят

### Время: 2-3 дня

---

## Итерация 8: Интеграция с Agent Runtime ✅ ЗАВЕРШЕНО

### Задачи

#### 8.1 JWT Auth Middleware для Agent Runtime
- [x] Создать `JWTAuthMiddleware` (аналогично Gateway)
- [x] Интегрировать в Agent Runtime
- [x] Обновить конфигурацию
- [x] Добавить тесты

**Файлы:**
- `agent-runtime/app/middleware/jwt_auth.py`
- `agent-runtime/tests/test_jwt_auth.py`

#### 8.2 Обновление моделей
- [x] Добавить `user_id` в модели сессий
- [x] Обновить миграции
- [x] Обновить сервисы для использования `user_id`

**Файлы:**
- `agent-runtime/app/models/` (обновить)
- `agent-runtime/alembic/versions/` (новая миграция)

### Критерии приемки
- ✅ Agent Runtime валидирует JWT токены
- ✅ Сессии привязаны к пользователям
- ✅ Все тесты проходят

### Время: 1-2 дня

---

## Итерация 9: Документация и примеры ✅ ЗАВЕРШЕНО

### Задачи

#### 9.1 API документация
- [x] Настроить OpenAPI/Swagger
- [x] Добавить описания endpoints
- [x] Добавить примеры запросов/ответов
- [x] Добавить описания ошибок

**Файлы:**
- `auth-service/app/main.py` (обновить)
- `auth-service/docs/API_DOCUMENTATION.md`

#### 9.2 Руководство по развертыванию
- [x] Создать инструкцию по развертыванию
- [x] Описать настройку переменных окружения
- [x] Описать процесс миграций
- [x] Описать генерацию RSA ключей

**Файлы:**
- `auth-service/docs/DEPLOYMENT_GUIDE.md`

#### 9.3 Руководство по интеграции
- [x] Создать примеры для Flutter клиента
- [x] Создать примеры для других клиентов
- [x] Описать процесс получения токенов
- [x] Описать процесс обновления токенов

**Файлы:**
- `auth-service/docs/INTEGRATION_GUIDE.md`
- `auth-service/examples/flutter_client.dart`
- `auth-service/examples/python_client.py`

#### 9.4 Troubleshooting guide
- [x] Описать частые проблемы
- [x] Добавить решения
- [x] Добавить примеры логов

**Файлы:**
- `auth-service/docs/TROUBLESHOOTING.md`

### Критерии приемки
- ✅ API документация полная и актуальная
- ✅ Руководства понятны и содержат примеры
- ✅ Примеры кода работают

### Время: 2-3 дня

---

## Итерация 10: Тестирование и оптимизация ✅ ЗАВЕРШЕНО

### Задачи

#### 10.1 Unit тесты
- [x] Покрытие всех сервисов (coverage > 80%)
- [x] Покрытие всех утилит
- [x] Покрытие всех middleware

**Файлы:**
- `auth-service/tests/` (дополнить)

#### 10.2 Integration тесты
- [x] Полный OAuth2 flow
- [x] Интеграция с Gateway
- [x] Интеграция с Agent Runtime
- [x] Тесты с реальной БД и Redis

**Файлы:**
- `tests/integration/` (дополнить)

#### 10.3 Security тесты
- [x] Тест на SQL injection
- [x] Тест на JWT tampering
- [x] Тест на brute-force
- [x] Тест на refresh token reuse

**Файлы:**
- `auth-service/tests/security/`

#### 10.4 Performance тесты
- [x] Load testing (100 RPS)
- [x] Latency benchmarks
- [x] Database query optimization
- [x] Redis caching optimization

**Файлы:**
- `auth-service/tests/performance/`
- `auth-service/docs/PERFORMANCE_REPORT.md`

#### 10.5 Оптимизация
- [x] Оптимизация SQL запросов
- [x] Настройка connection pool
- [x] Настройка Redis кэширования
- [x] Профилирование и устранение bottlenecks

### Критерии приемки
- ✅ Coverage > 80%
- ✅ Все тесты проходят
- ✅ Performance требования выполнены (< 200ms p95)
- ✅ Security тесты проходят

### Время: 3-4 дня

---

## Итерация 11: Мониторинг и observability ✅ ЗАВЕРШЕНО

### Задачи

#### 11.1 Prometheus metrics
- [x] Добавить счетчики запросов
- [x] Добавить метрики latency
- [x] Добавить метрики ошибок
- [x] Добавить метрики БД и Redis

**Файлы:**
- `auth-service/app/middleware/metrics.py`
- `auth-service/app/core/metrics.py`

#### 11.2 Health checks
- [x] Расширить health check endpoint
- [x] Добавить проверку БД
- [x] Добавить проверку Redis
- [x] Добавить readiness probe

**Файлы:**
- `auth-service/app/api/v1/health.py`

#### 11.3 Alerting
- [x] Определить критические метрики
- [x] Создать правила алертинга
- [x] Документировать runbook

**Файлы:**
- `auth-service/docs/MONITORING.md`
- `auth-service/prometheus/alerts.yml`

### Критерии приемки
- ✅ Prometheus metrics экспортируются
- ✅ Health checks работают
- ✅ Alerting правила определены

### Время: 2-3 дня

---

## Итерация 12: Финализация и деплой ✅ ЗАВЕРШЕНО

### Задачи

#### 12.1 Code review
- [x] Провести code review всего кода
- [x] Исправить замечания
- [x] Проверить соответствие стандартам

#### 12.2 Финальное тестирование
- [x] Запустить все тесты
- [x] Проверить coverage
- [x] Провести ручное тестирование

#### 12.3 Подготовка к деплою
- [x] Создать production конфигурацию
- [x] Подготовить миграции
- [x] Создать backup план
- [x] Создать rollback план

**Файлы:**
- `auth-service/.env.production`
- `auth-service/docs/DEPLOYMENT_CHECKLIST.md`

#### 12.4 Деплой в staging
- [x] Развернуть в staging окружение
- [x] Провести smoke тесты
- [x] Провести нагрузочное тестирование
- [x] Исправить найденные проблемы

#### 12.5 Деплой в production
- [x] Развернуть в production
- [x] Мониторинг метрик
- [x] Проверка логов
- [x] Smoke тесты

### Критерии приемки
- ✅ Все тесты проходят
- ✅ Code review пройден
- ✅ Staging деплой успешен
- ✅ Production деплой успешен
- ✅ Метрики в норме

### Время: 2-3 дня

---

## Общая оценка времени

| Итерация | Описание | Время | Статус |
|----------|----------|-------|--------|
| 0 | Подготовка инфраструктуры | 1-2 дня | ✅ Завершено |
| 1 | Модели данных и миграции | 2-3 дня | ✅ Завершено |
| 2 | Криптография и безопасность | 2-3 дня | ✅ Завершено |
| 3 | User Service и аутентификация | 2-3 дня | ✅ Завершено |
| 4 | OAuth2 Password Grant | 3-4 дня | ✅ Завершено |
| 5 | Rate Limiting и защита | 2-3 дня | ✅ Завершено |
| 6 | Аудит и логирование | 1-2 дня | ✅ Завершено |
| 7 | Интеграция с Gateway | 2-3 дня | ✅ Завершено |
| 8 | Интеграция с Agent Runtime | 1-2 дня | ✅ Завершено |
| 9 | Документация и примеры | 2-3 дня | ✅ Завершено |
| 10 | Тестирование и оптимизация | 3-4 дня | ✅ Завершено |
| 11 | Мониторинг и observability | 2-3 дня | ✅ Завершено |
| 12 | Финализация и деплой | 2-3 дня | ✅ Завершено |
| **ИТОГО** | | **25-38 дней** | **✅ РЕАЛИЗОВАНО** |

**Фактическое время реализации:** ~35 рабочих дней (7 недель)
**Статус:** ✅ Production Ready (Январь 2026)

---

## Особенности использования SQLite

### Преимущества
- ✅ Простота развертывания (нет отдельного сервера БД)
- ✅ Соответствие архитектуре других сервисов CodeLab
- ✅ Нулевая конфигурация
- ✅ Легкое резервное копирование (один файл)

### Ограничения и решения

#### 1. Конкурентная запись
**Проблема:** SQLite имеет ограничения на конкурентную запись  
**Решение:**
- Использовать WAL (Write-Ahead Logging) режим
- Настроить правильные timeout для busy handler
- Минимизировать длительность транзакций

```python
# В database.py
engine = create_engine(
    "sqlite:///data/auth.db",
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
    pool_pre_ping=True,
)

# Включить WAL режим
with engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL"))
```

#### 2. Горизонтальное масштабирование
**Проблема:** SQLite не поддерживает распределенную работу  
**Решение:**
- Для MVP: один инстанс Auth Service
- Для production: миграция на PostgreSQL
- Использовать Redis для кэширования и rate limiting

#### 3. Отсутствие некоторых типов данных
**Проблема:** SQLite не имеет нативного UUID типа  
**Решение:**
- Использовать TEXT для хранения UUID
- Валидация на уровне приложения

```python
class User(Base):
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
```

### Миграция на PostgreSQL (Post-MVP)

Когда потребуется масштабирование:

1. Создать дамп SQLite БД
2. Конвертировать в PostgreSQL формат
3. Обновить connection string
4. Обновить типы данных (TEXT → UUID)
5. Протестировать миграцию

---

## Риски и митигация

### Риск 1: Проблемы с производительностью SQLite
**Вероятность:** Средняя  
**Влияние:** Среднее  
**Митигация:**
- Использовать WAL режим
- Агрессивное кэширование в Redis
- Оптимизация запросов и индексов
- План миграции на PostgreSQL

### Риск 2: Проблемы безопасности
**Вероятность:** Средняя  
**Влияние:** Критическое  
**Митигация:**
- Security тесты на каждой итерации
- Code review с фокусом на безопасность
- Использование проверенных библиотек (bcrypt, python-jose)

### Риск 3: Проблемы интеграции
**Вероятность:** Средняя  
**Влияние:** Высокое  
**Митигация:**
- Ранняя интеграция с Gateway (итерация 7)
- Интеграционные тесты
- Переходный период с поддержкой старой аутентификации

### Риск 4: Недостаточное покрытие тестами
**Вероятность:** Низкая  
**Влияние:** Среднее  
**Митигация:**
- Тесты пишутся параллельно с кодом
- Требование coverage > 80%
- Автоматическая проверка coverage в CI/CD

---

## Зависимости между итерациями

```
Итерация 0 (Инфраструктура)
    ↓
Итерация 1 (Модели данных)
    ↓
Итерация 2 (Криптография) ← Итерация 3 (User Service)
    ↓                              ↓
Итерация 4 (OAuth2 Password Grant)
    ↓
Итерация 5 (Rate Limiting) ← Итерация 6 (Аудит)
    ↓
Итерация 7 (Gateway) → Итерация 8 (Agent Runtime)
    ↓
Итерация 9 (Документация)
    ↓
Итерация 10 (Тестирование) → Итерация 11 (Мониторинг)
    ↓
Итерация 12 (Деплой)
```

---

## Команда и роли

### Backend Developer (1 человек)
- Основная разработка Auth Service
- Интеграция с существующими сервисами
- Написание тестов

### DevOps Engineer (0.5 человека)
- Настройка Docker Compose
- Настройка мониторинга
- Деплой в staging/production

### QA Engineer (0.5 человека)
- Тестирование
- Security тесты
- Performance тесты

**Итого:** 2 FTE (Full-Time Equivalent)

---

## Критерии успеха проекта

### Функциональные
- ✅ Пользователь может войти по login/password
- ✅ Пользователь может обновить access token
- ✅ Gateway валидирует JWT токены
- ✅ Refresh token ротируется корректно

### Нефункциональные
- ✅ Время ответа < 200ms (p95)
- ✅ Throughput > 100 RPS (для одного инстанса)
- ✅ Coverage > 80%
- ✅ Доступность > 99.9%

### Безопасность
- ✅ Rate limiting работает
- ✅ Brute-force защита работает
- ✅ JWT токены валидируются корректно
- ✅ Refresh token reuse обнаруживается

---

## Следующие шаги после MVP (Backlog)

### Планируемые улучшения

1. **Authorization Code Flow + PKCE** (4-6 недель) - для веб-приложений
2. **Client Credentials Grant** (2-3 недели) - для межсервисного взаимодействия
3. **RBAC** (4-6 недель) - ролевая модель доступа
4. **SSO с внешними провайдерами** (6-8 недель) - Google, GitHub
5. **Admin UI** (8-10 недель) - веб-интерфейс управления
6. **MFA** (4-6 недель) - двухфакторная аутентификация

### Текущий статус

✅ **MVP полностью реализован и работает в production**
- OAuth2 Password Grant
- Refresh Token Grant с rotation
- JWT токены (RS256)
- JWKS endpoint
- Rate limiting и brute-force защита
- Аудит логирование
- Интеграция с Gateway и Agent Runtime
- PostgreSQL/SQLite поддержка

---

## Контакты

**Разработчик:** Sergey Penkovsky  
**Email:** sergey.penkovsky@gmail.com  
**Проект:** CodeLab Auth Service  
**Версия документа:** 1.1  
**Дата:** 2026-01-05  
**Изменения:** Адаптация под SQLite вместо PostgreSQL
