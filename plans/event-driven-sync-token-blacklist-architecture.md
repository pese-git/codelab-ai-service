# Event-Driven синхронизация и Token Blacklist между codelab-auth-service и codelab-core-service

**Дата документа:** 31 марта 2026  
**Версия:** 1.0.0 (Draft)  
**Статус:** 🚀 Архитектурный анализ

---

## 📋 Executive Summary

Документ описывает детальные подходы для реализации **event-driven синхронизации** между `codelab-auth-service` и `codelab-core-service` с поддержкой **немедленной инвалидации JWT токенов через blacklist**.

### Ключевые решения:
- **Token Blacklist**: Redis-based хранилище с TTL для отозванных токенов
- **Event Broker**: Сравнительный анализ 3 подходов (Redis Streams, RabbitMQ, Kafka)
- **Event Schema**: Типизированные события (user.created, user.deleted, user.updated, token.revoked)
- **Synchronization**: Transactional Outbox pattern в auth-service, Event Consumer в core-service
- **Consistency Model**: Eventual consistency с гарантиями доставки

### Текущее состояние инфраструктуры:
- ✅ Redis 8.6.1 (кэширование, возможен message broker)
- ✅ PostgreSQL 16 (transactional storage)
- ✅ FastAPI (обе сервисы)
- ✅ JWT RS256 интеграция (уже реализована)
- ✅ User Isolation Middleware (уже в core-service)
- ✅ Event Outbox pattern (уже используется в core-service)

---

## 🔐 1. Архитектура Token Blacklist

### 1.1 Концепция и требования

**Проблема:** При удалении пользователя в auth-service выданные JWT токены остаются валидными до истечения (expiration). Нужен механизм немедленной инвалидации.

**Решение:** Token Blacklist — хранилище отозванных токенов с TTL равным времени жизни токена.

### 1.2 Структура данных в Redis

```
Redis Blacklist структура:
├── token_blacklist:{jti}              # Значение: 1 (флаг)
│                                      # TTL = max(token_exp - now, default_ttl)
│
├── user_tokens:{user_id}              # Set отозванных JTI токенов пользователя
│                                      # Для быстрого отзыва всех токенов
│
└── token_metadata:{jti}               # JSON с метаданными (опционально)
                                       # Причина отзыва, время отзыва, админ
```

**Примеры ключей:**
```
token_blacklist:550e8400-e29b-41d4-a716-446655440000  # Token JTI
user_tokens:123e4567-e89b-12d3-a456-426614174000    # User ID

# Примеры значений
REDIS> GET token_blacklist:550e8400-e29b-41d4-a716-446655440000
"1"

REDIS> SMEMBERS user_tokens:123e4567-e89b-12d3-a456-426614174000
1) "550e8400-e29b-41d4-a716-446655440000"
2) "660e8400-e29b-41d4-a716-446655440001"
```

### 1.3 API Blacklist Service

#### Интерфейс в auth-service

```python
# app/services/token_blacklist_service.py

class TokenBlacklistService:
    """Service для управления blacklist отозванных токенов"""
    
    def __init__(self, redis: Redis, logger):
        self.redis = redis
        self.logger = logger
        self.blacklist_prefix = "token_blacklist"
        self.user_tokens_prefix = "user_tokens"
        self.metadata_prefix = "token_metadata"
    
    async def revoke_token(
        self,
        token_jti: str,
        user_id: str,
        exp_timestamp: int,
        reason: str = "user_requested",
        admin_id: str | None = None
    ) -> bool:
        """
        Отозвать один токен
        
        Args:
            token_jti: JWT ID (jti claim)
            user_id: User ID (sub claim)
            exp_timestamp: Token expiration timestamp (для TTL)
            reason: Причина отзыва (user_requested, user_deleted, admin_revoke)
            admin_id: ID админа если admin_revoke
            
        Returns:
            True if revoked, False if already revoked
        """
        # TTL = время до истечения токена
        ttl = max(exp_timestamp - int(time.time()), 3600)
        
        # Добавить в основной blacklist
        key = f"{self.blacklist_prefix}:{token_jti}"
        result = await self.redis.setex(key, ttl, "1")
        
        # Добавить JTI в user_tokens для быстрого отзыва
        user_key = f"{self.user_tokens_prefix}:{user_id}"
        await self.redis.sadd(user_key, token_jti)
        await self.redis.expire(user_key, ttl)
        
        # Опционально: сохранить метаданные
        metadata_key = f"{self.metadata_prefix}:{token_jti}"
        metadata = {
            "user_id": user_id,
            "reason": reason,
            "revoked_at": datetime.utcnow().isoformat(),
            "admin_id": admin_id
        }
        await self.redis.setex(
            metadata_key,
            ttl,
            json.dumps(metadata)
        )
        
        self.logger.info(
            "token_revoked",
            token_jti=token_jti,
            user_id=user_id,
            reason=reason
        )
        
        return result is not None
    
    async def revoke_all_user_tokens(
        self,
        user_id: str,
        reason: str = "user_deleted",
        admin_id: str | None = None
    ) -> int:
        """
        Отозвать все активные токены пользователя
        
        Args:
            user_id: User ID
            reason: Причина отзыва
            admin_id: ID админа если admin_revoke
            
        Returns:
            Количество отозванных токенов
        """
        user_key = f"{self.user_tokens_prefix}:{user_id}"
        jtis = await self.redis.smembers(user_key)
        
        # Временная заглушка: в реальности нужно брать jti из БД auth-service
        # Здесь предполагаем, что jti хранятся в Redis
        count = 0
        for jti in jtis:
            await self.revoke_token(
                token_jti=jti,
                user_id=user_id,
                exp_timestamp=int(time.time()) + 86400,  # Примерное значение
                reason=reason,
                admin_id=admin_id
            )
            count += 1
        
        self.logger.info(
            "all_user_tokens_revoked",
            user_id=user_id,
            count=count,
            reason=reason
        )
        
        return count
    
    async def is_token_revoked(self, token_jti: str) -> bool:
        """
        Проверить если токен отозван
        
        Args:
            token_jti: JWT ID
            
        Returns:
            True if revoked, False if active
        """
        key = f"{self.blacklist_prefix}:{token_jti}"
        result = await self.redis.exists(key)
        return bool(result)
    
    async def get_token_metadata(self, token_jti: str) -> dict | None:
        """Получить метаданные отозванного токена (опционально)"""
        metadata_key = f"{self.metadata_prefix}:{token_jti}"
        data = await self.redis.get(metadata_key)
        if data:
            return json.loads(data)
        return None
```

#### Интерфейс в core-service

```python
# app/services/token_validation_service.py

class TokenValidationService:
    """Service для валидации токенов с проверкой blacklist"""
    
    def __init__(self, redis: Redis, jwks_client: JWKSClient, logger):
        self.redis = redis
        self.jwks_client = jwks_client
        self.logger = logger
        self.blacklist_prefix = "token_blacklist"
    
    async def validate_token_with_blacklist_check(
        self,
        token: str,
        issuer: str,
        audience: str
    ) -> dict:
        """
        Валидировать JWT токен и проверить если он в blacklist
        
        Args:
            token: JWT токен
            issuer: Expected issuer
            audience: Expected audience
            
        Returns:
            dict с payload если валиден
            
        Raises:
            JWTError: если невалиден или в blacklist
        """
        # 1. Базовая валидация JWT (подпись, exp, iss, aud)
        payload = await self.jwks_client.validate_token(
            token,
            issuer=issuer,
            audience=audience
        )
        
        # 2. Проверить если токен в blacklist
        jti = payload.get("jti")
        if not jti:
            raise JWTError("Missing 'jti' claim in token")
        
        is_revoked = await self._is_token_revoked(jti)
        if is_revoked:
            self.logger.warning(
                "token_is_revoked",
                token_jti=jti,
                user_id=payload.get("sub")
            )
            raise JWTError("Token has been revoked")
        
        return payload
    
    async def _is_token_revoked(self, token_jti: str) -> bool:
        """Проверить если токен в blacklist"""
        key = f"{self.blacklist_prefix}:{token_jti}"
        result = await self.redis.exists(key)
        return bool(result)
```

### 1.4 Интеграция с UserIsolationMiddleware

```python
# Обновленный app/middleware/user_isolation.py

class UserIsolationMiddleware(BaseHTTPMiddleware):
    """Middleware с поддержкой Token Blacklist проверки"""
    
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request and inject user context with blacklist validation."""
        if not request.url.path.startswith("/my/"):
            return await call_next(request)
        
        if request.url.path in ["/my/docs", "/my/openapi.json", "/health", "/ready"]:
            return await call_next(request)
        
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                logger.warning("missing_authorization_header", path=request.url.path)
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content=ErrorResponse(
                        detail="Missing or invalid Authorization header",
                        error_code="UNAUTHORIZED",
                    ).model_dump(mode='json'),
                )
            
            token = auth_header.split(" ")[1]
            
            # ✨ NEW: Валидация с проверкой blacklist
            token_validation_service = await get_token_validation_service()
            payload = await token_validation_service.validate_token_with_blacklist_check(
                token,
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
            )
            
            user_id_str = payload.get("sub")
            user_email = payload.get("email")
            if not user_id_str:
                raise JWTError("Missing 'sub' claim in token")
            
            user_id = UUID(user_id_str)
            
            # Inject user context
            request.state.user_id = user_id
            request.state.user_email = user_email
            request.state.user_prefix = f"user{user_id}"
            request.state.db_filter = {"user_id": user_id}
            
            response = await call_next(request)
            return response
        
        except JWTError as e:
            logger.warning("invalid_jwt_token", error=str(e), path=request.url.path)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=ErrorResponse(
                    detail="Invalid, expired, or revoked token",
                    error_code="INVALID_TOKEN",
                ).model_dump(mode='json'),
            )
```

### 1.5 Event для отзыва токенов

При удалении пользователя в auth-service публикуется событие:

```json
{
  "event_type": "user.deleted",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-03-31T11:16:30Z",
  "aggregate_type": "user",
  "aggregate_id": "123e4567-e89b-12d3-a456-426614174000",
  "data": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "reason": "admin_deletion"
  }
}
```

**В auth-service** (при получении события):
```python
# Отозвать все активные токены пользователя
await token_blacklist_service.revoke_all_user_tokens(
    user_id=event.data["user_id"],
    reason="user_deleted"
)
```

**В core-service** (при получении события):
```python
# Удалить все данные пользователя (CASCADE)
await user_service.delete_user_data_cascade(
    user_id=event.data["user_id"]
)
```

---

## 📡 2. Архитектура Event-Driven синхронизации

### 2.1 Общая схема взаимодействия

```
┌──────────────────────────────────────────────────────────────┐
│                    CODELAB-AUTH-SERVICE                      │
│                                                              │
│  ┌─────────────┐      ┌──────────────────┐                 │
│  │ User Model  │──┬───│ Outbox Publisher │                 │
│  └─────────────┘  │   └──────────┬───────┘                 │
│                   │              │                          │
│              [USER DELETE]        │ Events to broker        │
│                   │              │                          │
│                   └──────┬───────┘                          │
│                          │                                   │
│           ┌──────────────▼──────────────┐                   │
│           │   Event Outbox (Database)   │                   │
│           │  (transactional guarantee)  │                   │
│           └──────────────┬──────────────┘                   │
│                          │                                   │
│           ┌──────────────▼──────────────┐                   │
│           │  Token Blacklist Service    │                   │
│           │  (Redis: revoke tokens)     │                   │
│           └──────────────┬──────────────┘                   │
│                          │                                   │
└──────────────────────────┼──────────────────────────────────┘
                           │
                ┌──────────▼──────────┐
                │  MESSAGE BROKER     │
                │  (Redis/RMQ/Kafka)  │
                └──────────┬──────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼────────┐ ┌──────▼────────┐ ┌──────▼────────┐
│ Event Consumer │ │ Event Consumer│ │ Event Consumer│
│ (core-service) │ │(auth-service) │ │(other-service)│
│                │ │               │ │                │
│ ┌────────────┐ │ │ ┌───────────┐ │ │                │
│ │Delete User │ │ │ │Process    │ │ │                │
│ │Data (DB)   │ │ │ │Events     │ │ │                │
│ │  CASCADE   │ │ │ │(idempotent)│ │ │                │
│ └────────────┘ │ │ └───────────┘ │ │                │
└────────────────┘ └──────────────┘ └────────────────┘
```

### 2.2 Сравнительный анализ Message Broker

#### 2.2.1 Redis Streams

**Особенности:**
- Встроенная очередь сообщений (Redis 5.0+)
- Consumer Groups для масштабирования
- Персистенция на диск
- Уже есть Redis в инфраструктуре

**Преимущества:**
✅ Простота развертывания (нет новых компонентов)  
✅ Низкая латентность (in-memory)  
✅ TTL support для автоматической очистки  
✅ Встроенная подробная история событий  
✅ Хороша для small-to-medium throughput  

**Недостатки:**
❌ Память (все события в памяти)  
❌ Нет встроенной HA по умолчанию  
❌ Ограничена одной машиной (масштабирование сложнее)  
❌ Нет встроенной гарантии доставки по сети  
❌ Сложнее масштабировать на 100k+ событий/сек  

**Пример использования:**

```python
# app/services/event_publisher.py (auth-service)

class RedisStreamPublisher:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.stream_key = "user_events"
    
    async def publish_event(self, event: dict) -> str:
        """Publish event to Redis Stream"""
        message_id = await self.redis.xadd(
            self.stream_key,
            {"event": json.dumps(event)}
        )
        return message_id

# app/services/event_consumer.py (core-service)

class RedisStreamConsumer:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.stream_key = "user_events"
        self.group_name = "core-service-group"
        self.consumer_name = "core-service-1"
    
    async def start_consuming(self):
        """Consume events from Redis Stream"""
        # Create consumer group if not exists
        try:
            await self.redis.xgroup_create(
                self.stream_key,
                self.group_name,
                id="0"
            )
        except ResponseError:
            pass  # Group already exists
        
        while True:
            # Read pending messages first
            messages = await self.redis.xreadgroup(
                {self.stream_key: ">"},
                self.group_name,
                self.consumer_name,
                count=10,
                block=1000
            )
            
            for stream, stream_messages in messages or []:
                for message_id, message_data in stream_messages:
                    event = json.loads(message_data[b"event"])
                    await self.handle_event(event)
                    
                    # Acknowledge message
                    await self.redis.xack(
                        self.stream_key,
                        self.group_name,
                        message_id
                    )
```

---

#### 2.2.2 RabbitMQ

**Особенности:**
- Message Queue with Exchanges (topic, fanout, direct)
- Durable queues и persistent messages
- Dead Letter Exchange для обработки ошибок
- Встроенная HA с clustering

**Преимущества:**
✅ Надежность (гарантированная доставка)  
✅ Встроенный DLQ (Dead Letter Queue)  
✅ Хорошо для enterprise (банки, финтех)  
✅ Масштабируемость через кластеризацию  
✅ Гибкая маршрутизация (exchanges, bindings)  
✅ Requeue и retry механизмы  

**Недостатки:**
❌ Новая инфраструктура (docker-compose update)  
❌ Больше ресурсов (memory, CPU)  
❌ Сложнее в настройке (exchanges, queues, bindings)  
❌ Медленнее чем Redis (не in-memory optimized)  
❌ Требует мониторинга (RabbitMQ Management UI)  

**Пример использования:**

```python
# app/services/event_publisher.py (auth-service)

import aio_pika

class RabbitMQPublisher:
    def __init__(self, connection: aio_pika.RobustConnection):
        self.connection = connection
    
    async def publish_event(self, event: dict) -> None:
        """Publish event to RabbitMQ"""
        channel = await self.connection.channel()
        
        # Declare exchange
        exchange = await channel.declare_exchange(
            "user_events",
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        # Create message
        message = aio_pika.Message(
            body=json.dumps(event).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        
        # Publish
        routing_key = f"user.{event['event_type'].split('.')[-1]}"
        await exchange.publish(message, routing_key=routing_key)

# app/services/event_consumer.py (core-service)

class RabbitMQConsumer:
    def __init__(self, connection: aio_pika.RobustConnection):
        self.connection = connection
    
    async def start_consuming(self):
        """Consume events from RabbitMQ"""
        channel = await self.connection.channel()
        
        # Declare exchange
        exchange = await channel.declare_exchange(
            "user_events",
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        # Declare queue with DLQ
        queue = await channel.declare_queue(
            "core_service_user_events",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "user_events_dlx",
                "x-dead-letter-routing-key": "dlq"
            }
        )
        
        # Bind queue to exchange
        await queue.bind(exchange, routing_key="user.*")
        
        # Consume
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    event = json.loads(message.body)
                    await self.handle_event(event)
```

---

#### 2.2.3 Kafka

**Особенности:**
- Distributed event streaming platform
- Topics с partitions для масштабирования
- Consumer groups с offset tracking
- High throughput, strong durability

**Преимущества:**
✅ Максимальная масштабируемость (миллионы событий/сек)  
✅ Встроенная HA через replication  
✅ Event history (topic retention)  
✅ Параллельная обработка (partitions)  
✅ Stream processing (Kafka Streams, KSQL)  
✅ Сильная durability  

**Недостатки:**
❌ Сложная инфраструктура (zookeeper/kraft)  
❌ Больше ресурсов (disk space для retention)  
❌ Более высокая латентность чем Redis  
❌ Требует опытной команды для операций  
❌ Overhead для small throughput (над-инженеринг)  
❌ Сложнее debug'ить  

**Пример использования:**

```python
# app/services/event_publisher.py (auth-service)

from aiokafka import AIOKafkaProducer

class KafkaPublisher:
    def __init__(self, bootstrap_servers: str):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    
    async def start(self):
        await self.producer.start()
    
    async def stop(self):
        await self.producer.stop()
    
    async def publish_event(self, event: dict) -> None:
        """Publish event to Kafka"""
        topic = "user_events"
        partition_key = event["aggregate_id"]
        
        await self.producer.send_and_wait(
            topic,
            value=event,
            key=partition_key.encode(),
            timestamp_ms=int(time.time() * 1000)
        )

# app/services/event_consumer.py (core-service)

from aiokafka import AIOKafkaConsumer

class KafkaConsumer:
    def __init__(self, bootstrap_servers: str):
        self.consumer = AIOKafkaConsumer(
            'user_events',
            bootstrap_servers=bootstrap_servers,
            group_id='core_service_group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest'
        )
    
    async def start_consuming(self):
        """Consume events from Kafka"""
        await self.consumer.start()
        try:
            async for message in self.consumer:
                event = message.value
                await self.handle_event(event)
        finally:
            await self.consumer.stop()
```

---

#### 2.2.4 Сравнительная таблица

| Параметр | Redis Streams | RabbitMQ | Kafka |
|----------|---------------|----------|-------|
| **Зависимости** | Уже есть | Нужно добавить | Нужно добавить |
| **Освоение** | ⭐⭐ Легко | ⭐⭐⭐ Среднее | ⭐⭐⭐⭐ Сложно |
| **Операции** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Latency** | <5ms | 50-100ms | 100-200ms |
| **Throughput** | ~100k msg/s | ~1M msg/s | ~10M+ msg/s |
| **Durability** | Хорошо | Отличная | Отличная |
| **Масштабирование** | До ~1M | 100M+ | 1B+ |
| **Memory usage** | Высокое | Среднее | Среднее |
| **HA/Replication** | Sentinel | Clustering | Replication |
| **Retry/DLQ** | Manual | Built-in | Manual |
| **Multitenancy** | Проблемы | OK | OK |
| **Cost (Ops)** | Низкие | Средние | Высокие |
| **Best for** | ~100k events/s | Enterprise, DLQ | Ultra-scale |

---

### 2.3 Рекомендация по выбору

**Для текущего проекта рекомендуется: RabbitMQ**

**Обоснование:**
1. ✅ **Enterprise-grade надежность** — соответствует требованиям production
2. ✅ **Built-in DLQ и retry** — обработка ошибок из коробки
3. ✅ **Сбалансирован** — не over-engineered (как Kafka), но надежнее Redis
4. ✅ **Операционная поддержка** — хорошо задокументирован, большое сообщество
5. ✅ **Интеграция с Python** — excellent async support (aio-pika)
6. ✅ **Масштабируемость** — хватает на 10-100M events/sec (future-proof)
7. ⚠️ **Redis Streams** — хорош как первоначальное решение, но:
   - Будет проблема с retention при росте volume
   - Нет встроенного DLQ механизма
   - Нужна будет миграция на RabbitMQ/Kafka в будущем

**Миграционный путь (если выбрать Redis):**
```
Redis Streams (v1.0) → RabbitMQ (v2.0) → Kafka (v3.0, если масштаб потребует)
```

---

## 📋 3. Схемы событий (Event Schema)

### 3.1 Event envelope (общий формат)

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "user.deleted",
  "event_version": "1.0",
  "timestamp": "2026-03-31T11:16:30.000Z",
  "aggregate_type": "user",
  "aggregate_id": "123e4567-e89b-12d3-a456-426614174000",
  "correlation_id": "req-123456789",
  "causation_id": "event-987654321",
  "source": "auth-service",
  "data": {}
}
```

### 3.2 User Events

#### 3.2.1 user.created

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "user.created",
  "event_version": "1.0",
  "timestamp": "2026-03-31T11:16:30.000Z",
  "aggregate_type": "user",
  "aggregate_id": "123e4567-e89b-12d3-a456-426614174000",
  "source": "auth-service",
  "data": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "created_at": "2026-03-31T11:16:30.000Z"
  }
}
```

**Consumer (core-service):**
- Синхронизировать profile пользователя в core-service
- Создать изолированное рабочее пространство

#### 3.2.2 user.updated

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440001",
  "event_type": "user.updated",
  "event_version": "1.0",
  "timestamp": "2026-03-31T11:16:30.000Z",
  "aggregate_type": "user",
  "aggregate_id": "123e4567-e89b-12d3-a456-426614174000",
  "source": "auth-service",
  "data": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "newemail@example.com",
    "first_name": "John",
    "last_name": "Smith",
    "updated_at": "2026-03-31T11:16:30.000Z",
    "changes": ["email", "last_name"]
  }
}
```

**Consumer (core-service):**
- Обновить profile пользователя
- Уведомить активные sessions если email изменился

#### 3.2.3 user.deleted

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440002",
  "event_type": "user.deleted",
  "event_version": "1.0",
  "timestamp": "2026-03-31T11:16:30.000Z",
  "aggregate_type": "user",
  "aggregate_id": "123e4567-e89b-12d3-a456-426614174000",
  "source": "auth-service",
  "data": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "deleted_at": "2026-03-31T11:16:30.000Z",
    "reason": "admin_deletion",
    "admin_id": "admin-uuid"
  }
}
```

**Consumer (auth-service):**
- Отозвать ВСЕ активные токены пользователя
- Очистить session данные

**Consumer (core-service):**
- Удалить пользователя и все связанные данные (CASCADE)
- Закрыть все активные sessions/connections
- Удалить из кэшей

### 3.3 Token Events

#### 3.3.1 token.revoked

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440003",
  "event_type": "token.revoked",
  "event_version": "1.0",
  "timestamp": "2026-03-31T11:16:30.000Z",
  "aggregate_type": "token",
  "aggregate_id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "auth-service",
  "data": {
    "token_jti": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "token_type": "access",
    "token_exp": 1711960590,
    "revoked_at": "2026-03-31T11:16:30.000Z",
    "reason": "user_logout",
    "admin_id": null
  }
}
```

**Consumer (core-service):**
- Проверить если токен в blacklist (уже должен быть добавлен)
- Логирование

---

## 🔄 4. Диаграммы последовательности (Sequence Diagrams)

### 4.1 Сценарий: Удаление пользователя

```mermaid
sequenceDiagram
    participant Admin as Администратор
    participant AuthAPI as Auth Service API
    participant AuthDB as Auth DB
    participant TokenBL as Token Blacklist
    participant Broker as Message Broker
    participant CoreService as Core Service
    participant CoreDB as Core DB

    Admin->>AuthAPI: DELETE /admin/users/{user_id}
    activate AuthAPI
    
    AuthAPI->>AuthDB: Start Transaction
    activate AuthDB
    
    AuthDB->>AuthDB: Mark user as deleted
    AuthDB->>AuthDB: Get all active token JTIs
    
    Note over AuthDB: SELECT jti FROM tokens WHERE user_id = ? AND exp > NOW()
    
    AuthAPI->>TokenBL: Revoke all tokens (batch)
    activate TokenBL
    loop For each token JTI
        TokenBL->>TokenBL: Set token_blacklist:{jti} = 1 (TTL = exp - now)
        TokenBL->>TokenBL: Add JTI to user_tokens:{user_id} set
    end
    deactivate TokenBL
    
    AuthAPI->>Broker: Publish user.deleted event
    activate Broker
    
    AuthDB->>AuthDB: Commit Transaction
    deactivate AuthDB
    
    AuthAPI-->>Admin: 204 No Content
    deactivate AuthAPI
    
    Note over Broker: Event in queue: user.deleted
    
    Broker->>CoreService: Deliver event
    activate CoreService
    
    CoreService->>CoreDB: Start Transaction
    activate CoreDB
    
    CoreDB->>CoreDB: Delete all user projects
    CoreDB->>CoreDB: Delete all user agents
    CoreDB->>CoreDB: Delete all chat sessions
    CoreDB->>CoreDB: Delete user profile
    
    Note over CoreDB: Cascading deletes with constraints
    
    CoreDB->>CoreDB: Commit Transaction
    deactivate CoreDB
    
    CoreService->>CoreService: Acknowledge event
    deactivate CoreService
    
    deactivate Broker
```

### 4.2 Сценарий: Валидация токена (с blacklist проверкой)

```mermaid
sequenceDiagram
    participant Client as Client
    participant CoreAPI as Core Service API
    participant Middleware as User Isolation Middleware
    participant JWKS as JWKS Client
    participant Redis as Redis (Blacklist)
    participant Handler as Request Handler

    Client->>CoreAPI: GET /my/projects (Authorization: Bearer token)
    activate CoreAPI
    
    CoreAPI->>Middleware: Process Request
    activate Middleware
    
    Middleware->>Middleware: Extract token from header
    
    Middleware->>JWKS: Validate JWT (verify signature, exp, iss, aud)
    activate JWKS
    JWKS-->>Middleware: payload = {sub, jti, exp, ...}
    deactivate JWKS
    
    Middleware->>Redis: Check if token_blacklist:{jti} exists
    activate Redis
    
    alt Token is in blacklist
        Redis-->>Middleware: EXISTS returns 1
        Middleware-->>Client: 401 Unauthorized (Token revoked)
        deactivate Redis
        deactivate CoreAPI
    else Token is NOT in blacklist
        Redis-->>Middleware: EXISTS returns 0
        deactivate Redis
        
        Middleware->>Middleware: Inject user context to request.state
        
        Middleware->>Handler: Call next handler
        activate Handler
        
        Handler->>Handler: Process request (projects.list)
        
        Handler-->>Middleware: Response
        deactivate Handler
        
        Middleware-->>Client: 200 OK (Projects list)
    end
    
    deactivate Middleware
    deactivate CoreAPI
```

### 4.3 Сценарий: Event Consumer Retry и Error Handling

```mermaid
sequenceDiagram
    participant Broker as Message Broker
    participant Consumer as Event Consumer
    participant Handler as Event Handler
    participant Logger as Logger
    participant DLQ as Dead Letter Queue

    Broker->>Consumer: Deliver message (attempt 1)
    activate Consumer
    
    Consumer->>Handler: Process event
    activate Handler
    
    Note over Handler: Try to update user profile
    
    alt Success
        Handler-->>Consumer: OK
        deactivate Handler
        
        Consumer->>Broker: Acknowledge message
        Consumer-->>Broker: (message removed from queue)
        
        Consumer->>Logger: Log success
    else Temporary Error (e.g., DB connection lost)
        Handler-->>Consumer: Retry Exception
        deactivate Handler
        
        Consumer->>Logger: Log error (attempt 1)
        
        Consumer->>Broker: Negative acknowledgement + delay
        
        Note over Broker: Schedule retry with backoff
        
        Broker->>Consumer: Deliver message again (after delay)
        activate Consumer
        activate Handler
        
        Handler-->>Consumer: OK
        deactivate Handler
        
        Consumer->>Broker: Acknowledge message
        deactivate Consumer
    else Permanent Error (max retries exceeded)
        Handler-->>Consumer: Fatal Exception
        deactivate Handler
        
        Consumer->>Logger: Log error (attempt 5 - FAILED)
        
        Consumer->>DLQ: Send to Dead Letter Queue
        Consumer-->>Broker: Acknowledge (with error flag)
        
        Note over DLQ: Manual investigation needed
    end
    
    deactivate Consumer
```

---

## 💻 5. Примеры кода и конфигурации

### 5.1 RabbitMQ docker-compose конфигурация

```yaml
# Добавить в docker-compose.yml

rabbitmq:
  image: rabbitmq:3.14-management-alpine
  container_name: codelab-rabbitmq
  environment:
    RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-guest}
    RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-guest}
    RABBITMQ_DEFAULT_VHOST: ${RABBITMQ_VHOST:-/}
  ports:
    - "${RABBITMQ_PORT:-5672}:5672"        # AMQP
    - "${RABBITMQ_MGMT_PORT:-15672}:15672" # Management UI
  volumes:
    - rabbitmq_data:/var/lib/rabbitmq
  healthcheck:
    test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 10s
  networks:
    - codelab-ai-service-network
  restart: unless-stopped

volumes:
  rabbitmq_data:
```

### 5.2 Environment variables

```bash
# .env

# RabbitMQ
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VHOST=/

# Event Config
EVENT_BROKER_TYPE=rabbitmq  # or redis, kafka
EVENT_MAX_RETRIES=5
EVENT_INITIAL_RETRY_DELAY=5
EVENT_MAX_RETRY_DELAY=300
```

### 5.3 Auth Service: Отправка события при удалении пользователя

```python
# codelab-auth-service/app/services/user_service.py

from datetime import datetime, timezone
from app.services.event_publisher import get_event_publisher
from app.core.models import User

class UserService:
    """User management service"""
    
    async def delete_user(
        self,
        user_id: str,
        session: AsyncSession,
        admin_id: str | None = None
    ) -> bool:
        """
        Delete user and publish event
        
        Args:
            user_id: User UUID to delete
            session: Database session
            admin_id: Admin who initiated deletion (if applicable)
            
        Returns:
            True if deleted, False if not found
        """
        # Get user
        user = await session.get(User, user_id)
        if not user:
            return False
        
        try:
            # Get all active tokens for revocation
            active_tokens = await session.execute(
                select(RefreshToken).where(
                    (RefreshToken.user_id == user_id) &
                    (RefreshToken.exp > datetime.now(timezone.utc))
                )
            )
            token_jtis = [t.jti for t in active_tokens.scalars()]
            
            # Mark user as deleted in DB
            user.is_deleted = True
            user.deleted_at = datetime.now(timezone.utc)
            await session.commit()
            
            # ✨ CRITICAL: Publish event AFTER DB commit
            event_publisher = get_event_publisher()
            await event_publisher.publish_event(
                event_type="user.deleted",
                aggregate_type="user",
                aggregate_id=user_id,
                data={
                    "user_id": user_id,
                    "email": user.email,
                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                    "reason": "admin_deletion" if admin_id else "user_requested",
                    "admin_id": admin_id,
                    "token_jtis": token_jtis  # For immediate revocation
                }
            )
            
            logger.info(
                "user_deleted",
                user_id=user_id,
                admin_id=admin_id,
                token_count=len(token_jtis)
            )
            
            return True
        
        except Exception as e:
            logger.error("user_deletion_failed", user_id=user_id, error=str(e))
            await session.rollback()
            raise
```

### 5.4 Auth Service: Event Publisher (RabbitMQ)

```python
# codelab-auth-service/app/services/event_publisher.py

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aio_pika
from aio_pika import ExchangeType, DeliveryMode

from app.core.config import settings, logger

_publisher_instance: "EventPublisher | None" = None

class EventPublisher:
    """RabbitMQ event publisher with reliability"""
    
    EXCHANGE_NAME = "user_events"
    EXCHANGE_TYPE = ExchangeType.TOPIC
    
    def __init__(self, connection: aio_pika.RobustConnection):
        self.connection = connection
        self.exchange = None
        self.channel = None
    
    async def initialize(self) -> None:
        """Initialize RabbitMQ connection and exchange"""
        self.channel = await self.connection.channel()
        
        self.exchange = await self.channel.declare_exchange(
            name=self.EXCHANGE_NAME,
            type=self.EXCHANGE_TYPE,
            durable=True,
            auto_delete=False
        )
        
        logger.info("event_publisher_initialized", exchange=self.EXCHANGE_NAME)
    
    async def publish_event(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        data: dict[str, Any],
        correlation_id: str | None = None
    ) -> str:
        """
        Publish event to message broker
        
        Args:
            event_type: e.g., "user.deleted", "user.updated"
            aggregate_type: e.g., "user", "token"
            aggregate_id: UUID of aggregate
            data: Event payload
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            event_id (UUID)
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat() + "Z"
        
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "event_version": "1.0",
            "timestamp": timestamp,
            "aggregate_type": aggregate_type,
            "aggregate_id": str(aggregate_id),
            "correlation_id": correlation_id or event_id,
            "source": "auth-service",
            "data": data
        }
        
        # Routing key based on event type
        routing_key = f"{aggregate_type}.{event_type.split('.')[-1]}"
        
        # Create message
        message = aio_pika.Message(
            body=json.dumps(event).encode('utf-8'),
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            correlation_id=correlation_id or event_id,
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000)
        )
        
        # Publish
        try:
            await self.exchange.publish(
                message=message,
                routing_key=routing_key
            )
            
            logger.info(
                "event_published",
                event_id=event_id,
                event_type=event_type,
                aggregate_id=aggregate_id
            )
            
            return event_id
        
        except Exception as e:
            logger.error(
                "event_publish_failed",
                event_id=event_id,
                event_type=event_type,
                error=str(e)
            )
            raise

async def get_event_publisher() -> EventPublisher:
    """Get or create event publisher singleton"""
    global _publisher_instance
    if _publisher_instance is None:
        raise RuntimeError("EventPublisher not initialized")
    return _publisher_instance

async def initialize_event_publisher(
    rabbitmq_url: str
) -> EventPublisher:
    """Initialize event publisher on startup"""
    global _publisher_instance
    
    connection = await aio_pika.connect_robust(rabbitmq_url)
    _publisher_instance = EventPublisher(connection)
    await _publisher_instance.initialize()
    
    return _publisher_instance

async def close_event_publisher() -> None:
    """Close event publisher on shutdown"""
    global _publisher_instance
    if _publisher_instance and _publisher_instance.connection:
        await _publisher_instance.connection.close()
        _publisher_instance = None
```

### 5.5 Core Service: Event Consumer (RabbitMQ)

```python
# codelab-core-service/app/services/event_consumer.py

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Callable, Any
from uuid import UUID

import aio_pika
from aio_pika import ExchangeType

from app.config import settings
from app.logging_config import get_logger
from app.services.user_service import UserService

logger = get_logger(__name__)

class EventConsumer:
    """RabbitMQ event consumer with retry and DLQ support"""
    
    EXCHANGE_NAME = "user_events"
    EXCHANGE_TYPE = ExchangeType.TOPIC
    
    def __init__(
        self,
        connection: aio_pika.RobustConnection,
        user_service: UserService
    ):
        self.connection = connection
        self.user_service = user_service
        self.channel = None
        self.queue = None
        self.exchange = None
        self.running = False
    
    async def initialize(self) -> None:
        """Initialize RabbitMQ resources"""
        self.channel = await self.connection.channel()
        
        # Set QoS (prefetch)
        await self.channel.set_qos(prefetch_count=10)
        
        # Declare main exchange
        self.exchange = await self.channel.declare_exchange(
            name=self.EXCHANGE_NAME,
            type=self.EXCHANGE_TYPE,
            durable=True,
            auto_delete=False
        )
        
        # Declare DLX (Dead Letter Exchange)
        dlx = await self.channel.declare_exchange(
            name=f"{self.EXCHANGE_NAME}_dlx",
            type=ExchangeType.DIRECT,
            durable=True,
            auto_delete=False
        )
        
        # Declare DLQ (Dead Letter Queue)
        dlq = await self.channel.declare_queue(
            name=f"{self.EXCHANGE_NAME}_dlq",
            durable=True
        )
        
        await dlq.bind(dlx, routing_key="dlq")
        
        # Declare main queue with DLX routing
        self.queue = await self.channel.declare_queue(
            name="core_service_user_events",
            durable=True,
            arguments={
                "x-dead-letter-exchange": f"{self.EXCHANGE_NAME}_dlx",
                "x-dead-letter-routing-key": "dlq",
                "x-message-ttl": 86400000,  # 24 hours
                "x-max-length": 100000  # Prevent queue explosion
            }
        )
        
        # Bind queue to exchange
        await self.queue.bind(self.exchange, routing_key="user.*")
        
        logger.info(
            "event_consumer_initialized",
            queue=self.queue.name,
            exchange=self.EXCHANGE_NAME
        )
    
    async def start(self) -> None:
        """Start consuming events"""
        self.running = True
        
        logger.info("event_consumer_starting")
        
        try:
            async with self.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if not self.running:
                        break
                    
                    async with message.process(
                        ignore_processed=False
                    ):
                        await self._handle_message(message)
        
        except asyncio.CancelledError:
            logger.info("event_consumer_cancelled")
        except Exception as e:
            logger.error("event_consumer_error", error=str(e))
            raise
        finally:
            self.running = False
    
    async def stop(self) -> None:
        """Stop consuming events"""
        self.running = False
        if self.channel:
            await self.channel.close()
    
    async def _handle_message(self, message: aio_pika.IncomingMessage) -> None:
        """Handle incoming message with retry logic"""
        try:
            event = json.loads(message.body.decode('utf-8'))
            event_type = event.get("event_type")
            
            logger.info(
                "event_received",
                event_id=event.get("event_id"),
                event_type=event_type,
                aggregate_id=event.get("aggregate_id")
            )
            
            # Route to appropriate handler
            handler = self._get_event_handler(event_type)
            if not handler:
                logger.warning(
                    "event_handler_not_found",
                    event_type=event_type
                )
                return
            
            # Handle event
            await handler(event)
            
            logger.info(
                "event_processed",
                event_id=event.get("event_id"),
                event_type=event_type
            )
        
        except Exception as e:
            retry_count = message.delivery_tag & 0xFF  # Extract retry count
            
            if retry_count < settings.EVENT_MAX_RETRIES:
                # Retry with exponential backoff
                delay = min(
                    settings.EVENT_INITIAL_RETRY_DELAY * (2 ** retry_count),
                    settings.EVENT_MAX_RETRY_DELAY
                )
                
                logger.warning(
                    "event_processing_error_retry",
                    event_id=event.get("event_id"),
                    retry_count=retry_count,
                    next_retry_delay_seconds=delay,
                    error=str(e)
                )
                
                # Nack and requeue with delay
                await message.nack(requeue=True)
            else:
                # Max retries exceeded - will go to DLQ
                logger.error(
                    "event_processing_failed_max_retries",
                    event_id=event.get("event_id"),
                    event_type=event.get("event_type"),
                    max_retries=settings.EVENT_MAX_RETRIES,
                    error=str(e)
                )
    
    def _get_event_handler(self, event_type: str) -> Callable | None:
        """Get handler function for event type"""
        handlers = {
            "user.created": self._handle_user_created,
            "user.updated": self._handle_user_updated,
            "user.deleted": self._handle_user_deleted,
            "token.revoked": self._handle_token_revoked,
        }
        return handlers.get(event_type)
    
    async def _handle_user_created(self, event: dict[str, Any]) -> None:
        """Handle user.created event"""
        data = event.get("data", {})
        user_id = UUID(data.get("user_id"))
        
        # Sync user profile to core-service
        await self.user_service.sync_user_profile(
            user_id=user_id,
            email=data.get("email"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name")
        )
    
    async def _handle_user_updated(self, event: dict[str, Any]) -> None:
        """Handle user.updated event"""
        data = event.get("data", {})
        user_id = UUID(data.get("user_id"))
        
        # Update user profile
        await self.user_service.update_user_profile(
            user_id=user_id,
            email=data.get("email"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name")
        )
    
    async def _handle_user_deleted(self, event: dict[str, Any]) -> None:
        """Handle user.deleted event - CASCADE DELETE"""
        data = event.get("data", {})
        user_id = UUID(data.get("user_id"))
        
        logger.info(
            "handling_user_deletion",
            user_id=user_id,
            event_id=event.get("event_id")
        )
        
        # CASCADE delete all user data
        await self.user_service.delete_user_data_cascade(user_id=user_id)
    
    async def _handle_token_revoked(self, event: dict[str, Any]) -> None:
        """Handle token.revoked event - logging only"""
        data = event.get("data", {})
        
        logger.info(
            "token_revoked_event",
            token_jti=data.get("token_jti"),
            user_id=data.get("user_id"),
            reason=data.get("reason")
        )
        # Token is already in blacklist from auth-service
```

### 5.6 Core Service: Main app initialization

```python
# codelab-core-service/app/main.py (добавить в lifespan)

import aio_pika
from app.services.event_consumer import EventConsumer

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("application_starting")
    
    # ... existing code ...
    
    # Initialize RabbitMQ event consumer
    if settings.event_broker_type == "rabbitmq":
        rabbitmq_url = settings.rabbitmq_url
        rabbitmq_connection = await aio_pika.connect_robust(rabbitmq_url)
        
        event_consumer = EventConsumer(
            connection=rabbitmq_connection,
            user_service=user_service
        )
        await event_consumer.initialize()
        
        # Start consumer in background
        consumer_task = asyncio.create_task(event_consumer.start())
        app.state.event_consumer = event_consumer
        app.state.event_consumer_task = consumer_task
        
        logger.info("event_consumer_started")
    
    yield
    
    # Shutdown
    if hasattr(app.state, 'event_consumer'):
        await app.state.event_consumer.stop()
        logger.info("event_consumer_stopped")
    
    logger.info("application_shutdown_complete")
```

---

## 📅 6. План миграции

### 6.1 Фазы внедрения

#### **Фаза 1: Подготовка (1-2 недели)**

- [ ] Настроить RabbitMQ в docker-compose
- [ ] Создать Event schema в Protobuf/JSON
- [ ] Добавить зависимости (aio-pika, event libraries)
- [ ] Создать базовые services: EventPublisher, EventConsumer
- [ ] Добавить конфигурацию в .env

#### **Фаза 2: Token Blacklist (1-2 недели)**

- [ ] Реализовать TokenBlacklistService в auth-service
- [ ] Обновить TokenService для добавления JTI в токены (если не было)
- [ ] Интегрировать Token Blacklist Service с UserIsolationMiddleware в core-service
- [ ] Написать unit tests для blacklist логики
- [ ] Тестирование: отозвать токен, проверить если access заблокирован

#### **Фаза 3: Event Publishing (1-2 недели)**

- [ ] Реализовать EventPublisher в auth-service
- [ ] Обновить UserService.delete_user() для публикации событий
- [ ] Обновить UserService.update_user() для публикации событий
- [ ] Добавить Outbox pattern для гарантированной доставки (если требуется)
- [ ] Тестирование: отправить события в broker, проверить что доставляются

#### **Фаза 4: Event Consuming (1-2 недели)**

- [ ] Реализовать EventConsumer в core-service
- [ ] Реализовать event handlers (user.created, user.updated, user.deleted)
- [ ] Интегрировать retry logic и DLQ handling
- [ ] Написать unit tests для handlers
- [ ] Тестирование: получить события, обновить core-service данные

#### **Фаза 5: Интеграционное тестирование (1-2 недели)**

- [ ] E2E тесты: удалить пользователя в auth-service, проверить CASCADE delete в core-service
- [ ] E2E тесты: отозвать токен, проверить что access deny работает
- [ ] Load testing: 1000+ событий/сек
- [ ] Chaos testing: отключить RabbitMQ, проверить graceful degradation

#### **Фаза 6: Production Rollout (1 неделя)**

- [ ] Развернуть RabbitMQ в production
- [ ] Мониторинг: метрики события, DLQ размер, latency
- [ ] Алерты: DLQ превышение, publisher/consumer errors
- [ ] Документация: run books для операций

### 6.2 Backward compatibility

**Стратегия:**
1. Оба сервиса могут работать БЕЗ event broker (graceful degradation)
2. Core-service может валидировать токены без blacklist (проверка exp)
3. Gradual rollout: сначала publish, потом consume

**Конфигурация:**
```python
# app/config.py

class Settings:
    event_broker_enabled: bool = True  # Can disable temporarily
    event_broker_type: str = "rabbitmq"  # redis, rabbitmq, kafka
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq/"
    
    # Fallback behavior
    use_token_blacklist: bool = True  # Can disable
    use_event_sync: bool = True  # Can disable
```

### 6.3 Rollback strategy

**Если RabbitMQ отключится:**

```python
# Event Consumer Resilience
class EventConsumer:
    async def start(self):
        while self.running:
            try:
                await self._consume_loop()
            except aio_pika.exceptions.AMQPConnectionError:
                logger.error("rabbitmq_connection_lost", 
                            retry_in_seconds=30)
                await asyncio.sleep(30)  # Reconnect after 30s
                continue
            except Exception as e:
                logger.error("event_consumer_error", error=str(e))
                await asyncio.sleep(60)
                continue
```

**Если очередь переполнится (DLQ растет):**
1. Масштабировать consumers (горизонтально)
2. Оптимизировать handler логику
3. Увеличить RabbitMQ ресурсы (памяти, CPU)
4. Если критично — отключить event sync (SET use_event_sync=false)

---

## 💰 7. Оценка трудозатрат

### 7.1 Разбивка по компонентам

#### **Token Blacklist Service**
| Компонент | Effort | Notes |
|-----------|--------|-------|
| Redis data structure | 4 ч | Планирование структуры ключей |
| TokenBlacklistService (auth) | 8 ч | Revoke, check API |
| TokenValidationService (core) | 6 ч | Интеграция с JWKS |
| UserIsolationMiddleware update | 4 ч | Добавить blacklist check |
| Unit tests | 12 ч | Coverage ~80% |
| **Subtotal** | **34 ч** | |

#### **RabbitMQ Infrastructure**
| Компонент | Effort | Notes |
|-----------|--------|-------|
| Docker-compose setup | 2 ч | RabbitMQ + management UI |
| Configuration | 3 ч | .env, settings, health checks |
| Monitoring setup | 4 ч | Prometheus metrics, Grafana |
| Documentation | 3 ч | Ops runbooks |
| **Subtotal** | **12 ч** | |

#### **Event Publishing (Auth Service)**
| Компонент | Effort | Notes |
|-----------|--------|-------|
| Event schema design | 6 ч | JSON schemas, versioning |
| EventPublisher impl | 10 ч | RabbitMQ integration |
| UserService updates | 8 ч | Publish on user events |
| Outbox pattern (opt) | 12 ч | Transactional reliability |
| Unit tests | 12 ч | Coverage ~80% |
| **Subtotal** | **48 ч** | |

#### **Event Consuming (Core Service)**
| Компонент | Effort | Notes |
|-----------|--------|-------|
| EventConsumer impl | 10 ч | RabbitMQ consumer |
| Event handlers | 16 ч | 4 handlers * 4 ч |
| Retry/DLQ logic | 8 ч | Exponential backoff |
| Unit tests | 16 ч | Handler testing |
| Integration tests | 12 ч | End-to-end scenarios |
| **Subtotal** | **62 ч** | |

#### **Testing & QA**
| Компонент | Effort | Notes |
|-----------|--------|-------|
| Functional testing | 20 ч | Manual scenarios |
| Load testing | 16 ч | 1000+ msg/sec |
| Chaos testing | 12 ч | Failure scenarios |
| Documentation | 8 ч | Test plans, results |
| **Subtotal** | **56 ч** | |

#### **Documentation & Ops**
| Компонент | Effort | Notes |
|-----------|--------|-------|
| Architecture docs | 8 ч | Design decisions |
| API documentation | 6 ч | Event schemas |
| Operational runbooks | 6 ч | Troubleshooting |
| Training/knowledge transfer | 4 ч | Team alignment |
| **Subtotal** | **24 ч** | |

### 7.2 Итоговая оценка

| Category | Hours | Days (8h) | Weeks |
|----------|-------|-----------|-------|
| Token Blacklist | 34 | 4.25 | 1 |
| Infrastructure | 12 | 1.5 | 0.3 |
| Event Publishing | 48 | 6 | 1.2 |
| Event Consuming | 62 | 7.75 | 1.5 |
| Testing & QA | 56 | 7 | 1.4 |
| Documentation & Ops | 24 | 3 | 0.6 |
| **TOTAL** | **236** | **29.5** | **6** |

**Критический путь:** Event Consuming (62 ч) — это может быть параллелизировано с Event Publishing

**Оптимальное распределение команды:**
- Backend Dev #1: Token Blacklist (34 ч) + Event Publishing (48 ч) = 82 ч / ~4 недели
- Backend Dev #2: Event Consuming (62 ч) + Testing (56 ч) = 118 ч / ~6 недель
- DevOps/SRE: Infrastructure (12 ч) + Ops docs (8 ч) = 20 ч / ~1 неделя

**Total dev weeks (2 человека): ~6 недель**

---

## ⚠️ 8. Риски и митигация

### 8.1 Техничесские риски

| Риск | Вероятность | Impact | Митигация |
|------|------------|--------|-----------|
| RabbitMQ недоступность | Средняя | Высокий | Graceful degradation, fallback to TTL |
| Event loss при RabbitMQ crash | Низкая | Критический | Persistent messages, Outbox pattern |
| Infinite retry loop | Низкая | Высокий | Max retries + DLQ, circuit breaker |
| Cascade delete ошибки | Средняя | Критический | Transaction rollback, alerts |
| Token blacklist miss | Низкая | Критический | Double-check (blacklist + exp) |
| High latency consuming | Низкая | Средний | Scale consumers, optimize handlers |

### 8.2 Операционные риски

| Риск | Вероятность | Impact | Митигация |
|------|------------|--------|-----------|
| RabbitMQ OOM | Средняя | Высокий | Resource limits, queue size limits |
| DLQ переполнение | Средняя | Высокий | Alerts, automatic cleanup after investigation |
| Broker misconfiguration | Средняя | Высокий | IaC (terraform/ansible), code review |
| Consumer lag growth | Средняя | Высокий | Monitoring, auto-scaling consumers |
| Production debugging | Средняя | Средний | Logging, distributed tracing |

---

## 🎯 9. Рекомендации

### 9.1 Приоритеты реализации

**MUST (обязательно):**
1. ✅ Token Blacklist (немедленная блокировка токенов)
2. ✅ Event Publishing (уведомления об удалении)
3. ✅ Cascade Delete (удаление данных пользователя)

**SHOULD (желательно):**
4. ✅ RabbitMQ (вместо Redis Streams для надежности)
5. ✅ Retry logic и DLQ (обработка ошибок)
6. ✅ Monitoring и alerting

**COULD (опционально):**
7. ⚠️ Outbox pattern (если требуется 100% гарантия)
8. ⚠️ Event sourcing (если нужна история всех изменений)
9. ⚠️ Kafka (если масштаб > 100k msg/sec)

### 9.2 Best Practices

1. **Idempotency** — все handlers должны быть idempotent (одно событие не вызовет duplicate results)
2. **Correlation IDs** — использовать для tracing запросов через сервисы
3. **Circuit Breaker** — если consumer persistent ошибки, отключить его
4. **Graceful Shutdown** — обработать SIGTERM, дождаться ACK текущих сообщений
5. **Monitoring** — дозволять видеть состояние брокера, очередей, DLQ в реальном времени
6. **Testing** — chaos testing, fail-over scenarios, load testing

### 9.3 Дальнейшие улучшения (v2.0+)

- [ ] **Event Sourcing** — сохранить ALL события для аудита
- [ ] **CQRS Pattern** — отделить reads от writes
- [ ] **Sagas** — для distributed transactions
- [ ] **Event Replay** — восстановление данных после сбоев
- [ ] **Kafka migration** — если масштаб требует

---

## 📊 10. Метрики успеха

### 10.1 Функциональные метрики

- ✅ Токены инвалидируются в течение 100ms после отзыва
- ✅ Cascade delete завершается в течение 5s
- ✅ Events доставляются с 99.99% reliability
- ✅ Нет потери данных при сбоях сервиса

### 10.2 Операционные метрики

- 📊 Event latency p95 < 500ms
- 📊 DLQ размер < 100 сообщений
- 📊 Consumer lag < 5 сек
- 📊 RabbitMQ CPU < 70%
- 📊 RabbitMQ Memory < 80%

---

## 📚 Приложение: Полезные ссылки

- **RabbitMQ Docs:** https://www.rabbitmq.com/documentation.html
- **Redis Streams:** https://redis.io/docs/data-types/streams/
- **Apache Kafka:** https://kafka.apache.org/documentation/
- **aio-pika (Python):** https://aio-pika.readthedocs.io/
- **Event-Driven Architecture:** https://martinfowler.com/articles/201701-event-driven.html
- **Transactional Outbox Pattern:** https://microservices.io/patterns/data/transactional-outbox.html

---

**Документ подготовлен:** 31 марта 2026  
**Автор:** Architecture Team  
**Статус:** 🔄 Ожидается feedback и выбор решения
