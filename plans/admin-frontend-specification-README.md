# CodeLab Admin Frontend — Полная спецификация

**Версия:** 1.0.0  
**Статус:** ✅ Готова к разработке  
**Дата создания:** 2 апреля 2026  
**Автор:** Technical Architecture Team

---

## 📚 Содержание спецификации

Спецификация состоит из 4 документов:

### 1. [`admin-frontend-specification-project.md`](admin-frontend-specification-project.md)
**Обзор проекта и архитектура**

Содержит:
- 📋 Описание целей и задач проекта
- 🎯 Определение MVP функционала (5 модулей)
- 🔧 Технологический стек (Next.js 15, Ant Design 5, TanStack Query)
- 🏗️ Архитектурная диаграмма компонентов
- 🔐 Требования безопасности и аутентификации
- 📊 Success criteria и дорожная карта

### 2. [`admin-frontend-specification-api.md`](admin-frontend-specification-api.md)
**Полная спецификация REST API**

Содержит:
- 🔌 13 API endpoints с детальным описанием
- 📝 Request/Response примеры для каждого endpoint
- 🔑 Параметры запросов и фильтрацию
- ❌ Обработка ошибок и HTTP статус коды
- 🔍 Сценарии использования (Use Cases)
- 🔐 Требования к аутентификации (JWT, scopes)

**Покрытые модули:**
- 👥 User Management (4 endpoints)
- 🤖 LLM Providers Management (5 endpoints)
- 📊 Dashboard & Analytics (1 endpoint)
- 📝 Audit Log (1 endpoint)
- ⚙️ Settings/Configuration (2 endpoints)

### 3. [`admin-frontend-specification-data-models.md`](admin-frontend-specification-data-models.md)
**TypeScript Data Models и интерфейсы**

Содержит:
- 📦 Полный набор TypeScript интерфейсов
- 👥 User Management типы (User, UserSession, UserDetail)
- 🤖 LLM Providers типы (LLMProvider, LLMModel, ProviderError)
- 📊 Dashboard типы (DashboardStats, MetricCard)
- 📝 Audit Log типы (AuditLogEntry, SecurityEvent)
- ⚙️ Settings типы (SystemSettings, RateLimitingSettings)
- 🔄 Shared типы (PaginationInfo, ApiError, JWTPayload)
- 📚 React Query / TanStack Query типы
- 💡 Примеры использования с кодом
- ✅ Чек-лист валидации типов

---

## 🏗️ Архитектурная диаграмма

```
┌───────────────────────────────────────────────────────────────┐
│                   Admin Frontend (Next.js 15)                 │
├───────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    Pages (App Router)                   │  │
│  ├──────────────────┬──────────────────┬──────────────────┤  │
│  │ /admin/dashboard │ /admin/users     │ /admin/llm-...   │  │
│  │ 📊 Dashboard     │ 👥 User Mgmt     │ 🤖 Providers     │  │
│  ├──────────────────┼──────────────────┼──────────────────┤  │
│  │ /admin/audit-log │ /admin/settings  │ Middleware       │  │
│  │ 📝 Audit Log     │ ⚙️ Configuration │ 🔐 Auth Guards   │  │
│  └─────────────────────────────────────────────────────────┘  │
│                            ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              Reusable Components (Ant Design)           │  │
│  ├──────────────────┬──────────────────┬──────────────────┤  │
│  │ Tables           │ Forms & Dialogs  │ Charts & Cards   │  │
│  │ (User, Provider) │ (CRUD operations)│ (Cost, Usage)    │  │
│  └─────────────────────────────────────────────────────────┘  │
│                            ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │            API Client Layer (lib/api)                   │  │
│  ├──────────────────┬──────────────────┬──────────────────┤  │
│  │ UsersClient      │ ProvidersClient  │ AuditClient      │  │
│  │ (GET, PATCH)     │ (CRUD, Test)     │ (GET, Search)    │  │
│  └─────────────────────────────────────────────────────────┘  │
│                            ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         TanStack Query (Caching & Sync)                 │  │
│  │     useQuery (read), useMutation (write)                │  │
│  └─────────────────────────────────────────────────────────┘  │
│                            ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │       HTTP Client (fetch/axios) & Middleware            │  │
│  │  JWT Bearer Token, Error Handling, Request Logging      │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
          ↓                              ↓
┌─────────────────────────┐  ┌─────────────────────────┐
│ codelab-auth-service    │  │ codelab-core-service    │
│ Port 8003               │  │ Port 8001               │
├─────────────────────────┤  ├─────────────────────────┤
│ ✅ User Management      │  │ ✅ LLM Providers       │
│ ✅ Authentication       │  │ ✅ Audit Log           │
│ ✅ Sessions             │  │ ✅ Dashboard Stats     │
│ ✅ Password Reset       │  │ ✅ Security Events     │
└─────────────────────────┘  └─────────────────────────┘
```

---

## 🎯 MVP Функционал (фаза 1)

### 1. User Management 👥
- ✅ Список пользователей с поиском и фильтрацией
- ✅ Детальная страница пользователя с сессиями
- ✅ Действия: сброс пароля, блокировка, удаление
- ✅ Audit trail всех действий администратора

**API:** 4 endpoints (GET users, GET user detail, POST reset-password, PATCH status)

### 2. LLM Providers Management 🤖
- ✅ Список провайдеров со статусом и статистикой
- ✅ Детали провайдера, конфигурация моделей
- ✅ Тестирование подключения (Test Connection)
- ✅ CRUD операции (создание, редактирование, удаление)
- ✅ Статистика использования и затрат

**API:** 5 endpoints (GET providers, GET detail, POST test, PATCH update, DELETE)

### 3. Dashboard & Analytics 📊
- ✅ System Overview (активные пользователи, проекты, агенты)
- ✅ Usage Metrics (графики использования LLM)
- ✅ Cost Analytics (затраты по провайдерам)
- ✅ Service Health (latency, uptime микросервисов)

**API:** 1 endpoint (GET stats с параметром period)

### 4. Audit Log 📝
- ✅ Журнал всех действий администраторов
- ✅ Security events (попытки входа, блокировки и т.д.)
- ✅ Поиск и фильтрация по типу события, дате, пользователю
- ✅ Экспорт логов (будущее)

**API:** 1 endpoint (GET audit-log с фильтрацией)

### 5. System Settings ⚙️
- ✅ Rate Limiting конфигурация
- ✅ Email/SMTP настройки
- ✅ Логирование и retention policy
- ✅ Approval timeout конфигурация

**API:** 2 endpoints (GET settings, PATCH settings)

---

## 📊 Статистика спецификации

| Метрика | Значение |
|---------|----------|
| **API Endpoints** | 13 |
| **HTTP Methods** | 5 (GET, POST, PATCH, DELETE, HEAD) |
| **Data Models** | 40+ TypeScript интерфейсов |
| **Modules** | 5 |
| **Pages** | 5 |
| **React Components** | ~15 (таблицы, формы, карточки) |
| **API Scopes** | 6 (`admin:read`, `admin:write`, `admin:audit`, `admin:users`, `admin:llm`) |
| **Security Requirements** | 5 (Auth, RBAC, Audit, CSRF, XSS) |

---

## 🔐 Безопасность

### Аутентификация
- ✅ JWT Bearer Token (RS256)
- ✅ Refresh token автоматическое обновление
- ✅ Secure HttpOnly cookies

### Авторизация
- ✅ Role-Based Access Control (RBAC)
- ✅ Scope-based permissions
- ✅ Middleware проверка на каждом запросе

### Аудит
- ✅ Все действия администраторов логируются
- ✅ API ключи НИКОГДА не логируются
- ✅ Sensitive данные защищены

### Защита
- ✅ CSRF protection (SameSite cookies)
- ✅ XSS protection (React escaping)
- ✅ Input validation (Zod schemas)
- ✅ Rate limiting на frontend

---

## 🚀 Quick Start для разработчиков

### 1. Установка зависимостей
```bash
cd admin-frontend
npm install
```

### 2. Конфигурация окружения
```bash
cp .env.example .env.local
# Отредактировать .env.local:
NEXT_PUBLIC_AUTH_API_URL=http://localhost:8003
NEXT_PUBLIC_CORE_API_URL=http://localhost:8001
```

### 3. Запуск разработки
```bash
npm run dev
# Открыть http://localhost:3010
```

### 4. Структура проекта
```
admin-frontend/
├── app/
│   ├── (admin)/
│   │   ├── dashboard/       # 📊 Dashboard page
│   │   ├── users/           # 👥 Users management
│   │   ├── llm-providers/   # 🤖 LLM Providers
│   │   ├── audit-log/       # 📝 Audit log
│   │   ├── settings/        # ⚙️ Configuration
│   │   └── layout.tsx       # Admin shell layout
│   ├── (auth)/
│   │   └── login/           # 🔐 Login page
│   ├── middleware.ts        # Auth guards
│   └── layout.tsx           # Root layout
├── components/
│   ├── tables/              # Ant Design таблицы
│   ├── forms/               # CRUD формы
│   ├── charts/              # Графики (Cost, Usage)
│   └── admin-shell.tsx      # Layout компонент
├── lib/
│   ├── api/
│   │   ├── auth-client.ts   # Users API
│   │   ├── core-client.ts   # Providers API
│   │   └── axios.ts         # HTTP client
│   ├── types.ts             # TypeScript интерфейсы
│   ├── hooks.ts             # Custom React Query hooks
│   └── utils.ts             # Утилиты
└── public/                  # Статические файлы
```

---

## 📖 Документация по модулям

### Модуль: User Management 👥
- **Страница:** `/admin/users`
- **API:** `/admin/users`, `/admin/users/{id}`, `/admin/users/{id}/reset-password`, `/admin/users/{id}/status`
- **Компоненты:** UsersTable, UserDetail, UserActions
- **Data Models:** User, UserSession, UserDetail, GetUsersParams
- **Примеры API:** [см. admin-frontend-specification-api.md](#1-get-adminusers)

### Модуль: LLM Providers Management 🤖
- **Страница:** `/admin/llm-providers`
- **API:** `/admin/llm-providers`, `/admin/llm-providers/{id}`, `/admin/llm-providers/{id}/test`, `/admin/llm-providers/{id}` (PATCH/DELETE)
- **Компоненты:** ProvidersTable, ProviderDetail, TestConnection, ModelConfig
- **Data Models:** LLMProvider, LLMModel, ProviderError, TestProviderResponse
- **Примеры API:** [см. admin-frontend-specification-api.md](#-llm-providers-management-api)

### Модуль: Dashboard 📊
- **Страница:** `/admin/dashboard`
- **API:** `/admin/dashboard/stats`
- **Компоненты:** StatsCards, UsageChart, CostChart, ServiceHealth
- **Data Models:** DashboardStats, MetricCard, ServiceStatus
- **Примеры API:** [см. admin-frontend-specification-api.md](#10-get-admindashboardstats)

### Модуль: Audit Log 📝
- **Страница:** `/admin/audit-log`
- **API:** `/admin/audit-log`
- **Компоненты:** AuditTable, EventFilter, SecurityAlerts
- **Data Models:** AuditLogEntry, SecurityEvent, AuditAction
- **Примеры API:** [см. admin-frontend-specification-api.md](#11-get-adminaudit-log)

### Модуль: Settings ⚙️
- **Страница:** `/admin/settings`
- **API:** `/admin/settings` (GET, PATCH)
- **Компоненты:** SettingsForm, RateLimitingConfig, EmailConfig
- **Data Models:** SystemSettings, RateLimitingSettings, EmailSettings
- **Примеры API:** [см. admin-frontend-specification-api.md](#⚙️-settingsconfiguration-api)

---

## 🔗 Интеграция с микросервисами

### codelab-auth-service (Port 8003)
**Используется для:**
- Управления пользователями (list, detail, actions)
- Сброса паролей
- Управления статусом пользователей

**Endpoints:**
```
GET    /admin/users
GET    /admin/users/{user_id}
GET    /admin/users/{user_id}/sessions
POST   /admin/users/{user_id}/reset-password
PATCH  /admin/users/{user_id}/status
```

### codelab-core-service (Port 8001)
**Используется для:**
- Управления LLM провайдерами
- Статистики и аналитики
- Audit log и security events

**Endpoints:**
```
GET    /admin/llm-providers
GET    /admin/llm-providers/{provider_id}
POST   /admin/llm-providers/{provider_id}/test
PATCH  /admin/llm-providers/{provider_id}
DELETE /admin/llm-providers/{provider_id}
GET    /admin/dashboard/stats
GET    /admin/audit-log
GET    /admin/settings
PATCH  /admin/settings
```

---

## 📅 Дорожная карта

### Phase 1: MVP ✅ (текущий спринт)
- [x] Определение требований и функционала
- [x] Написание спецификации (проект, API, data models)
- [ ] Разработка frontend'а
- [ ] Разработка API в backend сервисах
- [ ] Интеграционное тестирование

### Phase 2: Enhancement 📅 (Q2 2026)
- [ ] Approvals Management (queue, bulk actions)
- [ ] Role-Based Access Control (granular roles)
- [ ] Real-time Updates (WebSocket)
- [ ] Advanced Analytics (cost forecasting)

### Phase 3: Advanced 🔮 (Q3-Q4 2026)
- [ ] Custom Reports Builder
- [ ] Integration with monitoring tools (Prometheus)
- [ ] Slack/Email notifications
- [ ] Two-Factor Authentication (2FA)

---

## ✅ Success Criteria

### Функциональные критерии
- ✅ Все 5 модулей MVP полностью функциональны
- ✅ Все 13 API endpoints реализованы
- ✅ 100% test coverage для критичных компонентов
- ✅ Документация с примерами

### Нефункциональные критерии
- ✅ Performance: Page load < 2s, API response < 500ms
- ✅ Security: все требования выполнены
- ✅ Accessibility: WCAG 2.1 AA
- ✅ Browser support: Chrome, Firefox, Safari (последние версии)

---

## 🤝 Контакты и вопросы

**Вопросы по спецификации?**
- Проверьте соответствующий документ в `/plans`
- Свяжитесь с техническим лидом для уточнений
- Создайте issue в GitHub с меткой `specification`

---

## 📝 История версий

| Версия | Дата | Описание |
|--------|------|---------|
| 1.0.0 | 02.04.2026 | Первая полная спецификация MVP |

---

## 🎓 Связанные документы

- [`codelab-auth-service/docs/TECHNICAL_SPECIFICATION.md`](../../codelab-auth-service/docs/TECHNICAL_SPECIFICATION.md) — Спецификация Auth Service
- [`codelab-core-service/openspec/specs/project.md`](../../codelab-core-service/openspec/specs/project.md) — Спецификация Core Service
- [`admin-frontend/README.md`](../README.md) — README admin-frontend проекта
- [`doc/README.md`](../../doc/README.md) — Общая документация CodeLab

---

**Спецификация готова к разработке! 🚀**
