# Диаграммы архитектуры codelab-user-frontend (Mermaid)

## 1. High-Level Data Flow

```mermaid
graph TD
    UI["React Components<br/>UI Layer"]
    Hooks["Custom Hooks<br/>Business Logic"]
    Query["React Query<br/>State Management"]
    API["API Clients<br/>HTTP Layer"]
    Auth["Auth Service<br/>port 8003"]
    Core["Core Service<br/>port 8000"]
    Redis["Redis/Cache<br/>SSE Events"]
    
    UI -->|useState, useContext| Hooks
    Hooks -->|useQuery, useMutation| Query
    Query -->|fetch| API
    API -->|POST /token<br/>GET /sessions| Auth
    API -->|GET /projects<br/>POST /chat| Core
    Core -->|Subscribe SSE| Redis
    
    style UI fill:#e1f5ff
    style Hooks fill:#f3e5f5
    style Query fill:#fce4ec
    style API fill:#fff3e0
    style Auth fill:#e8f5e9
    style Core fill:#e8f5e9
    style Redis fill:#fbe9e7
```

---

## 2. Component Tree Architecture

```mermaid
graph TD
    Root["RootLayout<br/>app/layout.tsx"]
    Auth["Auth Group<br/>app/auth/"]
    App["App Group<br/>app/app/ Protected"]
    Public["Public Pages"]
    
    Root -->|Public Routes| Auth
    Root -->|Protected Routes| App
    Root -->|Fallback| Public
    
    Auth -->|/login| Login["LoginPage"]
    Auth -->|/register| Register["RegisterPage"]
    Auth -->|/password-reset| Reset["PasswordResetPage"]
    Auth -->|/confirm-email| Confirm["ConfirmEmailPage"]
    
    App -->|Layout| Shell["UserShell<br/>Navigation + Sidebar"]
    Shell -->|/projects| Projects["ProjectsPage"]
    Shell -->|/projects/:id| ProjectDetail["ProjectDetailPage"]
    Shell -->|/projects/:id/chat| ChatPage["ChatPage"]
    Shell -->|/agents| AgentsPage["AgentsPage"]
    Shell -->|/agents/:id| AgentDetail["AgentDetailPage"]
    Shell -->|/approvals| ApprovalsPage["ApprovalsPage"]
    Shell -->|/llm-providers| ProvidersPage["ProvidersPage"]
    Shell -->|/llm-providers/:id| ProviderDetail["ProviderDetailPage"]
    Shell -->|/profile| ProfilePage["ProfilePage"]
    
    Public -->|/| HomePage["HomePage<br/>Redirect Logic"]
    Public -->|/404| NotFound["NotFoundPage"]
    
    style Root fill:#b3e5fc
    style Auth fill:#c8e6c9
    style App fill:#c8e6c9
    style Shell fill:#fff9c4
    style Projects fill:#f8bbd0
    style ChatPage fill:#f8bbd0
    style ProfilePage fill:#f8bbd0
```

---

## 3. Projects Page Component Tree

```mermaid
graph TD
    Page["ProjectsPage<br/>useProjects, useState"]
    Filters["ProjectFilters<br/>Search, Sort"]
    List["ProjectList<br/>map projects"]
    Modal["CreateProjectModal"]
    
    Page -->|projects, loading| List
    Page -->|onChange| Filters
    List --> Card1["ProjectCard #1"]
    List --> Card2["ProjectCard #2"]
    List --> CardN["ProjectCard N"]
    
    Card1 -->|Title, Meta| CardContent["Card Content"]
    Card1 -->|Actions| Dropdown["ActionDropdown<br/>Edit, Delete, Open"]
    
    Page -->|onClick| Modal
    Modal --> Form["CreateProjectForm<br/>Name, Path"]
    Form --> Submit["SubmitButton"]
    
    style Page fill:#ffccbc
    style Filters fill:#c8e6c9
    style List fill:#bbdefb
    style Card1 fill:#ffe0b2
    style Modal fill:#f0f4c3
```

---

## 4. Chat Page Component Tree

```mermaid
graph TD
    Page["ChatPage<br/>useChat, useState"]
    Window["ChatWindow"]
    Sidebar["ChatSessionSelector<br/>Left Sidebar"]
    Area["ChatArea<br/>Main Chat"]
    
    Page -->|sessions, activeId| Sidebar
    Page -->|messages, projectId| Area
    
    Sidebar -->|Create| NewSession["CreateSessionBtn"]
    Sidebar -->|List| SessionList["SessionList"]
    SessionList --> Item1["SessionItem #1"]
    SessionList --> Item2["SessionItem #2"]
    Sidebar -->|Delete| DeleteBtn["DeleteSessionBtn"]
    
    Area -->|Messages| MsgList["MessageList<br/>Scroll Area"]
    MsgList --> Msg1["MessageItem #1<br/>User Message"]
    MsgList --> Msg2["MessageItem #2<br/>Assistant Response"]
    MsgList --> Streaming["StreamingMessage<br/>Real-time Content"]
    
    Area -->|Input| Input["MessageInput<br/>@mentions support"]
    Input -->|Send| SendBtn["SendButton"]
    
    style Page fill:#ffccbc
    style Window fill:#c8e6c9
    style Sidebar fill:#ffe0b2
    style Area fill:#f0f4c3
    style Streaming fill:#ffccbc
    style Input fill:#c5cae9
```

---

## 5. State Management with React Query

```mermaid
graph TD
    Hook["useProjects Hook"]
    Query["useQuery"]
    Cache["QueryCache"]
    Fn["queryFn: fetchProjects"]
    
    Hook -->|Create| Query
    Query -->|Check| Cache
    Cache -->|Hit?| CacheHit["Return Cached<br/>Data"]
    Cache -->|Miss| Execute["Execute queryFn"]
    
    Execute -->|Fetch| API["GET /projects"]
    API -->|Response| Validate["Zod Validation"]
    Validate -->|Valid| Save["Save to Cache"]
    Validate -->|Invalid| Error["ValidationError"]
    
    Save -->|Notify| Subscribers["Update Components"]
    Subscribers -->|Re-render| Component["Display Data"]
    
    Cache -->|5 min| Stale["Mark as Stale"]
    Stale -->|Background| RefreshBG["Background Refetch"]
    RefreshBG -->|Update| Save
    
    style Hook fill:#e1bee7
    style Query fill:#bbdefb
    style Cache fill:#ffccbc
    style API fill:#c8e6c9
    style Validate fill:#fff9c4
    style Component fill:#f8bbd0
```

---

## 6. Authentication Flow (Login)

```mermaid
sequenceDiagram
    actor User
    participant LoginForm as LoginPage
    participant API as API Client
    participant AuthSvc as Auth Service
    participant DB as Database
    participant Cookie as HttpOnly Cookie
    participant Dashboard as /app/projects
    
    User->>LoginForm: Enter email & password
    LoginForm->>LoginForm: Validate input
    LoginForm->>API: POST /token
    API->>AuthSvc: (email, password)
    AuthSvc->>DB: Query user
    DB-->>AuthSvc: User record
    AuthSvc->>AuthSvc: Verify password
    AuthSvc->>AuthSvc: Generate JWT tokens
    AuthSvc-->>API: TokenResponse
    API-->>LoginForm: {access_token, refresh_token}
    LoginForm->>Cookie: Set user_token
    LoginForm-->>User: Redirect
    User->>Dashboard: Navigate to /app/projects
```

---

## 7. Token Refresh Auto-Flow

```mermaid
graph TD
    Root["RootLayout"]
    Hook["useTokenRefresh Hook"]
    Decode["Decode JWT Token"]
    CalcTime["Calculate Time Until<br/>Expiry - 60s"]
    Timer["setTimeout"]
    
    Root -->|Mount| Hook
    Hook -->|Get token| Decode
    Decode -->|exp claim| CalcTime
    CalcTime -->|Schedule| Timer
    
    Timer -->|After calculated time| Refresh["Call refreshToken()"]
    Refresh -->|POST /token| AuthAPI["Auth Service"]
    AuthAPI -->|200 OK| NewToken["Get new access_token"]
    NewToken -->|Update| Cookie["HttpOnly Cookie"]
    Cookie -->|Schedule next| Timer
    
    Refresh -->|Error| ClearAuth["Clear Auth"]
    ClearAuth -->|Redirect| Login["Redirect /login"]
    
    style Hook fill:#fff9c4
    style Refresh fill:#ffccbc
    style Cookie fill:#c8e6c9
    style Login fill:#ffcdd2
```

---

## 8. Chat SSE Real-time Flow

```mermaid
sequenceDiagram
    actor User
    participant Input as MessageInput
    participant Cache as React Query<br/>Cache
    participant API as API Client
    participant CoreSvc as Core Service
    participant SSE as SSE Stream
    participant UI as MessageList
    
    User->>Input: Type message
    Input->>Input: Validate @mentions
    User->>Input: Click Send
    
    Input->>Cache: Optimistic Update<br/>(Add user message)
    Input->>API: POST /chat/{id}/message
    API->>CoreSvc: {text, agent_name}
    CoreSvc->>Cache: Return MessageResponse
    Cache->>UI: Update with ID
    
    API->>SSE: Subscribe EventSource
    CoreSvc-->>SSE: event: message_started
    SSE->>UI: Show loading indicator
    
    CoreSvc-->>SSE: event: message_streaming
    CoreSvc-->>SSE: data: {chunk}
    SSE->>UI: Append chunk to message
    
    CoreSvc-->>SSE: event: message_streaming
    CoreSvc-->>SSE: data: {chunk}
    SSE->>UI: Append chunk
    
    CoreSvc-->>SSE: event: message_completed
    SSE->>UI: Final message
    SSE->>Cache: Invalidate messages
    Cache->>UI: Refetch new message
```

---

## 9. Error Handling Flow

```mermaid
graph TD
    Request["API Request"]
    Response{Response<br/>Status}
    
    Request -->|Success| Success["200-299"]
    Success -->|Parse| Data["Return Data"]
    Data -->|Validate| Zod["Zod Schema"]
    Zod -->|Valid| Component["Update Component"]
    Zod -->|Invalid| ValError["ValidationError"]
    
    Request -->|Error| Error["4xx/5xx"]
    
    Error -->|401| Unauthorized["Unauthorized"]
    Unauthorized -->|Try Refresh| Refresh["refreshToken()"]
    Refresh -->|Success| Retry["Retry Request"]
    Refresh -->|Failure| ClearAuth["Clear Auth + Login"]
    
    Error -->|400, 422| BadReq["Bad Request"]
    BadReq -->|Show Toast| ShowErr["showToast(error)"]
    
    Error -->|403| Forbidden["Forbidden"]
    Forbidden -->|Show Toast| ShowErr
    
    Error -->|404| NotFound["Not Found"]
    NotFound -->|Show Toast| ShowErr
    
    Error -->|429| RateLimit["Rate Limited"]
    RateLimit -->|Exponential Backoff| RetryExp["Retry with Delay"]
    
    Error -->|500+| Server["Server Error"]
    Server -->|Log Sentry| LogError["Log to Sentry"]
    LogError -->|Show Toast| ShowErr
    
    Error -->|Network| NetError["Network Error"]
    NetError -->|Show Toast| ShowErr
    
    ShowErr -->|Toast Notification| User["User Sees Message"]
    ValError -->|Toast| User
    
    style Component fill:#c8e6c9
    style ClearAuth fill:#ffcdd2
    style ShowErr fill:#fff3e0
    style LogError fill:#ffccbc
```

---

## 10. Middleware Route Protection

```mermaid
graph TD
    Request["Incoming Request"]
    Path{Check<br/>Pathname}
    
    Path -->|/login<br/>/register| AuthRoute["Auth Route"]
    Path -->|/app/*| ProtectedRoute["Protected Route"]
    Path -->|Other| PublicRoute["Public Route"]
    
    AuthRoute -->|Has token?| HasToken{Token<br/>Valid?}
    HasToken -->|Yes| Redirect1["Redirect /app/projects"]
    HasToken -->|No| Allow1["Allow Access"]
    
    ProtectedRoute -->|Has token?| HasToken2{Token<br/>Valid?}
    HasToken2 -->|Yes| Allow2["Allow Access"]
    HasToken2 -->|No| Redirect2["Redirect /login"]
    
    PublicRoute -->|Always| Allow3["Allow Access"]
    
    Redirect1 -->|Next Response| Browser["Browser"]
    Redirect2 -->|Next Response| Browser
    Allow1 -->|Next Response| Browser
    Allow2 -->|Next Response| Browser
    Allow3 -->|Next Response| Browser
    
    style ProtectedRoute fill:#ffccbc
    style AuthRoute fill:#c8e6c9
    style Redirect2 fill:#ffcdd2
    style Allow2 fill:#c8e6c9
```

---

## 11. API Integration Map

```mermaid
graph LR
    Frontend["codelab-user-frontend<br/>port 3020"]
    
    AuthSvc["codelab-auth-service<br/>port 8003"]
    CoreSvc["codelab-core-service<br/>port 8000"]
    
    AuthAPI["Auth API"]
    CoreAPI["Core API"]
    
    Frontend -->|lib/api/auth.ts| AuthAPI
    Frontend -->|lib/api/core.ts| CoreAPI
    
    AuthAPI -->|POST /token| AuthSvc
    AuthAPI -->|POST /register| AuthSvc
    AuthAPI -->|POST /logout| AuthSvc
    AuthAPI -->|GET /sessions| AuthSvc
    AuthAPI -->|DELETE /sessions| AuthSvc
    AuthAPI -->|GET /.well-known/jwks| AuthSvc
    
    CoreAPI -->|GET/POST /projects| CoreSvc
    CoreAPI -->|GET/POST /chat/sessions| CoreSvc
    CoreAPI -->|POST /chat/message| CoreSvc
    CoreAPI -->|GET /events SSE| CoreSvc
    CoreAPI -->|GET/POST /agents| CoreSvc
    CoreAPI -->|GET /approvals| CoreSvc
    CoreAPI -->|GET/POST /llm-providers| CoreSvc
    
    style Frontend fill:#bbdefb
    style AuthSvc fill:#c8e6c9
    style CoreSvc fill:#c8e6c9
    style AuthAPI fill:#fff9c4
    style CoreAPI fill:#fff9c4
```

---

## 12. Build & Deployment Pipeline

```mermaid
graph TD
    Source["TypeScript + JSX<br/>Source Code"]
    Build["npm run build"]
    Dist[".next folder<br/>Compiled & Optimized"]
    
    Build -->|TSC| TypeScript["TypeScript Compilation"]
    Build -->|SWC| JSX["JSX Transpilation"]
    Build -->|Split| CodeSplit["Code Splitting"]
    Build -->|Minify| Mini["Minification"]
    
    TypeScript --> Dist
    JSX --> Dist
    CodeSplit --> Dist
    Mini --> Dist
    
    Dist -->|Docker| Builder["Stage 1: Builder<br/>node:20-alpine"]
    Builder -->|Copy| Runtime["Stage 2: Runtime<br/>node:20-alpine"]
    
    Runtime -->|npm start| Server["Node Server<br/>port 3020"]
    
    Server -->|env vars| Env["NEXT_PUBLIC_CORE_API_URL<br/>NEXT_PUBLIC_AUTH_API_URL"]
    
    Env -->|Ready| Deploy["Deployment<br/>Docker/K8s"]
    
    style Source fill:#bbdefb
    style Build fill:#fff9c4
    style Dist fill:#f0f4c3
    style Runtime fill:#c8e6c9
    style Server fill:#f8bbd0
    style Deploy fill:#ffe0b2
```

---

## 13. Performance Optimization Strategy

```mermaid
graph TD
    App["Application"]
    
    App -->|Code Splitting| Split["Dynamic Imports<br/>ChatWindow, AgentDetail<br/>LLMProviderConfig"]
    
    App -->|Caching| Cache["Browser Cache"]
    Cache -->|Static| Static["Assets: 1 year"]
    Cache -->|JS| JS["Bundles: hash-based"]
    Cache -->|Images| Images["Images: 30 days"]
    
    App -->|State Cache| RQ["React Query"]
    RQ -->|Queries| QCache["staleTime: 5 min<br/>gcTime: 10 min"]
    RQ -->|Auto Refetch| BG["Background Refetch"]
    
    App -->|Images| OptImg["next/image"]
    OptImg -->|Responsive| Resp["Auto Sizing"]
    OptImg -->|Format| Format["WebP Conversion"]
    OptImg -->|Lazy| Lazy["Lazy Loading"]
    
    App -->|Memoization| Memo["React.memo"]
    Memo -->|Components| CompMemo["ProjectCard<br/>MessageItem<br/>AgentCard"]
    
    App -->|Metrics| Perf["Performance Targets"]
    Perf -->|FCP| FCP["First Contentful Paint: &lt;1.5s"]
    Perf -->|LCP| LCP["Largest Contentful Paint: &lt;2.5s"]
    Perf -->|CLS| CLS["Cumulative Layout Shift: &lt;0.1"]
    Perf -->|Bundle| Bundle["Total gzipped: &lt;200KB"]
    
    style Split fill:#c8e6c9
    style Cache fill:#fff9c4
    style RQ fill:#f0f4c3
    style OptImg fill:#ffe0b2
    style Memo fill:#f8bbd0
    style Perf fill:#bbdefb
```

---

## 14. Approval Request Flow

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant ApprovalMgr as Approval Manager<br/>Core Service
    participant DB as Database
    participant UI as ApprovalsPage
    
    Agent->>ApprovalMgr: Dangerous operation<br/>Execute tool
    ApprovalMgr->>DB: Create approval request<br/>status: pending
    ApprovalMgr-->>Agent: Hold execution
    
    DB-->>UI: New approval available
    UI->>UI: Show notification
    User->>UI: View pending approvals
    UI->>DB: GET /approvals?status=pending
    
    User->>UI: Review & Approve
    UI->>UI: Show confirmation dialog
    User->>UI: Confirm
    
    UI->>ApprovalMgr: POST /approvals/{id}/confirm
    ApprovalMgr->>DB: Update status: approved
    ApprovalMgr->>Agent: Resume execution
    Agent->>Agent: Execute tool
    Agent-->>User: Result
    
    UI->>DB: Refetch approvals
    UI->>User: Remove from pending list
```

---

## 15. Data Types & Validation

```mermaid
graph TD
    API["API Response<br/>JSON"]
    Zod["Zod Schema"]
    Type["TypeScript Type"]
    Component["Component Usage"]
    
    API -->|Parse| Zod
    Zod -->|Valid| Type
    Zod -->|Invalid| Error["ValidationError<br/>Toast notification"]
    
    Type -->|Typed| Props["Component Props"]
    Props -->|useQuery| Hook["Hook Return"]
    Hook -->|Type Safe| Component
    
    Zod -->|Examples| Schemas["ProjectSchema<br/>MessageSchema<br/>ApprovalSchema<br/>AgentSchema<br/>LLMProviderSchema"]
    
    style Zod fill:#fff9c4
    style Type fill:#bbdefb
    style Component fill:#c8e6c9
    style Error fill:#ffcdd2
    style Schemas fill:#f0f4c3
```

---

## 16. Full Login to Projects Page Sequence

```mermaid
sequenceDiagram
    actor User
    participant Browser as Browser
    participant Frontend as Next.js Frontend<br/>port 3020
    participant Middleware as middleware.ts
    participant LoginPage as LoginPage
    participant API as API Client
    participant AuthSvc as Auth Service<br/>port 8003
    participant DB as Database
    participant ProjectsPage as ProjectsPage
    
    User->>Browser: Visit http://localhost:3020
    Browser->>Frontend: GET /
    Frontend->>Middleware: Check cookie
    Middleware->>Middleware: No token found
    Middleware-->>Browser: Redirect /login
    
    Browser->>Frontend: GET /login
    Frontend-->>Browser: HTML + LoginForm
    
    User->>LoginPage: Enter email & password
    LoginPage->>LoginPage: Validate form
    LoginPage->>API: POST /token
    API->>AuthSvc: {grant_type, username, password}
    AuthSvc->>DB: Get user by email
    DB-->>AuthSvc: User found
    AuthSvc->>AuthSvc: bcrypt verify password
    AuthSvc->>AuthSvc: Create JWT tokens
    AuthSvc-->>API: TokenResponse
    API-->>LoginPage: {access_token, refresh_token}
    
    LoginPage->>Browser: Set HttpOnly cookie: user_token
    LoginPage->>Browser: Redirect /app/projects
    
    Browser->>Frontend: GET /app/projects
    Frontend->>Middleware: Check cookie
    Middleware->>Middleware: Token found ✓
    Middleware-->>Browser: Allow
    
    Frontend-->>Browser: ProjectsPage HTML
    Browser->>ProjectsPage: Mount component
    ProjectsPage->>API: GET /projects
    API->>AuthSvc: Validate JWT (get JWKS)
    AuthSvc-->>API: Public keys
    API->>AuthSvc: Extract user_id from JWT
    API->>Frontend: Return projects
    ProjectsPage->>ProjectsPage: Render projects list
    ProjectsPage-->>User: Show projects
    
    User->>User: Logged in! 🎉
```

---

## 17. Chat Message Lifecycle

```mermaid
graph TD
    User["User Types<br/>Message"]
    Input["MessageInput<br/>Component"]
    Validate["Validate Text"]
    Mentions["Parse @mentions<br/>Extract agents"]
    
    User -->|Input| Input
    Input -->|onChange| Validate
    Validate -->|Valid| Mentions
    Mentions -->|List agents| Autocomplete["Show Autocomplete"]
    
    User -->|Click Send| Send["sendMessage()"]
    Send -->|optimistic| OptUpdate["Add to MessageList<br/>with ID: 'temp'"]
    OptUpdate -->|UI Update| ShowLocal["User sees message"]
    
    Send -->|POST| APICall["API Call<br/>POST /chat/{id}/message"]
    APICall -->|Response| MsgResponse["MessageResponse<br/>ID assigned"]
    
    MsgResponse -->|Update cache| ReplaceTemp["Replace 'temp'<br/>with real ID"]
    
    Send -->|SSE Subscribe| SSE["EventSource<br/>GET /events"]
    SSE -->|message_started| StreamStart["Show loading<br/>indicator"]
    SSE -->|message_streaming| Chunk["Receive chunk<br/>Append to message"]
    SSE -->|message_streaming| Chunk
    SSE -->|message_completed| Done["Mark complete<br/>Remove indicator"]
    
    Done -->|Refetch| InvalidateCache["Invalidate messages<br/>cache"]
    InvalidateCache -->|Final| ComponentUpdate["Component shows<br/>final message"]
    
    style User fill:#bbdefb
    style Input fill:#fff9c4
    style Send fill:#f0f4c3
    style SSE fill:#ffccbc
    style ComponentUpdate fill:#c8e6c9
```

---

## 18. Project CRUD Operations

```mermaid
graph TD
    ProjectsPage["ProjectsPage"]
    
    ProjectsPage -->|useProjects| GetAll["GET /projects<br/>Fetch all projects"]
    ProjectsPage -->|useCreateProject| Create["POST /projects<br/>Create new"]
    
    GetAll -->|Response| List["Display ProjectList"]
    List -->|Each Card| Card["ProjectCard<br/>Name, Path, Date"]
    
    Card -->|Click Edit| Edit["Edit Form"]
    Edit -->|Save| Update["PUT /projects/{id}<br/>Update"]
    Update -->|Invalidate| Refetch1["Refetch projects"]
    
    Card -->|Click Delete| ConfirmDel["Confirm Dialog"]
    ConfirmDel -->|Confirm| Delete["DELETE /projects/{id}"]
    Delete -->|Invalidate| Refetch2["Refetch projects"]
    
    Card -->|Click Open| Navigate["Navigate<br/>/projects/{id}"]
    Navigate -->|Load| Detail["ProjectDetailPage"]
    
    Create -->|Form Submit| NewProj["Create mutation<br/>POST /projects"]
    NewProj -->|Success| Success["Toast: Success<br/>Clear form"]
    Success -->|Invalidate| Refetch3["Refetch projects"]
    NewProj -->|Error| ErrorToast["Toast: Error<br/>Show message"]
    
    Refetch1 -->|Done| List
    Refetch2 -->|Done| List
    Refetch3 -->|Done| List
    
    style GetAll fill:#bbdefb
    style Create fill:#fff9c4
    style Update fill:#f0f4c3
    style Delete fill:#ffcdd2
    style List fill:#c8e6c9
```

---

## Резюме диаграмм

Все диаграммы покрывают:

✅ **Data Flow** - высокоуровневый поток данных  
✅ **Component Architecture** - иерархия компонентов  
✅ **State Management** - React Query  
✅ **Authentication** - Login flow и auto-refresh  
✅ **Real-time Updates** - SSE streaming для чата  
✅ **Error Handling** - стратегия обработки ошибок  
├─ Retry on 429 (Rate limit) ✓
├─ Retry on 500+ (Server error) ✓
├─ Retry on network error ✓
├─ Don't retry on 400-499 (Client errors) ✗
└─ Don't retry on 401 unless token refresh succeeded ✗
```

---

## 8. Component Props Flow диаграмма

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    PROJECTS PAGE - PROPS FLOW                            │
└──────────────────────────────────────────────────────────────────────────┘

ProjectsPage
     │
     ├─ useProjects() → { data, isLoading, error }
     ├─ useCreateProject() → { mutate, isPending }
     ├─ useState(filters, searchQuery)
     │
     ├─ Pass down:
     │  │
     │  ├─> ProjectFilters
     │  │   ├─ filters: FilterState
     │  │   ├─ onFilterChange: (filters) => void
     │  │   └─ onSearch: (query) => void
     │  │
     │  └─> ProjectList
     │      ├─ projects: Project[]
     │      ├─ isLoading: boolean
     │      ├─ error?: Error
     │      ├─ onProjectDeleted: (id) => void
     │      │
     │      └─> ProjectCard (map)
     │          ├─ project: Project
     │          ├─ onDelete: () => void
     │          ├─ onEdit: () => void
     │          ├─ onOpen: () => void
     │          │
     │          └─> ActionDropdown
     │              ├─ items: MenuItem[]
     │              ├─ onClick: (action) => void

┌──────────────────────────────────────────────────────────────────────────┐
│                    CHAT PAGE - PROPS FLOW                                │
└──────────────────────────────────────────────────────────────────────────┘

ChatPage
     │
     ├─ useChat(projectId) → { sessions, messages, sendMessage }
     ├─ useState(activeSessionId)
     │
     ├─ Pass down:
     │  │
     │  ├─> ChatWindow
     │  │   ├─ projectId: string
     │  │   ├─ sessions: ChatSession[]
     │  │   │
     │  │   ├─> ChatSessionSelector
     │  │   │   ├─ sessions: ChatSession[]
     │  │   │   ├─ activeId: string
     │  │   │   ├─ onSelect: (id) => void
     │  │   │   ├─ onCreate: () => void
     │  │   │   └─ onDelete: (id) => void
     │  │   │
     │  │   └─> ChatArea
     │  │       ├─ messages: Message[]
     │  │       ├─ isLoading: boolean
     │  │       │
     │  │       ├─> MessageList
     │  │       │   ├─ messages: Message[]
     │  │       │   ├─ streaming: StreamingMessage
     │  │       │   │
     │  │       │   └─> MessageItem (map)
     │  │       │       ├─ message: Message
     │  │       │       ├─ isStreaming: boolean
     │  │       │       ├─ avatar: string
     │  │       │       └─ timestamp: Date
     │  │       │
     │  │       └─> MessageInput
     │  │           ├─ agents: Agent[] (for @mentions)
     │  │           ├─ disabled: boolean
     │  │           ├─ onSend: (text) => void
     │  │           └─ onMention: (agent) => void
```

---

## 9. Middleware Protection Flow диаграмма

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    NEXT.JS MIDDLEWARE FLOW                               │
└──────────────────────────────────────────────────────────────────────────┘

Request comes in
     │
     ▼
middleware.ts
     │
     ├─ Get cookies (user_token)
     ├─ Get pathname
     │
     ├─ Check if public route
     │  ├─ /login, /register, /password-reset, /confirm-email
     │  │  ├─ Has token?
     │  │  │  ├─ Yes → Redirect to /app/projects
     │  │  │  └─ No → Allow
     │  │  
     │  └─ Continue to next middleware
     │
     ├─ Check if protected route (/app/...)
     │  ├─ Has token?
     │  │  ├─ Yes → Allow
     │  │  └─ No → Redirect to /login
     │
     └─ Continue to route handler

┌──────────────────────────────────────────────────────────────────────────┐
│                   PROTECTED ROUTE WRAPPER                                │
└──────────────────────────────────────────────────────────────────────────┘

ProtectedRoute Component
     │
     ├─ useAuth() → { isAuthenticated, isLoading }
     │
     ├─ isLoading?
     │  ├─ Yes → <LoadingSpinner />
     │  │
     │  └─ No
     │     ├─ isAuthenticated?
     │     │  ├─ Yes → <>{children}</>
     │     │  └─ No → <Navigate to="/login" />
     │
     └─ Allow children rendering

Usage:
<ProtectedRoute>
  <ProjectsPage />
</ProtectedRoute>
```

---

## 10. Token Lifecycle диаграмма

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      TOKEN LIFECYCLE TIMELINE                            │
└──────────────────────────────────────────────────────────────────────────┘

Time: 0s - User login
     │
     ├─ POST /token (Password Grant)
     ├─ Receive: access_token (exp: 1800s = 30 min)
     ├─ Receive: refresh_token
     ├─ Store in HttpOnly cookie
     └─ Schedule refresh at 1740s (29 min)

Time: 1740s (29 min later)
     │
     ├─ useTokenRefresh hook fires
     ├─ POST /token (Refresh Grant)
     ├─ Receive new access_token
     ├─ Update cookie
     └─ Schedule next refresh

Time: ∞ (ongoing)
     │
     ├─ Every 30 min: auto-refresh happens
     ├─ No user action needed
     ├─ Seamless background refresh
     └─ Token always fresh

User makes request at any time:
     │
     ├─ If within 30 min window
     │  ├─ Token valid ✓
     │  └─ Request succeeds
     │
     └─ If at refresh boundary
        ├─ Refresh happens automatically
        ├─ Request uses new token
        └─ Request succeeds

If refresh fails (network error):
     │
     ├─ Keep using current token
     ├─ Retry refresh at next interval
     └─ If request fails with 401 → Manual login required

User logout:
     │
     ├─ POST /logout
     ├─ Clear cookies
     ├─ Stop refresh timer
     ├─ Redirect to /login
     └─ TokenRefresh hook cleanup
```

---

## 11. Build & Deploy Flow диаграмма

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    BUILD & DEPLOYMENT FLOW                               │
└──────────────────────────────────────────────────────────────────────────┘

Source Code (TypeScript + JSX)
     │
     ├─ npm run build
     │
     ├─ Next.js Compiler
     │  ├─ Parse TypeScript
     │  ├─ JSX transpilation
     │  ├─ Code splitting
     │  ├─ Minification
     │  └─ Tree shaking
     │
     ├─ Output: .next folder
     │  ├─ .next/server (SSR code)
     │  ├─ .next/static (CSR bundles)
     │  └─ .next/cache (optimizations)
     │
     ▼
Docker Build
     │
     ├─ Stage 1: Builder
     │  ├─ FROM node:20-alpine
     │  ├─ npm ci
     │  ├─ npm run build
     │  └─ Output: .next folder
     │
     ├─ Stage 2: Runtime
     │  ├─ FROM node:20-alpine
     │  ├─ Copy .next folder
     │  ├─ Copy package.json
     │  ├─ npm ci --omit=dev
     │  └─ EXPOSE 3020
     │
     ▼
Docker Image
     │
     ├─ Push to registry
     ├─ Tag: codelab-user-frontend:latest
     │
     ▼
Kubernetes Deployment (or Docker Compose)
     │
     ├─ Create pod
     ├─ Set env variables:
     │  ├─ NEXT_PUBLIC_CORE_API_URL
     │  ├─ NEXT_PUBLIC_AUTH_API_URL
     │  └─ NODE_ENV=production
     │
     ├─ Start: npm start (on port 3020)
     │
     └─ Available at: http://localhost:3020
```

---

## 12. Performance Optimization Flow диаграмма

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   PERFORMANCE OPTIMIZATIONS                              │
└──────────────────────────────────────────────────────────────────────────┘

Code Splitting
     │
     ├─ Dynamic imports for heavy components
     │  ├─ ChatWindow → Load on demand
     │  ├─ AgentDetail → Load on demand
     │  └─ LLMProviderConfig → Load on demand
     │
     ├─ Route-based code splitting
     │  ├─ /projects chunk
     │  ├─ /chat chunk
     │  ├─ /agents chunk
     │  └─ /profile chunk
     │
     └─ Lazy loading fallback: <LoadingSpinner />

Caching Strategy
     │
     ├─ Browser cache (HTTP)
     │  ├─ Static assets: 1 year
     │  ├─ Images: 30 days
     │  └─ JS bundles: 1 year (hash-based)
     │
     ├─ React Query cache
     │  ├─ staleTime: 5 min
     │  ├─ gcTime: 10 min
     │  └─ Automatic background refetch
     │
     └─ HTTP cache headers
        ├─ Cache-Control: max-age=...
        └─ ETag validation

Image Optimization
     │
     ├─ next/image component
     │  ├─ Automatic responsive sizing
     │  ├─ Format conversion (WebP)
     │  └─ Lazy loading
     │
     └─ Result: 40% smaller images

Bundle Analysis
     │
     ├─ npm run build → Output analysis
     ├─ Identify large packages
     ├─ Tree-shake unused code
     └─ Optimize imports

Memoization
     │
     ├─ React.memo for expensive components
     │  ├─ ProjectCard
     │  ├─ MessageItem
     │  └─ AgentCard
     │
     └─ useMemo/useCallback for computations

Result:
     │
     ├─ FCP: < 1.5s
     ├─ LCP: < 2.5s
     ├─ CLS: < 0.1
     └─ Total bundle: < 200KB (gzipped)
```

---

## 13. Sequence Diagram: Full Login Flow

```
Client                    Frontend               Auth Service             Database
  │                           │                      │                        │
  │─ Opens /login ────────────>│                      │                        │
  │                           │                      │                        │
  │<─ HTML page (login form) ──│                      │                        │
  │                           │                      │                        │
  │─ Enters email/password ───>│                      │                        │
  │                           │                      │                        │
  │─ Clicks "Login" ──────────>│                      │                        │
  │                           │                      │                        │
  │                           │ POST /token ────────>│                        │
  │                           │ (email, password)    │                        │
  │                           │                      │─ Query user ──────────>│
  │                           │                      │<─ User data ───────────│
  │                           │                      │                        │
  │                           │                      │─ Verify password ──────│
  │                           │                      │                        │
  │                           │                      │─ Generate tokens ──────│
  │                           │                      │  - access_token (JWT)  │
  │                           │                      │  - refresh_token       │
  │                           │                      │  - expires_in: 1800    │
  │                           │                      │                        │
  │                           │<─ TokenResponse ─────│                        │
  │                           │  (access, refresh)   │                        │
  │                           │                      │                        │
  │<─ Set HttpOnly cookie ─────│ Set-Cookie header   │                        │
  │  (user_token)              │ Set-Cookie header   │                        │
  │                            │ (refresh_token)     │                        │
  │                           │                      │                        │
  │<─ Redirect /app/projects ──│                      │                        │
  │                           │                      │                        │
  │─ GET /app/projects ──────>│                      │                        │
  │                           │ [With cookies]       │                        │
  │<─ Projects page ──────────│                      │                        │
  │  + useTokenRefresh hooks  │                      │                        │
```

---

## Резюме диаграмм

Эти диаграммы охватывают:

✅ **Data Flow** - как данные движутся через приложение  
✅ **Component Architecture** - иерархия компонентов  
✅ **State Management** - React Query flow и кэширование  
✅ **Authentication** - Login flow и token refresh  
✅ **Real-time Chat** - SSE streaming и обновления  
✅ **API Integration** - интеграция с backend сервисами  
✅ **Error Handling** - стратегия обработки ошибок  
✅ **Token Lifecycle** - управление токенами на протяжении сессии  
✅ **Middleware & Protection** - защита приватных маршрутов  
✅ **Performance** - оптимизация и кэширование  
✅ **Build & Deploy** - процесс сборки и развертывания  
✅ **Sequence Diagram** - полный flow логина
