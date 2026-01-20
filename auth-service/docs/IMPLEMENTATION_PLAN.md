# План реализации Auth Service

**Версия:** 1.0.0
**Дата:** 20 января 2026
**Статус:** ✅ Реализовано

---

## Обзор

Данный документ описывает пошаговый план реализации Auth Service для платформы CodeLab. План разбит на итерации с четкими задачами и критериями приемки.

**Важно:** В процессе разработки используется SQLite для разработки и PostgreSQL для production.

---

## Итерация 0: Подготовка инфраструктуры (1-2 дня)

### Задачи

#### 0.1 Создание структуры проекта
- [ ] Создать директорию `auth-service/`
- [ ] Настроить `pyproject.toml` с зависимостями
- [ ] Создать `Dockerfile`
- [ ] Создать `.env.example`
- [ ] Создать базовую структуру директорий

**Файлы:**
- `auth-service/pyproject.toml`
- `auth-service/Dockerfile`
- `auth-service/.env.example`
- `auth-service/.dockerignore`
- `auth-service/.gitignore`

#### 0.2 Настройка Docker Compose
- [ ] Добавить Redis сервис
- [ ] Добавить auth-service в docker-compose.yml
- [ ] Настроить сеть и зависимости
- [ ] Настроить volumes для SQLite БД

**Файлы:**
- `docker-compose.yml` (обновить)
- `.env.example` (обновить)

#### 0.3 Базовая конфигурация приложения
- [ ] Создать `app/core/config.py` с настройками
- [ ] Создать `app/main.py` с FastAPI приложением
- [ ] Добавить health check endpoint
- [ ] Настроить логирование

**Файлы:**
- `auth-service/app/core/config.py`
- `auth-service/app/main.py`
- `auth-service/app/__init__.py`

#### 0.4 Настройка базы данных
- [ ] Настроить SQLAlchemy для SQLite
- [ ] Настроить Alembic для миграций
- [ ] Создать базовую модель `Base`
- [ ] Настроить путь к SQLite файлу в volume

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

## Итерация 1: Модели данных и миграции (2-3 дня)

### Задачи

#### 1.1 Модель User
- [ ] Создать SQLAlchemy модель `User`
- [ ] Добавить валидацию полей
- [ ] Создать индексы
- [ ] Создать Alembic миграцию

**Файлы:**
- `auth-service/app/models/user.py`
- `auth-service/alembic/versions/001_create_users_table.py`

#### 1.2 Модель OAuth Client
- [ ] Создать SQLAlchemy модель `OAuthClient`
- [ ] Добавить валидацию полей
- [ ] Создать индексы
- [ ] Создать Alembic миграцию
- [ ] Добавить seed данные для тестовых клиентов

**Файлы:**
- `auth-service/app/models/oauth_client.py`
- `auth-service/alembic/versions/002_create_oauth_clients_table.py`
- `auth-service/alembic/versions/003_seed_oauth_clients.py`

#### 1.3 Модель Refresh Token
- [ ] Создать SQLAlchemy модель `RefreshToken`
- [ ] Добавить валидацию полей
- [ ] Создать индексы
- [ ] Создать Alembic миграцию

**Файлы:**
- `auth-service/app/models/refresh_token.py`
- `auth-service/alembic/versions/004_create_refresh_tokens_table.py`

#### 1.4 Модель Audit Log (опционально)
- [ ] Создать SQLAlchemy модель `AuditLog`
- [ ] Создать индексы
- [ ] Создать Alembic миграцию

**Файлы:**
- `auth-service/app/models/audit_log.py`
- `auth-service/alembic/versions/005_create_audit_logs_table.py`

#### 1.5 Pydantic схемы
- [ ] Создать схемы для User
- [ ] Создать схемы для OAuth Client
- [ ] Создать схемы для Token Response
- [ ] Создать схемы для OAuth Request

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

## Итерация 2: Криптография и безопасность (2-3 дня)

### Задачи

#### 2.1 Генерация RSA ключей
- [ ] Создать утилиту для генерации RSA ключей
- [ ] Реализовать хранение ключей (файловая система или env)
- [ ] Реализовать загрузку ключей при старте
- [ ] Поддержка множественных ключей (key rotation)

**Файлы:**
- `auth-service/app/core/security.py`
- `auth-service/app/utils/crypto.py`
- `auth-service/scripts/generate_keys.py`

#### 2.2 JWT сервис
- [ ] Реализовать создание access token
- [ ] Реализовать создание refresh token
- [ ] Реализовать валидацию JWT
- [ ] Реализовать извлечение payload из JWT
- [ ] Добавить тесты

**Файлы:**
- `auth-service/app/services/token_service.py`
- `auth-service/tests/test_token_service.py`

#### 2.3 Password hashing
- [ ] Реализовать хэширование паролей (bcrypt)
- [ ] Реализовать проверку паролей (constant-time)
- [ ] Добавить тесты

**Файлы:**
- `auth-service/app/utils/crypto.py`
- `auth-service/tests/test_crypto.py`

#### 2.4 JWKS endpoint
- [ ] Реализовать сервис для генерации JWKS
- [ ] Реализовать кэширование JWKS в Redis
- [ ] Создать endpoint `GET /.well-known/jwks.json`
- [ ] Добавить тесты

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

## Итерация 3: User Service и аутентификация (2-3 дня)

### Задачи

#### 3.1 User Service
- [ ] Реализовать создание пользователя
- [ ] Реализовать поиск пользователя по username/email
- [ ] Реализовать проверку пароля
- [ ] Реализовать обновление last_login_at
- [ ] Добавить тесты

**Файлы:**
- `auth-service/app/services/user_service.py`
- `auth-service/tests/test_user_service.py`

#### 3.2 OAuth Client Service
- [ ] Реализовать поиск клиента по client_id
- [ ] Реализовать проверку client_secret
- [ ] Реализовать валидацию allowed_scopes
- [ ] Реализовать валидацию allowed_grant_types
- [ ] Добавить кэширование в Redis
- [ ] Добавить тесты

**Файлы:**
- `auth-service/app/services/oauth_client_service.py`
- `auth-service/tests/test_oauth_client_service.py`

#### 3.3 Auth Service
- [ ] Реализовать аутентификацию пользователя
- [ ] Реализовать создание токенов
- [ ] Реализовать валидацию scope
- [ ] Добавить тесты

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

## Итерация 4: OAuth2 Password Grant (3-4 дня)

### Задачи

#### 4.1 Refresh Token Service
- [ ] Реализовать создание refresh token
- [ ] Реализовать сохранение в БД (хэш jti)
- [ ] Реализовать валидацию refresh token
- [ ] Реализовать ротацию refresh token
- [ ] Реализовать отзыв refresh token
- [ ] Реализовать обнаружение reuse
- [ ] Добавить тесты

**Файлы:**
- `auth-service/app/services/refresh_token_service.py`
- `auth-service/tests/test_refresh_token_service.py`

#### 4.2 OAuth Token Endpoint - Password Grant
- [ ] Создать endpoint `POST /oauth/token`
- [ ] Реализовать обработку password grant
- [ ] Валидация входных параметров
- [ ] Обработка ошибок (OAuth2 compliant)
- [ ] Добавить тесты

**Файлы:**
- `auth-service/app/api/v1/oauth.py`
- `auth-service/tests/test_oauth_password_grant.py`

#### 4.3 OAuth Token Endpoint - Refresh Token Grant
- [ ] Реализовать обработку refresh_token grant
- [ ] Валидация refresh token
- [ ] Ротация refresh token
- [ ] Обработка ошибок
- [ ] Добавить тесты

**Файлы:**
- `auth-service/app/api/v1/oauth.py` (обновить)
- `auth-service/tests/test_oauth_refresh_grant.py`

#### 4.4 Интеграционные тесты
- [ ] Полный flow: login → access token → refresh → new tokens
- [ ] Тест на reuse detection
- [ ] Тест на истекшие токены
- [ ] Тест на невалидные credentials

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

## Итерация 5: Rate Limiting и защита (2-3 дня)

### Задачи

#### 5.1 Rate Limiter Service
- [ ] Реализовать rate limiting на IP
- [ ] Реализовать rate limiting на username
- [ ] Использовать Redis для счетчиков
- [ ] Настроить лимиты (5/min на IP, 10/hour на username)
- [ ] Добавить тесты

**Файлы:**
- `auth-service/app/services/rate_limiter.py`
- `auth-service/tests/test_rate_limiter.py`

#### 5.2 Brute-force защита
- [ ] Реализовать подсчет неудачных попыток
- [ ] Реализовать временную блокировку
- [ ] Интегрировать с Auth Service
- [ ] Добавить тесты

**Файлы:**
- `auth-service/app/services/brute_force_protection.py`
- `auth-service/tests/test_brute_force.py`

#### 5.3 Middleware для rate limiting
- [ ] Создать middleware для применения rate limiting
- [ ] Интегрировать в FastAPI приложение
- [ ] Добавить тесты

**Файлы:**
- `auth-service/app/middleware/rate_limit.py`
- `auth-service/tests/test_rate_limit_middleware.py`

#### 5.4 Валидация входных данных
- [ ] Реализовать валидацию email
- [ ] Реализовать валидацию пароля (сложность)
- [ ] Реализовать валидацию scope
- [ ] Добавить тесты

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

## Итерация 6: Аудит и логирование (1-2 дня)

### Задачи

#### 6.1 Audit Service
- [ ] Реализовать логирование событий в БД
- [ ] Реализовать логирование в structured logs
- [ ] Добавить события: login, token_refresh, token_revoke
- [ ] Добавить тесты

**Файлы:**
- `auth-service/app/services/audit_service.py`
- `auth-service/tests/test_audit_service.py`

#### 6.2 Интеграция аудита
- [ ] Интегрировать аудит в Auth Service
- [ ] Интегрировать аудит в OAuth endpoints
- [ ] Логировать IP и User-Agent
- [ ] Добавить тесты

**Файлы:**
- `auth-service/app/services/auth_service.py` (обновить)
- `auth-service/app/api/v1/oauth.py` (обновить)

#### 6.3 Structured logging
- [ ] Настроить JSON логирование
- [ ] Добавить correlation ID
- [ ] Настроить уровни логирования
- [ ] Добавить логирование ошибок

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

## Итерация 7: Интеграция с Gateway (2-3 дня)

### Задачи

#### 7.1 JWT Auth Middleware для Gateway
- [ ] Создать `JWTAuthMiddleware`
- [ ] Реализовать получение JWKS
- [ ] Реализовать кэширование JWKS
- [ ] Реализовать валидацию JWT
- [ ] Добавить извлечение user_id и scope
- [ ] Добавить тесты

**Файлы:**
- `gateway/app/middleware/jwt_auth.py`
- `gateway/tests/test_jwt_auth.py`

#### 7.2 Обновление Gateway
- [ ] Добавить зависимость `python-jose[cryptography]`
- [ ] Интегрировать `JWTAuthMiddleware`
- [ ] Обновить конфигурацию
- [ ] Добавить fallback на старую аутентификацию (переходный период)
- [ ] Обновить тесты

**Файлы:**
- `gateway/pyproject.toml` (обновить)
- `gateway/app/main.py` (обновить)
- `gateway/app/core/config.py` (обновить)

#### 7.3 Интеграционные тесты
- [ ] Тест полного flow: Auth Service → Gateway → Agent Runtime
- [ ] Тест с невалидным токеном
- [ ] Тест с истекшим токеном
- [ ] Тест с отсутствующим токеном

**Файлы:**
- `tests/integration/test_auth_flow.py`

### Критерии приемки
- ✅ Gateway валидирует JWT токены
- ✅ JWKS кэшируется корректно
- ✅ User ID извлекается из токена
- ✅ Все тесты проходят

### Время: 2-3 дня

---

## Итерация 8: Интеграция с Agent Runtime (1-2 дня)

### Задачи

#### 8.1 JWT Auth Middleware для Agent Runtime
- [ ] Создать `JWTAuthMiddleware` (аналогично Gateway)
- [ ] Интегрировать в Agent Runtime
- [ ] Обновить конфигурацию
- [ ] Добавить тесты

**Файлы:**
- `agent-runtime/app/middleware/jwt_auth.py`
- `agent-runtime/tests/test_jwt_auth.py`

#### 8.2 Обновление моделей
- [ ] Добавить `user_id` в модели сессий
- [ ] Обновить миграции
- [ ] Обновить сервисы для использования `user_id`

**Файлы:**
- `agent-runtime/app/models/` (обновить)
- `agent-runtime/alembic/versions/` (новая миграция)

### Критерии приемки
- ✅ Agent Runtime валидирует JWT токены
- ✅ Сессии привязаны к пользователям
- ✅ Все тесты проходят

### Время: 1-2 дня

---

## Итерация 9: Документация и примеры (2-3 дня)

### Задачи

#### 9.1 API документация
- [ ] Настроить OpenAPI/Swagger
- [ ] Добавить описания endpoints
- [ ] Добавить примеры запросов/ответов
- [ ] Добавить описания ошибок

**Файлы:**
- `auth-service/app/main.py` (обновить)
- `auth-service/docs/API_DOCUMENTATION.md`

#### 9.2 Руководство по развертыванию
- [ ] Создать инструкцию по развертыванию
- [ ] Описать настройку переменных окружения
- [ ] Описать процесс миграций
- [ ] Описать генерацию RSA ключей

**Файлы:**
- `auth-service/docs/DEPLOYMENT_GUIDE.md`

#### 9.3 Руководство по интеграции
- [ ] Создать примеры для Flutter клиента
- [ ] Создать примеры для других клиентов
- [ ] Описать процесс получения токенов
- [ ] Описать процесс обновления токенов

**Файлы:**
- `auth-service/docs/INTEGRATION_GUIDE.md`
- `auth-service/examples/flutter_client.dart`
- `auth-service/examples/python_client.py`

#### 9.4 Troubleshooting guide
- [ ] Описать частые проблемы
- [ ] Добавить решения
- [ ] Добавить примеры логов

**Файлы:**
- `auth-service/docs/TROUBLESHOOTING.md`

### Критерии приемки
- ✅ API документация полная и актуальная
- ✅ Руководства понятны и содержат примеры
- ✅ Примеры кода работают

### Время: 2-3 дня

---

## Итерация 10: Тестирование и оптимизация (3-4 дня)

### Задачи

#### 10.1 Unit тесты
- [ ] Покрытие всех сервисов (coverage > 80%)
- [ ] Покрытие всех утилит
- [ ] Покрытие всех middleware

**Файлы:**
- `auth-service/tests/` (дополнить)

#### 10.2 Integration тесты
- [ ] Полный OAuth2 flow
- [ ] Интеграция с Gateway
- [ ] Интеграция с Agent Runtime
- [ ] Тесты с реальной БД и Redis

**Файлы:**
- `tests/integration/` (дополнить)

#### 10.3 Security тесты
- [ ] Тест на SQL injection
- [ ] Тест на JWT tampering
- [ ] Тест на brute-force
- [ ] Тест на refresh token reuse

**Файлы:**
- `auth-service/tests/security/`

#### 10.4 Performance тесты
- [ ] Load testing (100 RPS)
- [ ] Latency benchmarks
- [ ] Database query optimization
- [ ] Redis caching optimization

**Файлы:**
- `auth-service/tests/performance/`
- `auth-service/docs/PERFORMANCE_REPORT.md`

#### 10.5 Оптимизация
- [ ] Оптимизация SQL запросов
- [ ] Настройка connection pool для SQLite
- [ ] Настройка Redis кэширования
- [ ] Профилирование и устранение bottlenecks

### Критерии приемки
- ✅ Coverage > 80%
- ✅ Все тесты проходят
- ✅ Performance требования выполнены (< 200ms p95)
- ✅ Security тесты проходят

### Время: 3-4 дня

---

## Итерация 11: Мониторинг и observability (2-3 дня)

### Задачи

#### 11.1 Prometheus metrics
- [ ] Добавить счетчики запросов
- [ ] Добавить метрики latency
- [ ] Добавить метрики ошибок
- [ ] Добавить метрики БД и Redis

**Файлы:**
- `auth-service/app/middleware/metrics.py`
- `auth-service/app/core/metrics.py`

#### 11.2 Health checks
- [ ] Расширить health check endpoint
- [ ] Добавить проверку БД
- [ ] Добавить проверку Redis
- [ ] Добавить readiness probe

**Файлы:**
- `auth-service/app/api/v1/health.py`

#### 11.3 Alerting
- [ ] Определить критические метрики
- [ ] Создать правила алертинга
- [ ] Документировать runbook

**Файлы:**
- `auth-service/docs/MONITORING.md`
- `auth-service/prometheus/alerts.yml`

### Критерии приемки
- ✅ Prometheus metrics экспортируются
- ✅ Health checks работают
- ✅ Alerting правила определены

### Время: 2-3 дня

---

## Итерация 12: Финализация и деплой (2-3 дня)

### Задачи

#### 12.1 Code review
- [ ] Провести code review всего кода
- [ ] Исправить замечания
- [ ] Проверить соответствие стандартам

#### 12.2 Финальное тестирование
- [ ] Запустить все тесты
- [ ] Проверить coverage
- [ ] Провести ручное тестирование

#### 12.3 Подготовка к деплою
- [ ] Создать production конфигурацию
- [ ] Подготовить миграции
- [ ] Создать backup план
- [ ] Создать rollback план

**Файлы:**
- `auth-service/.env.production`
- `auth-service/docs/DEPLOYMENT_CHECKLIST.md`

#### 12.4 Деплой в staging
- [ ] Развернуть в staging окружение
- [ ] Провести smoke тесты
- [ ] Провести нагрузочное тестирование
- [ ] Исправить найденные проблемы

#### 12.5 Деплой в production
- [ ] Развернуть в production
- [ ] Мониторинг метрик
- [ ] Проверка логов
- [ ] Smoke тесты

### Критерии приемки
- ✅ Все тесты проходят
- ✅ Code review пройден
- ✅ Staging деплой успешен
- ✅ Production деплой успешен
- ✅ Метрики в норме

### Время: 2-3 дня

---

## Общая оценка времени

| Итерация | Описание | Время |
|----------|----------|-------|
| 0 | Подготовка инфраструктуры | 1-2 дня |
| 1 | Модели данных и миграции | 2-3 дня |
| 2 | Криптография и безопасность | 2-3 дня |
| 3 | User Service и аутентификация | 2-3 дня |
| 4 | OAuth2 Password Grant | 3-4 дня |
| 5 | Rate Limiting и защита | 2-3 дня |
| 6 | Аудит и логирование | 1-2 дня |
| 7 | Интеграция с Gateway | 2-3 дня |
| 8 | Интеграция с Agent Runtime | 1-2 дня |
| 9 | Документация и примеры | 2-3 дня |
| 10 | Тестирование и оптимизация | 3-4 дня |
| 11 | Мониторинг и observability | 2-3 дня |
| 12 | Финализация и деплой | 2-3 дня |
| **ИТОГО** | | **25-38 дней** |

**Реалистичная оценка с учетом рисков:** 30-40 рабочих дней (6-8 недель)

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

## Следующие шаги после MVP

1. **Миграция на PostgreSQL** (1-2 недели) - для горизонтального масштабирования
2. **Authorization Code Flow + PKCE** (4-6 недель)
3. **Client Credentials Grant** (2-3 недели)
4. **RBAC** (4-6 недель)
5. **SSO с внешними провайдерами** (6-8 недель)
6. **Admin UI** (8-10 недель)
7. **MFA** (4-6 недель)

---

## Контакты

**Разработчик:** Sergey Penkovsky  
**Email:** sergey.penkovsky@gmail.com  
**Проект:** CodeLab Auth Service  
**Версия документа:** 1.1  
**Дата:** 2026-01-05  
**Изменения:** Адаптация под SQLite вместо PostgreSQL
