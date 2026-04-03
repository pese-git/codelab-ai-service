# API Спецификация: CodeLab Admin Frontend

**Версия:** 1.0.0  
**Статус:** ✅ Production Ready  
**Дата обновления:** 2 апреля 2026

---

## 📡 Обзор API

Admin Frontend взаимодействует с двумя основными микросервисами:
- **codelab-auth-service** — управление пользователями и аутентификацией
- **codelab-core-service** — управление LLM провайдерами и аудитом

**Base URLs:**
- Auth Service: `http://auth-service:8003/`
- Core Service: `http://core-service:8001/`

**Версия API:** v1

---

## 🔐 Аутентификация

Все запросы требуют JWT Bearer Token в заголовке:

```
Authorization: Bearer {access_token}
```

**Получение токена:**

Frontend должен получить JWT token при логине через codelab-auth-service:

```http
POST /oauth/token HTTP/1.1
Host: auth-service:8003
Content-Type: application/x-www-form-urlencoded

grant_type=password&
username=admin@example.com&
password=SecurePassword123!&
client_id=codelab-admin&
scope=admin:read+admin:write
```

**Scope требования:**
- `admin:read` — чтение данных администратора (GET, HEAD)
- `admin:write` — запись данных (POST, PATCH, DELETE)
- `admin:audit` — доступ к audit log
- `admin:users` — управление пользователями
- `admin:llm` — управление LLM провайдерами

---

## 📌 User Management API

### 1. GET /admin/users

**Назначение:** Получить список всех пользователей с фильтрацией и пагинацией

**Endpoint:** `GET /admin/users?status=active&search=john&page=1&limit=20`

**Authentication:** Bearer Token (scope: `admin:read`, `admin:users`)

**Query Parameters:**

| Параметр | Тип | Обязательно | Описание |
|----------|-----|-----------|---------|
| `search` | string | ❌ | Поиск по email или username |
| `status` | enum | ❌ | Фильтр: `active`, `inactive`, `suspended`, `deleted` |
| `created_from` | ISO 8601 | ❌ | Фильтр по дате создания (от) |
| `created_to` | ISO 8601 | ❌ | Фильтр по дате создания (до) |
| `page` | integer | ❌ | Номер страницы (default: 1) |
| `limit` | integer | ❌ | Количество результатов на странице (default: 20, max: 100) |
| `sort_by` | string | ❌ | Поле сортировки: `created_at`, `last_login`, `email` |
| `sort_order` | enum | ❌ | `asc` или `desc` (default: `desc`) |

**Success Response (200 OK):**

```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "john@example.com",
      "username": "john_doe",
      "status": "active",
      "role": "user",
      "created_at": "2026-03-15T10:30:00Z",
      "last_login_at": "2026-04-02T14:25:00Z",
      "email_verified": true,
      "sessions_count": 2
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "email": "jane@example.com",
      "username": "jane_smith",
      "status": "inactive",
      "role": "user",
      "created_at": "2026-02-20T09:15:00Z",
      "last_login_at": "2026-03-25T11:00:00Z",
      "email_verified": true,
      "sessions_count": 0
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 156,
    "pages": 8
  }
}
```

**Error Responses:**

```json
// 401 Unauthorized — невалидный или истекший токен
{
  "error": "invalid_token",
  "error_description": "Token is invalid or expired"
}

// 403 Forbidden — недостаточно прав
{
  "error": "insufficient_scope",
  "error_description": "Required scope: admin:users"
}

// 400 Bad Request — невалидные параметры
{
  "error": "invalid_request",
  "error_description": "Invalid query parameters",
  "details": {
    "limit": "Must be between 1 and 100"
  }
}
```

**Сценарии использования:**

#### Scenario 1: Поиск активных пользователей
- **WHEN** админ открывает страницу Users Management
- **THEN** система запрашивает `GET /admin/users?status=active&limit=20`
- **AND** отображает таблицу с активными пользователями

#### Scenario 2: Поиск по email
- **WHEN** админ вводит "john" в поиск
- **THEN** система запрашивает `GET /admin/users?search=john`
- **AND** отображает результаты с фильтрацией в реальном времени

#### Scenario 3: Сортировка по последнему входу
- **WHEN** админ кликает на колонку "Last Login"
- **THEN** система запрашивает `GET /admin/users?sort_by=last_login&sort_order=desc`
- **AND** обновляет таблицу отсортированными данными

---

### 2. GET /admin/users/{user_id}

**Назначение:** Получить детальную информацию о конкретном пользователе

**Endpoint:** `GET /admin/users/550e8400-e29b-41d4-a716-446655440000`

**Authentication:** Bearer Token (scope: `admin:read`, `admin:users`)

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|---------|
| `user_id` | UUID | ID пользователя |

**Success Response (200 OK):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "john@example.com",
  "username": "john_doe",
  "status": "active",
  "role": "user",
  "created_at": "2026-03-15T10:30:00Z",
  "updated_at": "2026-04-01T15:45:00Z",
  "last_login_at": "2026-04-02T14:25:00Z",
  "last_login_ip": "192.168.1.100",
  "email_verified": true,
  "email_verified_at": "2026-03-15T10:35:00Z",
  "password_reset_at": null,
  "deleted_at": null,
  "profile": {
    "first_name": "John",
    "last_name": "Doe",
    "avatar_url": "https://example.com/avatar/john.jpg",
    "timezone": "Europe/Minsk"
  },
  "sessions": [
    {
      "id": "session-001",
      "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "ip_address": "192.168.1.100",
      "created_at": "2026-04-02T14:25:00Z",
      "last_activity_at": "2026-04-02T14:30:00Z",
      "expires_at": "2026-05-02T14:25:00Z",
      "is_active": true
    }
  ],
  "projects": [
    {
      "id": "proj-001",
      "name": "My AI Assistant",
      "created_at": "2026-03-20T08:00:00Z"
    }
  ]
}
```

**Error Responses:**

```json
// 404 Not Found — пользователь не найден
{
  "error": "user_not_found",
  "error_description": "User with ID 550e8400-e29b-41d4-a716-446655440000 not found"
}

// 401/403 — see above
```

**Сценарии использования:**

#### Scenario 1: Просмотр профиля пользователя
- **WHEN** админ кликает на пользователя в таблице
- **THEN** система запрашивает `GET /admin/users/{user_id}`
- **AND** отображает детальную страницу с информацией и сессиями

---

### 3. POST /admin/users/{user_id}/reset-password

**Назначение:** Инициировать сброс пароля для пользователя

**Endpoint:** `POST /admin/users/550e8400-e29b-41d4-a716-446655440000/reset-password`

**Authentication:** Bearer Token (scope: `admin:write`, `admin:users`)

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "send_email": true,
  "email_template": "admin_reset_password"
}
```

**Request Parameters:**

| Параметр | Тип | Обязательно | Описание |
|----------|-----|-----------|---------|
| `send_email` | boolean | ✅ | Отправить ссылку сброса на email пользователя |
| `email_template` | string | ❌ | Шаблон письма (default: `admin_reset_password`) |

**Success Response (200 OK):**

```json
{
  "success": true,
  "message": "Password reset initiated",
  "reset_token_sent": true,
  "expires_at": "2026-04-03T02:45:36Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Error Responses:**

```json
// 400 Bad Request — невалидный request
{
  "error": "invalid_request",
  "error_description": "send_email parameter is required"
}

// 409 Conflict — пользователь удален
{
  "error": "user_deleted",
  "error_description": "Cannot reset password for deleted user"
}

// 503 Service Unavailable — невозможно отправить email
{
  "error": "email_service_error",
  "error_description": "Failed to send reset email. Please try again later."
}
```

**Сценарии использования:**

#### Scenario 1: Сброс пароля пользователя
- **WHEN** админ кликает "Reset Password" на странице пользователя
- **THEN** система отправляет POST запрос к `/admin/users/{user_id}/reset-password`
- **AND** пользователь получает email с ссылкой для восстановления пароля
- **AND** админ видит подтверждение "Password reset email sent"

---

### 4. PATCH /admin/users/{user_id}/status

**Назначение:** Изменить статус пользователя (активировать, деактивировать, заблокировать)

**Endpoint:** `PATCH /admin/users/550e8400-e29b-41d4-a716-446655440000/status`

**Authentication:** Bearer Token (scope: `admin:write`, `admin:users`)

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "status": "suspended",
  "reason": "Account activity violation - multiple failed login attempts detected"
}
```

**Request Parameters:**

| Параметр | Тип | Обязательно | Описание |
|----------|-----|-----------|---------|
| `status` | enum | ✅ | Новый статус: `active`, `inactive`, `suspended` |
| `reason` | string | ❌ | Причина изменения статуса (для audit log) |

**Success Response (200 OK):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "suspended",
  "updated_at": "2026-04-02T14:45:00Z",
  "audit_id": "audit-123456",
  "sessions_revoked": 2
}
```

**Error Responses:**

```json
// 400 Bad Request — невалидный статус
{
  "error": "invalid_status",
  "error_description": "Status must be one of: active, inactive, suspended"
}

// 409 Conflict — уже в этом статусе
{
  "error": "user_already_suspended",
  "error_description": "User is already suspended"
}
```

**Сценарии использования:**

#### Scenario 1: Блокировка пользователя за подозрительную активность
- **WHEN** админ кликает "Suspend" на странице пользователя
- **THEN** система показывает диалог для ввода причины
- **AND** отправляет PATCH запрос с статусом `suspended`
- **AND** все активные сессии пользователя отзываются
- **AND** событие логируется в audit log

#### Scenario 2: Восстановление пользователя
- **WHEN** админ кликает "Activate" на странице suspended пользователя
- **THEN** система отправляет PATCH запрос с статусом `active`
- **AND** пользователь может вновь логиниться

---

## 🤖 LLM Providers Management API

### 5. GET /admin/llm-providers

**Назначение:** Получить список всех LLM провайдеров

**Endpoint:** `GET /admin/llm-providers?status=active&limit=20`

**Authentication:** Bearer Token (scope: `admin:read`, `admin:llm`)

**Query Parameters:**

| Параметр | Тип | Обязательно | Описание |
|----------|-----|-----------|---------|
| `status` | enum | ❌ | Фильтр: `active`, `inactive`, `error` |
| `search` | string | ❌ | Поиск по названию провайдера |
| `page` | integer | ❌ | Номер страницы (default: 1) |
| `limit` | integer | ❌ | Результатов на странице (default: 20, max: 100) |

**Success Response (200 OK):**

```json
{
  "data": [
    {
      "id": "prov-001",
      "name": "OpenAI Production",
      "provider_type": "openai",
      "status": "active",
      "api_url": "https://api.openai.com/v1",
      "models_count": 5,
      "users_count": 12,
      "last_used_at": "2026-04-02T13:45:00Z",
      "created_at": "2026-01-15T10:00:00Z",
      "last_tested_at": "2026-04-02T12:00:00Z",
      "test_status": "passed",
      "usage_stats": {
        "requests_today": 245,
        "tokens_today": 125000,
        "cost_today": 2.50
      }
    },
    {
      "id": "prov-002",
      "name": "Anthropic Claude",
      "provider_type": "anthropic",
      "status": "active",
      "api_url": "https://api.anthropic.com",
      "models_count": 3,
      "users_count": 8,
      "last_used_at": "2026-04-02T14:10:00Z",
      "created_at": "2026-02-01T09:30:00Z",
      "last_tested_at": "2026-04-02T12:15:00Z",
      "test_status": "passed",
      "usage_stats": {
        "requests_today": 89,
        "tokens_today": 45000,
        "cost_today": 1.80
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 2,
    "pages": 1
  }
}
```

**Сценарии использования:**

#### Scenario 1: Просмотр всех активных провайдеров
- **WHEN** админ открывает страницу LLM Providers
- **THEN** система запрашивает `GET /admin/llm-providers?status=active`
- **AND** отображает таблицу с провайдерами и статистикой использования

---

### 6. GET /admin/llm-providers/{provider_id}

**Назначение:** Получить детальную информацию о провайдере

**Endpoint:** `GET /admin/llm-providers/prov-001`

**Authentication:** Bearer Token (scope: `admin:read`, `admin:llm`)

**Success Response (200 OK):**

```json
{
  "id": "prov-001",
  "name": "OpenAI Production",
  "provider_type": "openai",
  "status": "active",
  "api_url": "https://api.openai.com/v1",
  "description": "Primary OpenAI provider for production workloads",
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-04-01T15:30:00Z",
  "created_by": "admin@example.com",
  "models": [
    {
      "id": "model-001",
      "name": "gpt-4",
      "display_name": "GPT-4",
      "context_window": 8192,
      "pricing": {
        "input": 0.03,
        "output": 0.06
      },
      "enabled": true
    },
    {
      "id": "model-002",
      "name": "gpt-3.5-turbo",
      "display_name": "GPT-3.5 Turbo",
      "context_window": 4096,
      "pricing": {
        "input": 0.0015,
        "output": 0.002
      },
      "enabled": true
    }
  ],
  "usage_stats": {
    "requests_total": 1250,
    "tokens_total": 625000,
    "cost_total": 62.50,
    "requests_today": 245,
    "tokens_today": 125000,
    "cost_today": 2.50,
    "requests_last_7days": 1100,
    "tokens_last_7days": 550000,
    "cost_last_7days": 55.00,
    "requests_last_30days": 1250,
    "tokens_last_30days": 625000,
    "cost_last_30days": 62.50
  },
  "error_stats": {
    "errors_today": 2,
    "errors_last_7days": 5,
    "error_rate": 0.004,
    "last_error": {
      "type": "rate_limit_exceeded",
      "message": "Rate limit exceeded",
      "timestamp": "2026-04-02T13:45:00Z"
    }
  },
  "last_tested_at": "2026-04-02T12:00:00Z",
  "test_status": "passed",
  "health_status": "healthy"
}
```

**Сценарии использования:**

#### Scenario 1: Просмотр деталей провайдера
- **WHEN** админ кликает на провайдер в таблице
- **THEN** система запрашивает `GET /admin/llm-providers/{provider_id}`
- **AND** отображает детальную страницу с конфигурацией и статистикой

---

### 7. POST /admin/llm-providers/{provider_id}/test

**Назначение:** Протестировать подключение к LLM провайдеру

**Endpoint:** `POST /admin/llm-providers/prov-001/test`

**Authentication:** Bearer Token (scope: `admin:write`, `admin:llm`)

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "model_id": "model-001",
  "test_message": "Hello, test message"
}
```

**Request Parameters:**

| Параметр | Тип | Обязательно | Описание |
|----------|-----|-----------|---------|
| `model_id` | string | ✅ | ID модели для тестирования |
| `test_message` | string | ❌ | Тестовое сообщение (default: "Hello") |

**Success Response (200 OK):**

```json
{
  "success": true,
  "provider_id": "prov-001",
  "model_id": "model-001",
  "status": "passed",
  "latency_ms": 542,
  "response": "Hello! This is a test response from OpenAI API.",
  "timestamp": "2026-04-02T14:45:00Z",
  "health_status": "healthy"
}
```

**Error Responses:**

```json
// 400 Bad Request — невалидная модель
{
  "error": "model_not_found",
  "error_description": "Model with ID model-999 not found in this provider"
}

// 503 Service Unavailable — ошибка подключения
{
  "success": false,
  "status": "failed",
  "error": "connection_error",
  "error_description": "Failed to connect to OpenAI API: Connection timeout",
  "timestamp": "2026-04-02T14:45:00Z"
}

// 401 Unauthorized — невалидный API ключ
{
  "success": false,
  "status": "failed",
  "error": "authentication_error",
  "error_description": "API key is invalid or expired",
  "timestamp": "2026-04-02T14:45:00Z"
}
```

**Сценарии использования:**

#### Scenario 1: Тестирование нового провайдера
- **WHEN** админ добавляет новый LLM провайдер
- **THEN** система показит кнопку "Test Connection"
- **AND** при клике отправляет POST `/admin/llm-providers/{provider_id}/test`
- **AND** отображает результат (успешно/ошибка с деталями)

#### Scenario 2: Проверка здоровья провайдера после сбоя
- **WHEN** провайдер показывает статус "error" в списке
- **AND** админ кликает "Re-test"
- **THEN** система отправляет POST запрос к endpoint'у
- **AND** обновляет статус провайдера

---

### 8. PATCH /admin/llm-providers/{provider_id}

**Назначение:** Обновить конфигурацию LLM провайдера

**Endpoint:** `PATCH /admin/llm-providers/prov-001`

**Authentication:** Bearer Token (scope: `admin:write`, `admin:llm`)

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "name": "OpenAI Production v2",
  "status": "active",
  "api_url": "https://api.openai.com/v1",
  "models": [
    {
      "id": "model-001",
      "enabled": true
    },
    {
      "id": "model-002",
      "enabled": false
    }
  ]
}
```

**Success Response (200 OK):**

```json
{
  "id": "prov-001",
  "name": "OpenAI Production v2",
  "status": "active",
  "updated_at": "2026-04-02T14:50:00Z",
  "changes": {
    "name": {
      "old": "OpenAI Production",
      "new": "OpenAI Production v2"
    }
  }
}
```

**Сценарии использования:**

#### Scenario 1: Отключение модели в провайдере
- **WHEN** админ открывает детали провайдера
- **AND** отключает какую-то модель
- **THEN** система отправляет PATCH с `models[].enabled: false`
- **AND** модель становится недоступной для пользователей

---

### 9. DELETE /admin/llm-providers/{provider_id}

**Назначение:** Удалить LLM провайдера (soft delete)

**Endpoint:** `DELETE /admin/llm-providers/prov-001`

**Authentication:** Bearer Token (scope: `admin:write`, `admin:llm`)

**Success Response (204 No Content):**

```
HTTP/1.1 204 No Content
```

**Error Responses:**

```json
// 409 Conflict — провайдер используется
{
  "error": "provider_in_use",
  "error_description": "Cannot delete provider: used by 12 users and 5 agents",
  "details": {
    "users_count": 12,
    "agents_count": 5
  }
}
```

**Сценарии использования:**

#### Scenario 1: Удаление неиспользуемого провайдера
- **WHEN** админ кликает "Delete" на странице провайдера
- **THEN** система показывает подтверждение
- **AND** если провайдер не используется, отправляет DELETE запрос
- **AND** провайдер удаляется из списка

#### Scenario 2: Попытка удаления активного провайдера
- **WHEN** провайдер используется другими пользователями/агентами
- **THEN** система показывает ошибку "Provider in use"
- **AND** предлагает сначала отключить его (`status: inactive`)

---

## 📊 Dashboard & Analytics API

### 10. GET /admin/dashboard/stats

**Назначение:** Получить статистику для Dashboard

**Endpoint:** `GET /admin/dashboard/stats?period=today`

**Authentication:** Bearer Token (scope: `admin:read`)

**Query Parameters:**

| Параметр | Тип | Обязательно | Описание |
|----------|-----|-----------|---------|
| `period` | enum | ❌ | `today`, `week`, `month`, `year` (default: `today`) |

**Success Response (200 OK):**

```json
{
  "timestamp": "2026-04-02T21:00:00Z",
  "period": "today",
  "users": {
    "total": 156,
    "active": 42,
    "new_today": 3,
    "suspended": 2,
    "inactive": 112
  },
  "projects": {
    "total": 89,
    "active": 45,
    "new_today": 2
  },
  "agents": {
    "total": 234,
    "active": 120,
    "new_today": 5
  },
  "llm_usage": {
    "total_requests": 1245,
    "total_tokens": 625000,
    "total_cost": 62.50,
    "by_provider": [
      {
        "provider_id": "prov-001",
        "provider_name": "OpenAI",
        "requests": 890,
        "tokens": 450000,
        "cost": 45.00
      },
      {
        "provider_id": "prov-002",
        "provider_name": "Anthropic",
        "requests": 355,
        "tokens": 175000,
        "cost": 17.50
      }
    ]
  },
  "services": {
    "overall_status": "healthy",
    "services": [
      {
        "name": "auth-service",
        "status": "healthy",
        "uptime_percent": 99.98,
        "latency_ms": 45,
        "last_check": "2026-04-02T21:00:00Z"
      },
      {
        "name": "core-service",
        "status": "healthy",
        "uptime_percent": 99.95,
        "latency_ms": 120,
        "last_check": "2026-04-02T21:00:00Z"
      }
    ]
  }
}
```

**Сценарии использования:**

#### Scenario 1: Загрузка Dashboard
- **WHEN** админ открывает Dashboard страницу
- **THEN** система запрашивает `GET /admin/dashboard/stats?period=today`
- **AND** отображает overview карточки и графики использования

---

## 📝 Audit Log API

### 11. GET /admin/audit-log

**Назначение:** Получить логи всех событий системы

**Endpoint:** `GET /admin/audit-log?type=user_action&limit=50`

**Authentication:** Bearer Token (scope: `admin:read`, `admin:audit`)

**Query Parameters:**

| Параметр | Тип | Обязательно | Описание |
|----------|-----|-----------|---------|
| `type` | enum | ❌ | Фильтр типа события |
| `actor_id` | UUID | ❌ | Фильтр по администратору |
| `resource` | string | ❌ | Фильтр по ресурсу (user, provider, etc.) |
| `action` | string | ❌ | Фильтр по действию (create, update, delete) |
| `from` | ISO 8601 | ❌ | Дата от |
| `to` | ISO 8601 | ❌ | Дата до |
| `search` | string | ❌ | Поиск в payload |
| `page` | integer | ❌ | Номер страницы |
| `limit` | integer | ❌ | Результатов на странице (max: 100) |

**Success Response (200 OK):**

```json
{
  "data": [
    {
      "id": "audit-001",
      "timestamp": "2026-04-02T14:45:00Z",
      "actor_id": "admin-001",
      "actor_email": "admin@example.com",
      "actor_ip": "192.168.1.50",
      "type": "user_action",
      "resource": "user",
      "resource_id": "550e8400-e29b-41d4-a716-446655440000",
      "action": "status_change",
      "status": "success",
      "details": {
        "old_status": "active",
        "new_status": "suspended",
        "reason": "Account activity violation"
      },
      "user_agent": "Mozilla/5.0..."
    },
    {
      "id": "audit-002",
      "timestamp": "2026-04-02T14:30:00Z",
      "actor_id": "admin-001",
      "actor_email": "admin@example.com",
      "actor_ip": "192.168.1.50",
      "type": "provider_action",
      "resource": "llm_provider",
      "resource_id": "prov-001",
      "action": "test",
      "status": "success",
      "details": {
        "model_id": "model-001",
        "latency_ms": 542,
        "test_status": "passed"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 456,
    "pages": 10
  }
}
```

**Сценарии использования:**

#### Scenario 1: Просмотр истории действий администратора
- **WHEN** админ открывает Audit Log страницу
- **THEN** система запрашивает `GET /admin/audit-log?limit=50`
- **AND** отображает таблицу с логами

#### Scenario 2: Поиск действий по пользователю
- **WHEN** админ ищет все действия с user ID: `550e8400-e29b-41d4-a716-446655440000`
- **THEN** система запрашивает `GET /admin/audit-log?resource=user&resource_id=550e8400...`
- **AND** отображает все действия над этим пользователем

---

## ⚙️ Settings/Configuration API

### 12. GET /admin/settings

**Назначение:** Получить все конфигурационные настройки

**Endpoint:** `GET /admin/settings`

**Authentication:** Bearer Token (scope: `admin:read`)

**Success Response (200 OK):**

```json
{
  "rate_limiting": {
    "login_attempts_per_minute": 5,
    "api_requests_per_minute": 100,
    "lockout_duration_minutes": 15
  },
  "approval_settings": {
    "tool_approval_timeout_seconds": 300,
    "plan_approval_timeout_seconds": 600
  },
  "email_settings": {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_from_address": "noreply@codelab.local",
    "smtp_use_tls": true
  },
  "logging": {
    "retention_days": 90,
    "log_level": "INFO",
    "include_sensitive_data": false
  }
}
```

### 13. PATCH /admin/settings

**Назначение:** Обновить конфигурационные настройки

**Endpoint:** `PATCH /admin/settings`

**Authentication:** Bearer Token (scope: `admin:write`)

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "rate_limiting": {
    "login_attempts_per_minute": 10
  }
}
```

**Success Response (200 OK):**

```json
{
  "success": true,
  "updated_fields": {
    "rate_limiting.login_attempts_per_minute": {
      "old": 5,
      "new": 10
    }
  },
  "audit_id": "audit-123456"
}
```

---

## 🔌 HTTP Status Codes

| Code | Описание | Пример |
|------|---------|--------|
| **200 OK** | Успешный GET/PATCH | User list returned |
| **201 Created** | Успешное создание | New provider created |
| **204 No Content** | Успешное удаление | Provider deleted |
| **400 Bad Request** | Невалидные параметры | Invalid email format |
| **401 Unauthorized** | Невалидный/истекший токен | Token expired |
| **403 Forbidden** | Недостаточно прав | Missing required scope |
| **404 Not Found** | Ресурс не найден | User not found |
| **409 Conflict** | Конфликт в логике | Provider in use |
| **422 Unprocessable Entity** | Невалидные данные | Invalid status value |
| **429 Too Many Requests** | Rate limit | Too many requests |
| **500 Internal Server Error** | Внутренняя ошибка | Database error |
| **503 Service Unavailable** | Сервис недоступен | Auth service down |

---

## 📋 Следующие шаги

1. ✅ Написана base API спецификация
2. ⏳ Требуется согласование с backend сервисами
3. ⏳ Требуется реализация на frontend'е
4. ⏳ Требуется написание тестов (unit + integration)
