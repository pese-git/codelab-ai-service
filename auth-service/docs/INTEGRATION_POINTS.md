# Интеграционные точки Auth Service с существующими сервисами

**Версия:** 1.0.0
**Дата:** 20 января 2026
**Статус:** ✅ Реализовано

---

## Обзор

Данный документ описывает точки интеграции Auth Service с существующими микросервисами платформы CodeLab.

---

## 1. Gateway Service

### 1.1 Текущее состояние

**Аутентификация:**
- Использует `InternalAuthMiddleware`
- Проверяет заголовок `X-Internal-Auth`
- Единый API ключ для всех запросов

**Файлы:**
- [`gateway/app/middleware/internal_auth.py`](../../gateway/app/middleware/internal_auth.py)
- [`gateway/app/core/config.py`](../../gateway/app/core/config.py)

### 1.2 Требуемые изменения

#### Добавить зависимости

```toml
# gateway/pyproject.toml
dependencies = [
    # ... существующие зависимости
    "python-jose[cryptography]==3.3.0",
]
```

#### Создать JWT Auth Middleware

```python
# gateway/app/middleware/jwt_auth.py
from jose import jwt, JWTError
import httpx
import time
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

class JWTAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, jwks_url: str, cache_ttl: int = 3600):
        super().__init__(app)
        self.jwks_url = jwks_url
        self.jwks_cache = None
        self.jwks_cache_time = 0
        self.cache_ttl = cache_ttl
    
    async def get_jwks(self):
        """Получить JWKS с кэшированием"""
        if time.time() - self.jwks_cache_time > self.cache_ttl:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_url)
                self.jwks_cache = response.json()
                self.jwks_cache_time = time.time()
        return self.jwks_cache
    
    async def dispatch(self, request: Request, call_next):
        # Публичные endpoints
        public_paths = ("/health", "/docs", "/openapi.json", "/redoc")
        if request.url.path in public_paths or request.url.path.startswith("/ws/"):
            return await call_next(request)
        
        # Извлечь токен
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401, 
                content={"error": "unauthorized", "error_description": "Missing or invalid Authorization header"}
            )
        
        token = auth_header[7:]
        
        # Валидировать JWT
        try:
            jwks = await self.get_jwks()
            payload = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                audience="codelab-api",
                options={"verify_exp": True}
            )
            
            # Проверить тип токена
            if payload.get("type") != "access":
                return JSONResponse(
                    status_code=401,
                    content={"error": "invalid_token", "error_description": "Invalid token type"}
                )
            
            # Добавить user_id и scope в request state
            request.state.user_id = payload["sub"]
            request.state.scope = payload.get("scope", "")
            request.state.client_id = payload.get("client_id")
            
        except JWTError as e:
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_token", "error_description": str(e)}
            )
        
        return await call_next(request)
```

#### Обновить конфигурацию

```python
# gateway/app/core/config.py
class AppConfig:
    # ... существующие настройки
    AUTH_SERVICE_URL: str = os.getenv("GATEWAY__AUTH_SERVICE_URL", "http://auth-service:8003")
    JWKS_URL: str = f"{AUTH_SERVICE_URL}/.well-known/jwks.json"
```

#### Интегрировать middleware (переходный период)

```python
# gateway/app/main.py
from app.middleware.jwt_auth import JWTAuthMiddleware
from app.middleware.internal_auth import InternalAuthMiddleware

app = FastAPI(title="CodeLab Gateway")

# Переходный период: поддержка обоих методов
USE_JWT_AUTH = os.getenv("GATEWAY__USE_JWT_AUTH", "false").lower() == "true"

if USE_JWT_AUTH:
    app.add_middleware(
        JWTAuthMiddleware,
        jwks_url=AppConfig.JWKS_URL
    )
else:
    app.add_middleware(InternalAuthMiddleware)
```

### 1.3 Использование user_id в endpoints

```python
# gateway/app/api/v1/endpoints.py
@router.post("/chat")
async def chat(request: Request, message: ChatMessage):
    user_id = request.state.user_id  # Извлечено из JWT
    scope = request.state.scope
    
    # Использовать user_id для логики
    # ...
```

---

## 2. Agent Runtime Service

### 2.1 Текущее состояние

**Аутентификация:**
- Использует `InternalAuthMiddleware`
- Проверяет заголовок `X-Internal-Auth`

**Модели:**
- Сессии не привязаны к пользователям
- Нет поля `user_id` в моделях

**Файлы:**
- [`agent-runtime/app/middleware/internal_auth.py`](../../agent-runtime/app/middleware/internal_auth.py)
- [`agent-runtime/app/services/session_manager.py`](../../agent-runtime/app/services/session_manager.py)

### 2.2 Требуемые изменения

#### Добавить зависимости

```toml
# agent-runtime/pyproject.toml
dependencies = [
    # ... существующие зависимости
    "python-jose[cryptography]==3.3.0",
]
```

#### Создать JWT Auth Middleware

Аналогично Gateway (см. выше)

#### Обновить модели сессий

```python
# agent-runtime/app/models/session.py (пример)
from sqlalchemy import Column, String, DateTime, Text

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)  # НОВОЕ ПОЛЕ
    # ... остальные поля
```

#### Создать миграцию

```python
# agent-runtime/alembic/versions/XXX_add_user_id_to_sessions.py
def upgrade():
    op.add_column('sessions', sa.Column('user_id', sa.String(36), nullable=True))
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
    
    # Для существующих сессий установить default user_id
    op.execute("UPDATE sessions SET user_id = 'system' WHERE user_id IS NULL")
    
    # Сделать поле обязательным
    op.alter_column('sessions', 'user_id', nullable=False)

def downgrade():
    op.drop_index('ix_sessions_user_id', 'sessions')
    op.drop_column('sessions', 'user_id')
```

#### Обновить Session Manager

```python
# agent-runtime/app/services/session_manager.py
class SessionManager:
    async def create_session(self, user_id: str, **kwargs):
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user_id,  # Использовать user_id из JWT
            # ...
        )
        # ...
    
    async def get_user_sessions(self, user_id: str):
        """Получить все сессии пользователя"""
        return await self.db.query(Session).filter(
            Session.user_id == user_id
        ).all()
```

---

## 3. LLM Proxy Service

### 3.1 Текущее состояние

**Аутентификация:**
- Использует `InternalAuthMiddleware`
- Проверяет заголовок `X-Internal-Auth`

**Файлы:**
- [`llm-proxy/app/middleware/internal_auth.py`](../../llm-proxy/app/middleware/internal_auth.py)

### 3.2 Требуемые изменения

#### Опция 1: Оставить внутреннюю аутентификацию

LLM Proxy используется только внутренними сервисами (Agent Runtime), поэтому можно оставить `X-Internal-Auth` для межсервисного взаимодействия.

#### Опция 2: Добавить JWT аутентификацию

Если требуется прямой доступ клиентов к LLM Proxy:

1. Добавить `JWTAuthMiddleware` (аналогично Gateway)
2. Проверять scope `llm:access`
3. Логировать использование по `user_id`

**Рекомендация:** Для MVP оставить внутреннюю аутентификацию.

---

## 4. Docker Compose интеграция

### 4.1 Добавить Auth Service

```yaml
# docker-compose.yml
services:
  auth-service:
    build:
      context: ./auth-service
      dockerfile: Dockerfile
    ports:
      - "${AUTH_SERVICE_PORT:-8003}:${AUTH_SERVICE_PORT:-8003}"
    volumes:
      - ./auth-service/data:/app/data  # SQLite БД
      - ./auth-service/keys:/app/keys  # RSA ключи
    environment:
      - ENVIRONMENT=${ENVIRONMENT}
      - PORT=${AUTH_SERVICE_PORT:-8003}
      - AUTH_SERVICE__DB_URL=sqlite:///data/auth.db
      - AUTH_SERVICE__REDIS_URL=redis://redis:6379/1
      - AUTH_SERVICE__LOG_LEVEL=${AUTH_SERVICE__LOG_LEVEL:-DEBUG}
      - AUTH_SERVICE__JWT_ISSUER=https://auth.codelab.local
      - AUTH_SERVICE__JWT_AUDIENCE=codelab-api
      - AUTH_SERVICE__ACCESS_TOKEN_LIFETIME=900
      - AUTH_SERVICE__REFRESH_TOKEN_LIFETIME=2592000
      - AUTH_SERVICE__PRIVATE_KEY_PATH=/app/keys/private_key.pem
      - AUTH_SERVICE__PUBLIC_KEY_PATH=/app/keys/public_key.pem
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - codelab-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${AUTH_SERVICE_PORT:-8003}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - codelab-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### 4.2 Обновить Gateway

```yaml
# docker-compose.yml
services:
  gateway:
    # ... существующая конфигурация
    environment:
      # ... существующие переменные
      - GATEWAY__AUTH_SERVICE_URL=http://auth-service:8003
      - GATEWAY__USE_JWT_AUTH=${GATEWAY__USE_JWT_AUTH:-false}
    depends_on:
      agent-runtime:
        condition: service_healthy
      auth-service:  # НОВАЯ ЗАВИСИМОСТЬ
        condition: service_healthy
```

### 4.3 Обновить Agent Runtime

```yaml
# docker-compose.yml
services:
  agent-runtime:
    # ... существующая конфигурация
    environment:
      # ... существующие переменные
      - AGENT_RUNTIME__AUTH_SERVICE_URL=http://auth-service:8003
      - AGENT_RUNTIME__USE_JWT_AUTH=${AGENT_RUNTIME__USE_JWT_AUTH:-false}
    depends_on:
      llm-proxy:
        condition: service_healthy
      auth-service:  # НОВАЯ ЗАВИСИМОСТЬ
        condition: service_healthy
```

### 4.4 Обновить .env.example

```bash
# .env.example

# ... существующие переменные

# Auth Service настройки
AUTH_SERVICE_PORT=8003
AUTH_SERVICE__LOG_LEVEL=DEBUG

# Gateway JWT настройки
GATEWAY__USE_JWT_AUTH=false  # true для включения JWT аутентификации

# Agent Runtime JWT настройки
AGENT_RUNTIME__USE_JWT_AUTH=false  # true для включения JWT аутентификации
```

---

## 5. Последовательность миграции

### Этап 1: Развертывание Auth Service (неделя 1-2)
1. Развернуть Auth Service
2. Создать тестовых пользователей
3. Протестировать OAuth2 flow
4. Убедиться, что JWKS endpoint работает

### Этап 2: Интеграция с Gateway (неделя 3)
1. Добавить `JWTAuthMiddleware` в Gateway
2. Установить `GATEWAY__USE_JWT_AUTH=false` (переходный период)
3. Протестировать с JWT токенами
4. Убедиться, что старая аутентификация работает

### Этап 3: Обновление Flutter клиента (неделя 4)
1. Реализовать OAuth2 flow в Flutter
2. Хранить токены в secure storage
3. Автоматическое обновление access token
4. Тестирование

### Этап 4: Переключение Gateway на JWT (неделя 5)
1. Установить `GATEWAY__USE_JWT_AUTH=true`
2. Мониторинг ошибок
3. Откат при проблемах

### Этап 5: Интеграция с Agent Runtime (неделя 6)
1. Добавить `JWTAuthMiddleware` в Agent Runtime
2. Обновить модели (добавить `user_id`)
3. Миграция БД
4. Переключить на JWT

### Этап 6: Удаление старой аутентификации (неделя 7-8)
1. Убедиться, что все клиенты используют JWT
2. Удалить `InternalAuthMiddleware`
3. Удалить `X-Internal-Auth` конфигурацию
4. Финальное тестирование

---

## 6. Обратная совместимость

### Гибридный middleware (переходный период)

```python
# gateway/app/middleware/hybrid_auth.py
class HybridAuthMiddleware(BaseHTTPMiddleware):
    """Поддержка JWT и X-Internal-Auth одновременно"""
    
    def __init__(self, app, jwks_url: str, internal_api_key: str):
        super().__init__(app)
        self.jwt_middleware = JWTAuthMiddleware(app, jwks_url)
        self.internal_api_key = internal_api_key
    
    async def dispatch(self, request: Request, call_next):
        # Публичные endpoints
        public_paths = ("/health", "/docs", "/openapi.json", "/redoc")
        if request.url.path in public_paths:
            return await call_next(request)
        
        # Попробовать JWT
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return await self.jwt_middleware.dispatch(request, call_next)
        
        # Fallback на X-Internal-Auth
        internal_auth = request.headers.get("X-Internal-Auth")
        if internal_auth == self.internal_api_key:
            # Установить system user_id для внутренних запросов
            request.state.user_id = "system"
            request.state.scope = "internal"
            return await call_next(request)
        
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized"}
        )
```

---

## 7. Тестирование интеграции

### 7.1 Unit тесты

```python
# tests/test_jwt_middleware.py
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

@pytest.fixture
def app_with_jwt_auth():
    app = FastAPI()
    app.add_middleware(
        JWTAuthMiddleware,
        jwks_url="http://auth-service:8003/.well-known/jwks.json"
    )
    
    @app.get("/protected")
    async def protected(request: Request):
        return {"user_id": request.state.user_id}
    
    return app

def test_jwt_auth_valid_token(app_with_jwt_auth, valid_jwt_token):
    client = TestClient(app_with_jwt_auth)
    response = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {valid_jwt_token}"}
    )
    assert response.status_code == 200

def test_jwt_auth_missing_token(app_with_jwt_auth):
    client = TestClient(app_with_jwt_auth)
    response = client.get("/protected")
    assert response.status_code == 401
```

### 7.2 Integration тесты

```python
# tests/integration/test_auth_flow.py
import pytest
import httpx

@pytest.mark.asyncio
async def test_full_auth_flow():
    # 1. Получить токены
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://auth-service:8003/oauth/token",
            data={
                "grant_type": "password",
                "username": "test@example.com",
                "password": "password123",
                "client_id": "codelab-flutter-app",
            }
        )
        assert response.status_code == 200
        tokens = response.json()
        access_token = tokens["access_token"]
    
    # 2. Использовать access token в Gateway
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://gateway:8000/api/v1/chat",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"message": "Hello"}
        )
        assert response.status_code == 200
```

---

## 8. Мониторинг интеграции

### Метрики для отслеживания

```python
# Prometheus metrics
jwt_validation_total = Counter(
    "jwt_validation_total",
    "Total JWT validations",
    ["service", "status"]
)

jwt_validation_duration = Histogram(
    "jwt_validation_duration_seconds",
    "JWT validation duration",
    ["service"]
)

jwks_cache_hits = Counter(
    "jwks_cache_hits_total",
    "JWKS cache hits",
    ["service"]
)
```

### Логирование

```python
logger.info(
    "JWT validation successful",
    extra={
        "user_id": user_id,
        "client_id": client_id,
        "scope": scope,
        "service": "gateway"
    }
)
```

---

## 9. Rollback план

### Если возникли проблемы с JWT аутентификацией:

1. **Немедленный откат:**
   ```bash
   # Отключить JWT аутентификацию
   docker-compose exec gateway sh -c 'export GATEWAY__USE_JWT_AUTH=false'
   docker-compose restart gateway
   ```

2. **Проверка логов:**
   ```bash
   docker-compose logs -f gateway | grep "JWT"
   docker-compose logs -f auth-service
   ```

3. **Восстановление:**
   - Вернуться к `X-Internal-Auth`
   - Исправить проблемы в Auth Service
   - Повторить миграцию

---

## 10. Контрольный список интеграции

### Auth Service
- [ ] Auth Service развернут и работает
- [ ] JWKS endpoint доступен
- [ ] Тестовые пользователи созданы
- [ ] OAuth2 flow протестирован

### Gateway
- [ ] `JWTAuthMiddleware` добавлен
- [ ] Зависимости установлены
- [ ] Конфигурация обновлена
- [ ] Тесты проходят
- [ ] Переходный период настроен

### Agent Runtime
- [ ] `JWTAuthMiddleware` добавлен
- [ ] Модели обновлены (user_id)
- [ ] Миграции применены
- [ ] Тесты проходят

### Flutter Client
- [ ] OAuth2 flow реализован
- [ ] Токены хранятся безопасно
- [ ] Автообновление токенов работает
- [ ] Обработка ошибок реализована

### Мониторинг
- [ ] Метрики настроены
- [ ] Логирование работает
- [ ] Alerting настроен
- [ ] Dashboard создан

---

## Контакты

**Разработчик:** Sergey Penkovsky  
**Email:** sergey.penkovsky@gmail.com  
**Проект:** CodeLab Auth Service Integration  
**Версия документа:** 1.0  
**Дата:** 2026-01-05
