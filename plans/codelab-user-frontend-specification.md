# Спецификация модуля codelab-user-frontend

## 1. Обзор проекта

**Назначение:** Пользовательский веб-интерфейс для платформы CodeLab, обеспечивающий взаимодействие с сервисами аутентификации (`codelab-auth-service`) и основным API (`codelab-core-service`).

**Стек технологий:**
- Next.js 15 + React 19 + TypeScript
- Ant Design 5 (UI компоненты)
- TanStack React Query (state management, кэширование)
- Zod (валидация API ответов)
- CSS модули (стилизация)

**Порты и окружение:**
```
NEXT_PUBLIC_CORE_API_URL=http://localhost:8000
NEXT_PUBLIC_AUTH_API_URL=http://localhost:8003/api/v1
PORT=3020
```

---

## 2. Архитектура и структура проекта

### 2.1 Структура директорий

```
codelab-user-frontend/
├── app/                          # Next.js App Router
│   ├── (auth)/                   # Группа маршрутов аутентификации (без layout)
│   │   ├── login/
│   │   ├── register/
│   │   ├── password-reset/
│   │   └── confirm-email/
│   ├── app/                      # Приватные маршруты (защищены middleware)
│   │   ├── layout.tsx            # Layout с навигацией (UserShell)
│   │   ├── page.tsx              # Редирект на /app/projects
│   │   ├── projects/
│   │   ├── projects/[id]/        # Детали проекта
│   │   ├── projects/[id]/chat/   # Чат проекта
│   │   ├── agents/
│   │   ├── agents/[id]/          # Детали агента
│   │   ├── approvals/
│   │   ├── llm-providers/
│   │   ├── llm-providers/[id]/   # Детали провайдера
│   │   └── profile/
│   ├── layout.tsx                # Root layout
│   ├── page.tsx                  # Главная страница (редирект)
│   └── globals.css
├── components/
│   ├── user-shell.tsx            # Главный layout с навигацией
│   ├── auth/
│   │   ├── login-form.tsx
│   │   ├── register-form.tsx
│   │   └── password-reset-form.tsx
│   ├── projects/
│   │   ├── project-list.tsx
│   │   ├── project-card.tsx
│   │   ├── create-project-form.tsx
│   │   └── project-detail.tsx
│   ├── agents/
│   │   ├── agent-list.tsx
│   │   ├── agent-card.tsx
│   │   ├── create-agent-form.tsx
│   │   └── agent-detail.tsx
│   ├── chat/
│   │   ├── chat-window.tsx
│   │   ├── message-list.tsx
│   │   ├── message-input.tsx
│   │   └── chat-session-selector.tsx
│   ├── approvals/
│   │   ├── approval-list.tsx
│   │   ├── approval-card.tsx
│   │   └── approval-detail.tsx
│   ├── llm-providers/
│   │   ├── provider-list.tsx
│   │   ├── provider-card.tsx
│   │   ├── create-provider-form.tsx
│   │   └── provider-config-editor.tsx
│   ├── common/
│   │   ├── loading-spinner.tsx
│   │   ├── error-boundary.tsx
│   │   ├── toast-notification.tsx
│   │   └── modal-dialog.tsx
│   └── profile/
│       ├── user-info.tsx
│       ├── session-manager.tsx
│       └── account-settings.tsx
├── lib/
│   ├── api/
│   │   ├── auth.ts               # API клиент для auth-service
│   │   ├── core.ts               # API клиент для core-service
│   │   ├── projects.ts
│   │   ├── agents.ts
│   │   ├── chat.ts
│   │   ├── approvals.ts
│   │   ├── llm-providers.ts
│   │   └── utils.ts              # Утилиты для API (retry, error handling)
│   ├── hooks/
│   │   ├── use-auth.ts           # Hook для управления аутентификацией
│   │   ├── use-projects.ts
│   │   ├── use-agents.ts
│   │   ├── use-chat.ts
│   │   ├── use-approvals.ts
│   │   ├── use-llm-providers.ts
│   │   └── use-token-refresh.ts
│   ├── types.ts                  # TypeScript типы для API ответов
│   ├── validators.ts             # Zod схемы валидации
│   ├── auth-utils.ts             # Утилиты для работы с токенами и cookies
│   ├── constants.ts
│   └── storage.ts                # Работа с localStorage/sessionStorage
├── middleware.ts                 # Next.js middleware для защиты маршрутов
├── middleware.config.ts          # Конфиг для middleware (protected routes)
├── next.config.mjs
├── tsconfig.json
├── package.json
└── .env.example
```

### 2.2 Layer архитектура

```
UI Components (React)
      ↓
Hooks (use-projects, use-chat, etc.)
      ↓
React Query (useQuery, useMutation)
      ↓
API Clients (api/core.ts, api/auth.ts)
      ↓
HTTP Client (fetch with interceptors)
      ↓
Auth Service & Core Service
```

---

## 3. Страницы и функционал

### 3.1 Аутентификация

#### `/login` - Вход
**Описание:** Форма аутентификации с использованием Password Grant flow
**Функионал:**
- Форма с полями: email, пароль
- Кнопка "Вход"
- Ссылка на регистрацию
- Ссылка "Забыли пароль?"
- Сохранение user_token в secure HttpOnly cookie
- Автоматический редирект на `/app/projects` при успешном входе

**API вызовы:**
```
POST /api/v1/token
Content-Type: application/x-www-form-urlencoded
grant_type=password&username=email@example.com&password=password
→ TokenResponse { access_token, refresh_token, expires_in, token_type }
```

**Валидация:**
- Email валидность (Zod)
- Пароль не пуст
- HTTP 401 → "Неверные учетные данные"
- HTTP 429 → "Слишком много попыток входа"
- Network error → "Ошибка подключения"

---

#### `/register` - Регистрация
**Описание:** Форма регистрации нового пользователя
**Функионал:**
- Форма с полями: email, пароль, подтверждение пароля
- Проверка требований пароля (сложность)
- Кнопка "Зарегистрироваться"
- Ссылка на вход
- Сообщение об отправке письма подтверждения
- Редирект на экран подтверждения или автоматический вход

**API вызовы:**
```
POST /api/v1/register
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
→ { user_id, email, email_confirmed }

GET /api/v1/confirm-email?token=...
→ { email_confirmed: true }
```

**Валидация:**
- Email валидность и уникальность
- Пароль содержит буквы, цифры, спецсимволы, минимум 8 символов
- Пароли совпадают
- HTTP 400 → "Email уже зарегистрирован"
- HTTP 422 → "Пароль не соответствует требованиям"

---

#### `/password-reset` - Восстановление пароля
**Описание:** Двухшаговый процесс восстановления пароля
**Функионал:**
- Шаг 1: Форма с email → отправка ссылки восстановления
- Шаг 2: Форма с новым паролем (по ссылке из письма)
- Сообщение об отправке письма
- Редирект на login после успеха

**API вызовы:**
```
POST /api/v1/auth/password-reset/request
{ "email": "user@example.com" }
→ { message: "Email отправлен" }

POST /api/v1/auth/password-reset/confirm
{ "token": "...", "password": "NewPassword123!" }
→ { message: "Пароль изменен" }
```

---

#### `/confirm-email` - Подтверждение email
**Описание:** Страница подтверждения email при регистрации
**Функионал:**
- Показ статуса подтверждения
- Кнопка переотправления письма
- Редирект на login при успехе

---

### 3.2 Проекты

#### `/app/projects` - Список проектов
**Описание:** Главная страница со списком всех проектов пользователя
**Функионал:**
- Список проектов в виде карточек или таблицы
- Для каждого проекта: название, workspace_path, дата создания, статус
- Кнопка "Новый проект"
- Форма создания проекта (modal или inline)
- Поиск/фильтрация по названию
- Сортировка (дата, название)
- Пагинация (если > 20 проектов)
- Действия: Открыть, Редактировать, Удалить

**API вызовы:**
```
GET /projects?skip=0&limit=20&search=...
→ ProjectListResponse { items: Project[], total: int }

POST /projects
{ "name": "My Project", "workspace_path": "/path/to/workspace" }
→ ProjectResponse { id, name, workspace_path, created_at, ... }

PUT /projects/{project_id}
{ "name": "Updated Name" }
→ ProjectResponse

DELETE /projects/{project_id}
→ 204 No Content
```

**Компоненты:**
- `ProjectList` - контейнер со списком
- `ProjectCard` - карточка проекта
- `CreateProjectForm` - форма создания
- `ProjectFilters` - фильтры и поиск

---

#### `/app/projects/[id]` - Детали проекта
**Описание:** Страница управления конкретным проектом
**Функионал:**
- Информация о проекте (название, path, статистика)
- Переключатель между секциями: Агенты, Чат, Утверждения
- Редактирование названия/path
- Удаление проекта (с подтверждением)
- Экспорт конфигурации проекта

**API вызовы:**
```
GET /projects/{project_id}
→ ProjectResponse { id, name, workspace_path, agents_count, ... }

GET /projects/{project_id}/analytics
→ { total_messages, total_agents, active_sessions, ... }
```

---

#### `/app/projects/[id]/chat` - Чат проекта
**Описание:** Интерактивный чат с агентами проекта (Real-time streaming)
**Функионал:**
- Список сессий чата слева (sidebar)
- Область сообщений в центре
- Input для отправки сообщений
- Поддержка @agent_name упоминаний
- Real-time SSE streaming для ответов
- История сообщений
- Создание новой сессии
- Удаление сессии
- Экспорт диалога

**API вызовы:**
```
POST /projects/{project_id}/chat/sessions
{ "title": "Session name" }
→ ChatSessionResponse { id, title, created_at, ... }

GET /projects/{project_id}/chat/sessions
→ ChatSessionListResponse { items: ChatSession[] }

GET /projects/{project_id}/chat/sessions/{session_id}/messages
→ MessageListResponse { items: Message[] }

POST /projects/{project_id}/chat/{session_id}/message
{ "text": "Hello @agent_name", "agent_name": "agent_name" }
→ MessageResponse (с SSE streaming)

DELETE /projects/{project_id}/chat/sessions/{session_id}
→ 204 No Content

GET /projects/{project_id}/events?session_id={session_id}
→ Server-Sent Events (NDJSON формат)
```

**Компоненты:**
- `ChatWindow` - основной контейнер
- `ChatSessionSelector` - список сессий
- `MessageList` - область с сообщениями
- `MessageInput` - input с @mention поддержкой
- `StreamingMessage` - сообщение с real-time streaming

**State Management (React Query):**
```typescript
// Сессии
const sessionsQuery = useQuery(['chat-sessions', projectId])
const createSessionMutation = useMutation(createSession)
const deleteSessionMutation = useMutation(deleteSession)

// Сообщения
const messagesQuery = useQuery(['messages', sessionId])
const sendMessageMutation = useMutation(sendMessage) // с SSE подпиской
```

---

### 3.3 Агенты

#### `/app/agents` - Список агентов (опционально на projects page)
**Описание:** Список агентов всех проектов или в текущем проекте
**Функионал:**
- Список агентов по проектам
- Для каждого: название, роль, статус, количество задач
- Кнопка "Новый агент"
- Поиск и фильтрация
- Действия: Открыть, Редактировать, Удалить

**API вызовы:**
```
GET /projects/{project_id}/agents?skip=0&limit=20
→ AgentListResponse { items: Agent[] }

POST /projects/{project_id}/agents
{
  "name": "Agent Name",
  "role": "assistant",
  "description": "...",
  "config": { "temperature": 0.7, ... }
}
→ AgentResponse

PUT /projects/{project_id}/agents/{agent_id}
→ AgentResponse

DELETE /projects/{project_id}/agents/{agent_id}
→ 204 No Content
```

---

#### `/app/agents/[id]` - Детали агента
**Описание:** Управление конкретным агентом
**Функионал:**
- Информация об агенте
- Редактирование конфигурации (role, temperature, tools, context)
- Просмотр истории взаимодействий
- Удаление агента

**API вызовы:**
```
GET /projects/{project_id}/agents/{agent_id}
→ AgentResponse { id, name, role, config, ... }

PATCH /projects/{project_id}/agents/{agent_id}
{ "config": { "temperature": 0.5 } }
→ AgentResponse
```

---

### 3.4 Утверждения

#### `/app/approvals` - Список утверждений
**Описание:** Список требующих подтверждения действий (опасные tools, высокорисковые операции)
**Функионал:**
- Список pending утверждений
- Для каждого: описание, тип, дата создания, статус
- Фильтры по статусу (pending, approved, rejected)
- Действия: Просмотр деталей, Подтверждение, Отклонение
- История завершенных утверждений

**API вызовы:**
```
GET /approvals?status=pending&skip=0&limit=20
→ ApprovalListResponse { items: Approval[] }

GET /approvals/{approval_id}
→ ApprovalResponse {
    id, description, type, payload,
    status, created_at, expires_at
  }

POST /approvals/{approval_id}/confirm
{ "notes": "Approved" }
→ ApprovalResponse { status: "approved" }

POST /approvals/{approval_id}/reject
{ "reason": "Security concern" }
→ ApprovalResponse { status: "rejected" }
```

**Компоненты:**
- `ApprovalList` - контейнер со списком
- `ApprovalCard` - карточка утверждения
- `ApprovalDetail` - детали с кнопками approve/reject

---

### 3.5 LLM Провайдеры

#### `/app/llm-providers` - Список провайдеров
**Описание:** Управление LLM провайдерами (OpenAI, Claude, Gemini и т.д.)
**Функионал:**
- Список доступных провайдеров
- Для каждого: название, тип, статус подключения
- Кнопка "Добавить провайдер"
- Поиск по названию
- Действия: Открыть, Редактировать, Тестировать, Удалить
- Отображение лимитов и использования

**API вызовы:**
```
GET /llm-providers/available
→ LLMProviderListResponse { items: LLMProviderType[] }

GET /llm-providers
→ LLMProviderListResponse { items: UserLLMProvider[] }

POST /llm-providers
{
  "name": "My OpenAI",
  "provider_type": "openai",
  "config": { "api_key": "sk-..." }
}
→ LLMProviderResponse

PUT /llm-providers/{provider_id}
→ LLMProviderResponse

POST /llm-providers/{provider_id}/test
{ "model": "gpt-4", "prompt": "Hello" }
→ LLMProviderTestResponse { success: true, response: "..." }

DELETE /llm-providers/{provider_id}
→ 204 No Content

GET /llm-providers/audit
→ LLMProviderAuditLogListResponse
```

---

#### `/app/llm-providers/[id]` - Детали провайдера
**Описание:** Управление конфигурацией провайдера
**Функионал:**
- Редактирование конфигурации (API keys, параметры)
- Просмотр доступных моделей
- Тестирование подключения
- История использования и логирование
- Удаление провайдера

---

### 3.6 Профиль

#### `/app/profile` - Профиль пользователя
**Описание:** Управление профилем и сессиями
**Функионал:**
- Информация пользователя (email, дата регистрации, последний вход)
- Управление сессиями (список всех активных сессий)
- Кнопка "Выход" (logout)
- Кнопка "Выход со всех устройств"
- Изменение пароля
- Удаление аккаунта (с подтверждением)
- Настройки UI (тема, язык)

**API вызовы:**
```
GET /auth/sessions
→ SessionListResponse { items: Session[] }

GET /auth/sessions/{session_id}
→ SessionResponse { id, user_agent, created_at, last_used_at }

DELETE /auth/sessions/{session_id}
→ 204 No Content (logout)

POST /auth/logout
→ 200 OK (logout текущей сессии)

POST /auth/delete-account
{ "password": "..." }
→ 200 OK
```

---

## 4. State Management и Data Flow

### 4.1 React Query Setup

```typescript
// lib/query-client.ts
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 минут
      gcTime: 10 * 60 * 1000,   // 10 минут
      retry: 2,
      retryDelay: exponentialDelay,
    },
    mutations: {
      retry: 1,
    },
  },
});
```

### 4.2 Custom Hooks для State

```typescript
// lib/hooks/use-projects.ts
export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => fetchProjects(),
    enabled: !!getAuthToken(),
  });
}

export function useCreateProject() {
  return useMutation({
    mutationFn: (data: ProjectCreate) => createProject(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

// lib/hooks/use-chat.ts
export function useChatMessages(sessionId: string) {
  return useQuery({
    queryKey: ['messages', sessionId],
    queryFn: () => fetchMessages(sessionId),
  });
}

export function useSendMessage() {
  return useMutation({
    mutationFn: (data: MessageInput) => sendMessage(data),
    onSuccess: () => {
      // Invalidate только текущую сессию
      queryClient.invalidateQueries({ 
        queryKey: ['messages', sessionId] 
      });
    },
  });
}
```

### 4.3 Auth Context

```typescript
// lib/hooks/use-auth.ts
interface AuthContext {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
}

export function useAuth() {
  // Использует React Query для управления состоянием
  // Проверяет наличие токена в cookie
}
```

### 4.4 SSE Real-time Updates для Chat

```typescript
// lib/hooks/use-sse-events.ts
export function useSSEEvents(projectId: string, sessionId: string) {
  useEffect(() => {
    const eventSource = new EventSource(
      `/api/projects/${projectId}/events?session_id=${sessionId}`
    );
    
    eventSource.addEventListener('message', (event) => {
      const data = JSON.parse(event.data);
      // Обновляем локальное состояние сообщения
      updateStreamingMessage(data);
    });
    
    return () => eventSource.close();
  }, [projectId, sessionId]);
}
```

---

## 5. API Client Implementation

### 5.1 HTTP Interceptors и Error Handling

```typescript
// lib/api/utils.ts
class APIClient {
  private baseURL: string;
  
  async request<T>(
    endpoint: string,
    options: RequestInit
  ): Promise<T> {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAuthToken()}`,
          ...options.headers,
        },
        credentials: 'include', // Для HttpOnly cookies
      });
      
      if (response.status === 401) {
        // Token expired, попробуем refresh
        await refreshToken();
        return this.request<T>(endpoint, options);
      }
      
      if (!response.ok) {
        throw new APIError(response.status, await response.json());
      }
      
      return response.json();
    } catch (error) {
      handleAPIError(error);
      throw error;
    }
  }
}
```

### 5.2 API Clients для каждого модуля

```typescript
// lib/api/auth.ts
export async function login(email: string, password: string) {
  const formData = new FormData();
  formData.append('grant_type', 'password');
  formData.append('username', email);
  formData.append('password', password);
  
  return apiClient.request<TokenResponse>('/token', {
    method: 'POST',
    body: formData,
  });
}

// lib/api/projects.ts
export async function getProjects(skip = 0, limit = 20) {
  return apiClient.request<ProjectListResponse>(
    `/projects?skip=${skip}&limit=${limit}`,
    { method: 'GET' }
  );
}

// lib/api/chat.ts
export async function sendMessage(
  projectId: string,
  sessionId: string,
  text: string
) {
  return apiClient.request<MessageResponse>(
    `/projects/${projectId}/chat/${sessionId}/message`,
    {
      method: 'POST',
      body: JSON.stringify({ text }),
    }
  );
}
```

---

## 6. Валидация и Типизация

### 6.1 Zod Schemas для валидации

```typescript
// lib/validators.ts
export const ProjectSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(100),
  workspace_path: z.string().min(1),
  created_at: z.string().datetime(),
});

export const ProjectCreateSchema = z.object({
  name: z.string().min(1, 'Название обязательно').max(100),
  workspace_path: z.string().min(1, 'Путь обязателен'),
});

export const LoginSchema = z.object({
  email: z.string().email('Неверный email'),
  password: z.string().min(8, 'Минимум 8 символов'),
});

export const MessageSchema = z.object({
  id: z.string().uuid(),
  text: z.string(),
  role: z.enum(['user', 'assistant']),
  agent_name: z.string().optional(),
  created_at: z.string().datetime(),
});
```

### 6.2 TypeScript Types

```typescript
// lib/types.ts
export interface User {
  id: string;
  email: string;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  user_id: string;
  name: string;
  workspace_path: string;
  created_at: string;
  updated_at: string;
}

export interface ChatSession {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
}

export interface Message {
  id: string;
  session_id: string;
  text: string;
  role: 'user' | 'assistant';
  agent_name?: string;
  created_at: string;
}

export interface Agent {
  id: string;
  project_id: string;
  name: string;
  role: string;
  description?: string;
  config: Record<string, any>;
  created_at: string;
}

export interface Approval {
  id: string;
  user_id: string;
  description: string;
  type: string;
  payload: Record<string, any>;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  expires_at: string;
}

export interface LLMProvider {
  id: string;
  user_id: string;
  name: string;
  provider_type: string;
  config: Record<string, any>;
  status: 'active' | 'inactive' | 'error';
  created_at: string;
}
```

---

## 7. Обработка ошибок и Error Handling

### 7.1 Custom Error Classes

```typescript
// lib/api/errors.ts
export class APIError extends Error {
  constructor(
    public status: number,
    public data: Record<string, any>,
    message?: string
  ) {
    super(message || data.detail || 'API Error');
    this.name = 'APIError';
  }
}

export class NetworkError extends Error {
  constructor(message = 'Network connection error') {
    super(message);
    this.name = 'NetworkError';
  }
}

export class ValidationError extends Error {
  constructor(
    public errors: Record<string, string[]>
  ) {
    super('Validation failed');
    this.name = 'ValidationError';
  }
}
```

### 7.2 Error Boundaries и UI обработка

```typescript
// components/common/error-boundary.tsx
export class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null };
  
  static getDerivedStateFromError(error: any) {
    return { hasError: true, error };
  }
  
  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />;
    }
    return this.props.children;
  }
}

// components/common/error-fallback.tsx
export function ErrorFallback({ error }: { error: Error }) {
  return (
    <div className="error-container">
      <h2>Что-то пошло не так</h2>
      <p>{error.message}</p>
      <button onClick={() => window.location.reload()}>
        Перезагрузить страницу
      </button>
    </div>
  );
}
```

### 7.3 Toast Notifications для ошибок

```typescript
// lib/api/utils.ts
function handleAPIError(error: any) {
  if (error instanceof APIError) {
    switch (error.status) {
      case 400:
        showToast('Неверный запрос', 'error');
        break;
      case 401:
        showToast('Сессия истекла', 'warning');
        // Редирект на login
        break;
      case 403:
        showToast('Нет доступа', 'error');
        break;
      case 404:
        showToast('Ресурс не найден', 'error');
        break;
      case 409:
        showToast('Конфликт данных', 'warning');
        break;
      case 422:
        showToast('Ошибка валидации', 'error');
        break;
      case 429:
        showToast('Слишком много запросов. Попробуйте позже', 'warning');
        break;
      case 500:
        showToast('Ошибка сервера', 'error');
        break;
      default:
        showToast('Ошибка: ' + error.message, 'error');
    }
  } else if (error instanceof NetworkError) {
    showToast('Проблема с подключением', 'error');
  }
}
```

---

## 8. Middleware и маршрутизация

### 8.1 Next.js Middleware

```typescript
// middleware.ts
export function middleware(request: NextRequest) {
  const token = request.cookies.get('user_token')?.value;
  const pathname = request.nextUrl.pathname;
  
  // Защита приватных маршрутов
  if (pathname.startsWith('/app') && !token) {
    return NextResponse.redirect(new URL('/login', request.url));
  }
  
  // Редирект авторизованных с /login на /app/projects
  if ((pathname === '/login' || pathname === '/register') && token) {
    return NextResponse.redirect(new URL('/app/projects', request.url));
  }
  
  return NextResponse.next();
}

export const config = {
  matcher: ['/app/:path*', '/login', '/register'],
};
```

### 8.2 Protected Route Wrapper

```typescript
// lib/components/protected-route.tsx
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) {
    return <LoadingSpinner />;
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }
  
  return <>{children}</>;
}
```

---

## 9. Token Management и Refresh Flow

### 9.1 Token Refresh Hook

```typescript
// lib/hooks/use-token-refresh.ts
export function useTokenRefresh() {
  const { token, setToken } = useAuth();
  
  useEffect(() => {
    if (!token) return;
    
    // Декодируем токен и получаем время истечения
    const payload = jwtDecode(token);
    const expiresAt = (payload.exp || 0) * 1000;
    const now = Date.now();
    const timeUntilExpiry = expiresAt - now;
    
    // Рефрешим за 1 минуту до истечения
    const timeout = setTimeout(() => {
      refreshToken()
        .then(newToken => setToken(newToken))
        .catch(() => {
          // Редирект на login
          window.location.href = '/login';
        });
    }, timeUntilExpiry - 60000);
    
    return () => clearTimeout(timeout);
  }, [token]);
}
```

### 9.2 API Interceptor для автоматического refresh

```typescript
// lib/api/utils.ts
async function refreshToken(): Promise<string> {
  const response = await fetch(`${AUTH_API_URL}/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'grant_type=refresh_token&refresh_token=' + getRefreshToken(),
    credentials: 'include',
  });
  
  if (!response.ok) {
    // Очистить cookies и редирект на login
    clearAuthTokens();
    window.location.href = '/login';
    throw new Error('Token refresh failed');
  }
  
  const data = await response.json();
  setAuthToken(data.access_token, data.refresh_token);
  return data.access_token;
}
```

---

## 10. Компоненты UI

### 10.1 Основные компоненты

#### UserShell (Layout)
```typescript
// components/user-shell.tsx
export function UserShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  
  return (
    <Layout>
      <Sider theme="dark">
        <div className="logo">CodeLab</div>
        <Menu
          theme="dark"
          selectedKeys={[pathname]}
          items={[
            { key: '/app/projects', label: 'Проекты', icon: <ProjectIcon /> },
            { key: '/app/agents', label: 'Агенты', icon: <AgentIcon /> },
            { key: '/app/approvals', label: 'Утверждения', icon: <ApprovalIcon /> },
            { key: '/app/llm-providers', label: 'LLM', icon: <LLMIcon /> },
            { key: '/app/profile', label: 'Профиль', icon: <ProfileIcon /> },
          ]}
          onClick={(e) => router.push(e.key)}
        />
      </Sider>
      <Layout>
        <Header>
          <div className="header-content">
            <Breadcrumb items={getBreadcrumbs(pathname)} />
            <div className="header-actions">
              <NotificationBell />
              <Avatar onClick={() => router.push('/app/profile')} />
            </div>
          </div>
        </Header>
        <Content>{children}</Content>
      </Layout>
    </Layout>
  );
}
```

#### ProjectCard
```typescript
// components/projects/project-card.tsx
export function ProjectCard({ project, onDelete }: ProjectCardProps) {
  return (
    <Card
      title={project.name}
      extra={
        <Dropdown menu={{ items: getActions(onDelete) }}>
          <MoreOutlined />
        </Dropdown>
      }
    >
      <p>Путь: {project.workspace_path}</p>
      <p>Создан: {formatDate(project.created_at)}</p>
      <Button type="primary" onClick={() => navigate(`/app/projects/${project.id}`)}>
        Открыть
      </Button>
    </Card>
  );
}
```

#### ChatWindow
```typescript
// components/chat/chat-window.tsx
export function ChatWindow({ projectId }: ChatWindowProps) {
  const [sessionId, setSessionId] = useState<string>();
  const { data: sessions } = useChatSessions(projectId);
  const { data: messages } = useChatMessages(projectId, sessionId!);
  const { mutate: sendMessage } = useSendMessage();
  
  return (
    <div className="chat-container">
      <ChatSessionSelector
        sessions={sessions}
        activeId={sessionId}
        onSelect={setSessionId}
      />
      <div className="chat-area">
        <MessageList messages={messages} />
        <MessageInput
          onSend={(text) => sendMessage({ projectId, sessionId, text })}
        />
      </div>
    </div>
  );
}
```

### 10.2 Common компоненты

#### LoadingSpinner
```typescript
export function LoadingSpinner() {
  return <Spin size="large" fullscreen />;
}
```

#### Toast Notification
```typescript
// lib/notifications.ts
export function showToast(message: string, type: 'success' | 'error' | 'warning' | 'info') {
  notification[type]({
    message,
    duration: 3,
  });
}
```

#### Modal Dialog
```typescript
export function ConfirmDialog({ title, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <Modal
      title={title}
      okText="Подтвердить"
      cancelText="Отмена"
      onOk={onConfirm}
      onCancel={onCancel}
    >
      {/* Контент */}
    </Modal>
  );
}
```

---

## 11. Performance и Optimization

### 11.1 Code Splitting

```typescript
// lib/lazy-components.ts
import dynamic from 'next/dynamic';

export const ChatWindow = dynamic(() => import('@/components/chat/chat-window'), {
  loading: () => <LoadingSpinner />,
  ssr: false,
});

export const AgentDetail = dynamic(() => import('@/components/agents/agent-detail'), {
  loading: () => <LoadingSpinner />,
  ssr: false,
});
```

### 11.2 Image Optimization

```typescript
// Использование next/image для оптимизации
import Image from 'next/image';

<Image
  src={avatarUrl}
  alt="User avatar"
  width={40}
  height={40}
  priority
/>
```

### 11.3 Memoization

```typescript
// components/projects/project-card.tsx
export const ProjectCard = React.memo(function ProjectCard({ project }: Props) {
  // ...
});
```

---

## 12. Testing Strategy

### 12.1 Unit Tests (Jest + React Testing Library)

```typescript
// components/__tests__/login-form.test.tsx
describe('LoginForm', () => {
  it('submits form with email and password', async () => {
    const { getByLabelText, getByRole } = render(<LoginForm />);
    
    await userEvent.type(getByLabelText(/email/i), 'test@example.com');
    await userEvent.type(getByLabelText(/password/i), 'password123');
    await userEvent.click(getByRole('button', { name: /login/i }));
    
    // Assert API call
  });
});
```

### 12.2 Integration Tests (Cypress/Playwright)

```typescript
// e2e/login.spec.ts
describe('Login Flow', () => {
  it('should login and redirect to projects', () => {
    cy.visit('/login');
    cy.get('[data-testid="email-input"]').type('test@example.com');
    cy.get('[data-testid="password-input"]').type('password123');
    cy.get('[data-testid="login-button"]').click();
    cy.url().should('include', '/app/projects');
  });
});
```

---

## 13. Deployment и Build

### 13.1 Docker

```dockerfile
# Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3020
CMD ["npm", "start"]
```

### 13.2 Build Configuration

```javascript
// next.config.mjs
export default {
  reactStrictMode: true,
  swcMinify: true,
  images: {
    unoptimized: false,
  },
  env: {
    NEXT_PUBLIC_CORE_API_URL: process.env.NEXT_PUBLIC_CORE_API_URL,
    NEXT_PUBLIC_AUTH_API_URL: process.env.NEXT_PUBLIC_AUTH_API_URL,
  },
};
```

---

## 14. Security

### 14.1 CSRF Protection
- Использование Next.js встроенной поддержки через cookies
- Все POST/PUT/DELETE запросы используют fetch с `credentials: 'include'`

### 14.2 XSS Protection
- Все текстовые значения автоматически экранируются React
- DOMPurify для пользовательского контента (если необходимо)

### 14.3 Token Security
- Хранение в HttpOnly cookies (не в localStorage)
- Automatic refresh за 1 минуту до истечения
- Очистка при logout

### 14.4 Rate Limiting
- На фронте: debounce/throttle для частых операций
- На беке: встроенная защита от brute-force (auth-service)

---

## 15. Мониторинг и Логирование

### 15.1 Error Tracking (Sentry)

```typescript
// lib/sentry.ts
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 1.0,
});
```

### 15.2 Analytics (Posthog / Mixpanel)

```typescript
// lib/analytics.ts
export function trackEvent(name: string, properties: Record<string, any>) {
  if (typeof window !== 'undefined' && window.posthog) {
    window.posthog.capture(name, properties);
  }
}

// Использование
trackEvent('project_created', { projectName: 'My Project' });
```

---

## 16. Roadmap реализации

### Phase 1: Core (Weeks 1-2)
- [x] Базовая структура Next.js проекта
- [ ] Login/Register/Password Reset с auth-service
- [ ] Middleware для защиты маршрутов
- [ ] Projects page (CRUD)
- [ ] Profile page

### Phase 2: Advanced (Weeks 3-4)
- [ ] Agents management (CRUD)
- [ ] LLM Providers (CRUD)
- [ ] Approvals list и actions

### Phase 3: Real-time (Weeks 5-6)
- [ ] Chat с SSE streaming
- [ ] Real-time message updates
- [ ] Session management

### Phase 4: Polish (Week 7+)
- [ ] Full error handling и validation
- [ ] Performance optimization
- [ ] Testing (unit + e2e)
- [ ] Security audit
- [ ] Documentation

---

## 17. Dependencies

```json
{
  "dependencies": {
    "next": "^15.5.6",
    "react": "^19.1.1",
    "react-dom": "^19.1.1",
    "@tanstack/react-query": "^5.90.2",
    "antd": "^5.27.0",
    "zod": "^4.1.11",
    "jwt-decode": "^4.0.0",
    "clsx": "^2.0.0"
  },
  "devDependencies": {
    "typescript": "^5.9.3",
    "@types/react": "^19.1.13",
    "@testing-library/react": "^16.0.0",
    "cypress": "^14.0.0"
  }
}
```

---

## Заключение

Эта спецификация определяет полную архитектуру пользовательского фронтенда для CodeLab, интегрирующегося с auth-service и core-service. Модуль обеспечивает:

✅ Полную аутентификацию и управление сессиями  
✅ CRUD операции для проектов, агентов, провайдеров  
✅ Real-time чат с SSE streaming  
✅ Систему утверждений для критических операций  
✅ Современный UX с Ant Design  
✅ Надежную обработку ошибок и валидацию  
✅ Оптимизацию производительности  
✅ Security best practices
