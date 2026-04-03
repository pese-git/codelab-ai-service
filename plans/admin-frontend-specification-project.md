# Спецификация проекта: CodeLab Admin Frontend

**Версия:** 1.0.0  
**Статус:** 📋 В разработке  
**Дата создания:** 2 апреля 2026

---

## 📋 Обзор проекта

**CodeLab Admin Frontend** — это веб-приложение администратора для управления платформой CodeLab. Интерфейс предоставляет инструменты для контроля пользователей, конфигурации LLM провайдеров, мониторинга системы и аудита событий.

### 🎯 Назначение

Централизованная админ-панель для:
- ✅ Управления пользователями и их доступом
- ✅ Конфигурации и мониторинга LLM провайдеров
- ✅ Анализа использования ресурсов и стоимости
- ✅ Аудита всех действий администраторов
- ✅ Конфигурации системных параметров

### 👥 Целевая аудитория

- **System Administrators** — управление пользователями, конфигурация системы
- **DevOps/SRE** — мониторинг здоровья сервисов, анализ логов
- **Finance Team** — отслеживание затрат на LLM, статистика использования

---

## ⚡ Основные возможности (MVP)

### 1. User Management
Полное управление пользователями платформы CodeLab с использованием API сервиса `codelab-auth-service`.

| Функция | Описание | Статус |
|---------|---------|--------|
| **User List** | Таблица пользователей с поиском и фильтрацией | ✅ MVP |
| **User Details** | Детальная информация о пользователе, история логинов | ✅ MVP |
| **User Actions** | Сброс пароля, блокировка, удаление аккаунта | ✅ MVP |
| **Session Management** | Просмотр и управление активными сессиями | ✅ MVP |
| **Bulk Operations** | Массовые действия (блокировка нескольких пользователей) | ⏳ Post-MVP |

### 2. LLM Providers Management
Управление LLM провайдерами (OpenAI, Anthropic, etc.) с конфигурацией моделей и мониторингом.

| Функция | Описание | Статус |
|---------|---------|--------|
| **Providers List** | Список всех LLM провайдеров с статусом | ✅ MVP |
| **Provider Config** | Добавление/редактирование провайдера | ✅ MVP |
| **Provider Testing** | Тестирование подключения к провайдеру | ✅ MVP |
| **Usage Stats** | Статистика использования по провайдерам | ✅ MVP |
| **Model Management** | Управление моделями провайдера | ⏳ Post-MVP |

### 3. Dashboard & Analytics
Система мониторинга и аналитики состояния платформы.

| Функция | Описание | Статус |
|---------|---------|--------|
| **System Overview** | Активные пользователи, проекты, статус сервисов | ✅ MVP |
| **Usage Metrics** | Графики использования, токены, запросы | ✅ MVP |
| **Cost Analytics** | Затраты на LLM за период | ✅ MVP |
| **Health Status** | Latency и uptime микросервисов | ✅ MVP |

### 4. Audit Log
Журнал всех действий пользователей и системы.

| Функция | Описание | Статус |
|---------|---------|--------|
| **Event Logging** | Логирование всех действий администраторов | ✅ MVP |
| **Event Search** | Поиск и фильтрация событий | ✅ MVP |
| **Audit Trail** | История изменений объектов | ✅ MVP |
| **Security Events** | Специальный раздел security-related событий | ✅ MVP |

### 5. System Configuration
Управление настройками системы.

| Функция | Описание | Статус |
|---------|---------|--------|
| **Rate Limiting** | Конфигурация лимитов на запросы | ✅ MVP |
| **Email Settings** | SMTP конфигурация для уведомлений | ✅ MVP |
| **Logging Policy** | Параметры логирования и ретеншена | ✅ MVP |
| **Feature Flags** | Управление feature flags (если используются) | ⏳ Post-MVP |

---

## 🔧 Технологический стек

### Frontend

| Компонент | Выбор | Обоснование |
|-----------|-------|-------------|
| **Framework** | Next.js 15 | SSR, ISR, API routes, middleware |
| **UI Library** | Ant Design 5 | Rich component library, admin-friendly |
| **State Management** | TanStack React Query 5 | Data fetching, caching, sync |
| **Validation** | Zod | Type-safe validation, TypeScript |
| **Language** | TypeScript 5.9 | Type safety, developer experience |

### Backend Integration

| Компонент | Сервис | Базовый URL |
|-----------|--------|-------------|
| **Auth API** | codelab-auth-service | `http://auth-service:8003` |
| **Core API** | codelab-core-service | `http://core-service:8001` |
| **Real-time Events** | SSE/WebSocket | TBD |

---

## 📊 Архитектура компонентов

```
┌─────────────────────────────────────────────────┐
│         Admin Frontend (Next.js 15)             │
├─────────────────────────────────────────────────┤
│  Pages (Server + Client)                        │
│  ├── /admin/dashboard          (Overview)       │
│  ├── /admin/users              (User Mgmt)      │
│  ├── /admin/llm-providers      (LLM Config)     │
│  ├── /admin/audit-log          (Audit)          │
│  └── /admin/settings           (Config)         │
├─────────────────────────────────────────────────┤
│  Components (Reusable UI)                       │
│  ├── Tables (Ant Design)                        │
│  ├── Forms & Dialogs                            │
│  ├── Charts (Cost, Usage)                       │
│  └── Admin Shell (Layout)                       │
├─────────────────────────────────────────────────┤
│  API Client Layer                               │
│  ├── /lib/api/auth-client.ts   (Users, Auth)   │
│  ├── /lib/api/core-client.ts   (LLM, Audit)    │
│  └── /lib/types.ts              (TypeScript)   │
├─────────────────────────────────────────────────┤
│  Middleware & Auth                              │
│  ├── middleware.ts    (JWT validation)          │
│  └── Auth guards      (Role-based)              │
└─────────────────────────────────────────────────┘
         ↓                      ↓
  ┌─────────────────┐  ┌──────────────────┐
  │  codelab-auth   │  │  codelab-core    │
  │    service      │  │     service      │
  │   (Port 8003)   │  │   (Port 8001)    │
  └─────────────────┘  └──────────────────┘
```

---

## 🔐 Безопасность

### Требования безопасности

1. **Authentication**
   - JWT Bearer Token (RS256) из codelab-auth-service
   - Refresh token автоматическое обновление
   - Secure HttpOnly cookies для токенов

2. **Authorization**
   - Role-Based Access Control (RBAC)
   - Роли: `system_admin`, `audit_viewer`, `user_manager`, `llm_manager`
   - Middleware проверка прав доступа на каждом запросе

3. **Audit & Compliance**
   - Все действия администраторов логируются с timestamp, user_id, IP
   - API ключи НИКОГДА не логируются и не отправляются в браузер
   - Sensitive данные (пароли) не отображаются в UI

4. **Protection**
   - CSRF protection (SameSite cookies)
   - XSS protection (React escaping, CSP headers)
   - Rate limiting на frontend (debounce, request batching)
   - Input validation (Zod schemas)

---

## 📋 API Требования

### От codelab-auth-service

**Admin User Management Endpoints:**
- `GET /admin/users` — список всех пользователей
- `GET /admin/users/{user_id}` — детали пользователя
- `GET /admin/users/{user_id}/sessions` — активные сессии
- `POST /admin/users/{user_id}/reset-password` — сброс пароля
- `PATCH /admin/users/{user_id}/status` — изменение статуса
- `DELETE /admin/users/{user_id}` — soft delete пользователя

### От codelab-core-service

**Admin LLM Providers Endpoints:**
- `GET /admin/llm-providers` — список провайдеров
- `GET /admin/llm-providers/{provider_id}` — детали
- `POST /admin/llm-providers` — создать
- `PATCH /admin/llm-providers/{provider_id}` — обновить
- `POST /admin/llm-providers/{provider_id}/test` — тестировать
- `DELETE /admin/llm-providers/{provider_id}` — удалить
- `GET /admin/llm-providers/{provider_id}/usage` — статистика

**Admin Audit Endpoints:**
- `GET /admin/audit-log` — логи событий с фильтрацией
- `GET /admin/events/security` — security события
- `GET /admin/dashboard/stats` — статистика системы
- `GET /admin/health/services` — статус сервисов

---

## 🎯 Success Criteria

### Функциональные критерии
- ✅ Все 5 модулей MVP полностью функциональны
- ✅ API контракты согласованы с обоими сервисами
- ✅ Все сценарии протестированы (unit + integration)
- ✅ Документация с примерами использования

### Нефункциональные критерии
- ✅ Performance: Page load < 2s, API response < 500ms
- ✅ Security: все требования безопасности выполнены
- ✅ Accessibility: WCAG 2.1 AA compliance
- ✅ Browser support: Chrome, Firefox, Safari последних версий

---

## 📅 Дорожная карта

### Phase 1: MVP (текущий спринт)
- User Management (list, details, actions)
- LLM Providers (CRUD, testing, stats)
- Dashboard (overview, metrics)
- Audit Log (basic logging, search)
- Settings (rate limiting, email)

### Phase 2: Enhancement (Post-MVP)
- Approvals Management (queue, bulk actions)
- Role-Based Access Control (granular roles)
- Real-time Updates (WebSocket для approvals)
- Advanced Analytics (cost forecasting)
- Bulk Operations (массовые действия)

### Phase 3: Advanced (Future)
- Custom Reports Builder
- Integration with monitoring tools (Prometheus, Grafana)
- Slack/Email notifications
- Two-Factor Authentication (2FA)

---

## 📝 Следующие шаги

1. ✅ Согласование требований (DONE)
2. ⏳ Написание API спецификации (api.md)
3. ⏳ Написание data models (data-models.md)
4. ⏳ Уточнение API контрактов с backend сервисами
5. ⏳ Разработка и тестирование
