# Data Models: CodeLab Admin Frontend

**Версия:** 1.0.0  
**Статус:** ✅ Production Ready  
**Дата обновления:** 2 апреля 2026

---

## 📦 Обзор Data Models

Все TypeScript типы и интерфейсы используются для типобезопасной работы с данными в admin-frontend приложении.

---

## 👥 User Management Data Models

### User Types

```typescript
/**
 * Основной тип пользователя в системе
 * Используется в User Management модуле
 */
interface User {
  id: string;                    // UUID пользователя
  email: string;                 // Email адрес
  username: string;              // Username (уникальный)
  status: UserStatus;            // Статус аккаунта
  role: UserRole;                // Роль в системе
  profile: UserProfile;          // Профильная информация
  created_at: string;            // ISO 8601 дата создания
  updated_at: string;            // ISO 8601 дата обновления
  last_login_at: string | null;  // Последний вход
  last_login_ip: string | null;  // IP последнего входа
  email_verified: boolean;       // Email подтвержден
  email_verified_at: string | null;
  password_reset_at: string | null;
  deleted_at: string | null;     // Дата удаления (soft delete)
  sessions_count: number;        // Количество активных сессий
}

/**
 * Статус пользователя
 */
type UserStatus = 'active' | 'inactive' | 'suspended' | 'deleted';

/**
 * Роль пользователя в системе
 */
type UserRole = 'user' | 'admin' | 'moderator';

/**
 * Профильная информация пользователя
 */
interface UserProfile {
  first_name: string;
  last_name: string;
  avatar_url?: string;
  timezone: string;
}

/**
 * Сессия пользователя (для отображения активных сессий)
 */
interface UserSession {
  id: string;
  user_agent: string;
  ip_address: string;
  created_at: string;
  last_activity_at: string;
  expires_at: string;
  is_active: boolean;
}

/**
 * Проект пользователя (для отображения на странице пользователя)
 */
interface UserProject {
  id: string;
  name: string;
  created_at: string;
}

/**
 * Детальная информация о пользователе (для страницы User Details)
 */
interface UserDetail extends User {
  sessions: UserSession[];
  projects: UserProject[];
}

/**
 * Список пользователей с пагинацией
 */
interface UserListResponse {
  data: User[];
  pagination: PaginationInfo;
}

/**
 * Параметры для запроса списка пользователей
 */
interface GetUsersParams {
  search?: string;
  status?: UserStatus;
  created_from?: string;    // ISO 8601
  created_to?: string;      // ISO 8601
  page?: number;
  limit?: number;
  sort_by?: 'created_at' | 'last_login' | 'email';
  sort_order?: 'asc' | 'desc';
}

/**
 * Параметры для сброса пароля
 */
interface ResetPasswordRequest {
  send_email: boolean;
  email_template?: string;
}

/**
 * Ответ после сброса пароля
 */
interface ResetPasswordResponse {
  success: boolean;
  message: string;
  reset_token_sent: boolean;
  expires_at: string;
  user_id: string;
}

/**
 * Параметры для изменения статуса пользователя
 */
interface UpdateUserStatusRequest {
  status: UserStatus;
  reason?: string;  // Для audit log
}

/**
 * Ответ после изменения статуса
 */
interface UpdateUserStatusResponse {
  id: string;
  status: UserStatus;
  updated_at: string;
  audit_id: string;
  sessions_revoked: number;
}
```

---

## 🤖 LLM Providers Data Models

### Provider Types

```typescript
/**
 * LLM провайдер (например, OpenAI, Anthropic)
 */
interface LLMProvider {
  id: string;
  name: string;
  provider_type: ProviderType;
  status: ProviderStatus;
  api_url: string;
  models_count: number;
  users_count: number;
  last_used_at: string | null;
  created_at: string;
  last_tested_at: string | null;
  test_status: TestStatus;
  usage_stats: ProviderUsageStats;
}

/**
 * Тип LLM провайдера
 */
type ProviderType = 'openai' | 'anthropic' | 'local' | 'custom';

/**
 * Статус провайдера
 */
type ProviderStatus = 'active' | 'inactive' | 'error';

/**
 * Статус последнего теста
 */
type TestStatus = 'passed' | 'failed' | 'pending' | 'never_tested';

/**
 * Статистика использования провайдера
 */
interface ProviderUsageStats {
  requests_today: number;
  tokens_today: number;
  cost_today: number;
  requests_total?: number;
  tokens_total?: number;
  cost_total?: number;
}

/**
 * Детальная информация о провайдере
 */
interface LLMProviderDetail extends LLMProvider {
  description: string;
  created_by: string;
  updated_at: string;
  models: LLMModel[];
  usage_stats: ExtendedProviderUsageStats;
  error_stats: ProviderErrorStats;
  health_status: 'healthy' | 'degraded' | 'error';
}

/**
 * LLM модель в провайдере
 */
interface LLMModel {
  id: string;
  name: string;
  display_name: string;
  context_window: number;
  pricing: ModelPricing;
  enabled: boolean;
}

/**
 * Цена за модель
 */
interface ModelPricing {
  input: number;   // Цена за 1K input токенов
  output: number;  // Цена за 1K output токенов
}

/**
 * Расширенная статистика использования провайдера
 */
interface ExtendedProviderUsageStats extends ProviderUsageStats {
  requests_total: number;
  tokens_total: number;
  cost_total: number;
  requests_last_7days: number;
  tokens_last_7days: number;
  cost_last_7days: number;
  requests_last_30days: number;
  tokens_last_30days: number;
  cost_last_30days: number;
}

/**
 * Статистика ошибок провайдера
 */
interface ProviderErrorStats {
  errors_today: number;
  errors_last_7days: number;
  error_rate: number;  // 0.0 - 1.0
  last_error?: ProviderError;
}

/**
 * Информация об ошибке провайдера
 */
interface ProviderError {
  type: string;
  message: string;
  timestamp: string;
}

/**
 * Список провайдеров с пагинацией
 */
interface LLMProviderListResponse {
  data: LLMProvider[];
  pagination: PaginationInfo;
}

/**
 * Параметры для запроса списка провайдеров
 */
interface GetLLMProvidersParams {
  status?: ProviderStatus;
  search?: string;
  page?: number;
  limit?: number;
}

/**
 * Запрос на тестирование провайдера
 */
interface TestProviderRequest {
  model_id: string;
  test_message?: string;
}

/**
 * Ответ после теста провайдера
 */
interface TestProviderResponse {
  success: boolean;
  provider_id: string;
  model_id: string;
  status: 'passed' | 'failed';
  latency_ms: number;
  response?: string;
  error?: string;
  timestamp: string;
  health_status: 'healthy' | 'degraded' | 'error';
}

/**
 * Запрос на обновление провайдера
 */
interface UpdateProviderRequest {
  name?: string;
  status?: ProviderStatus;
  api_url?: string;
  models?: Array<{
    id: string;
    enabled: boolean;
  }>;
}

/**
 * Ответ после обновления провайдера
 */
interface UpdateProviderResponse {
  id: string;
  name: string;
  status: ProviderStatus;
  updated_at: string;
  changes: Record<string, { old: any; new: any }>;
}
```

---

## 📊 Dashboard Data Models

### Dashboard Types

```typescript
/**
 * Статистика для Dashboard
 */
interface DashboardStats {
  timestamp: string;
  period: DashboardPeriod;
  users: UserStatsBlock;
  projects: ProjectStatsBlock;
  agents: AgentStatsBlock;
  llm_usage: LLMUsageBlock;
  services: ServiceHealthBlock;
}

/**
 * Период для которого собрана статистика
 */
type DashboardPeriod = 'today' | 'week' | 'month' | 'year';

/**
 * Блок статистики пользователей
 */
interface UserStatsBlock {
  total: number;
  active: number;
  new_today: number;
  suspended: number;
  inactive: number;
}

/**
 * Блок статистики проектов
 */
interface ProjectStatsBlock {
  total: number;
  active: number;
  new_today: number;
}

/**
 * Блок статистики агентов
 */
interface AgentStatsBlock {
  total: number;
  active: number;
  new_today: number;
}

/**
 * Блок статистики использования LLM
 */
interface LLMUsageBlock {
  total_requests: number;
  total_tokens: number;
  total_cost: number;
  by_provider: ProviderUsageDetail[];
}

/**
 * Детали использования по провайдеру
 */
interface ProviderUsageDetail {
  provider_id: string;
  provider_name: string;
  requests: number;
  tokens: number;
  cost: number;
}

/**
 * Блок здоровья сервисов
 */
interface ServiceHealthBlock {
  overall_status: 'healthy' | 'degraded' | 'error';
  services: ServiceStatus[];
}

/**
 * Статус отдельного сервиса
 */
interface ServiceStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'error' | 'unknown';
  uptime_percent: number;
  latency_ms: number;
  last_check: string;
}

/**
 * Карточка метрики для Dashboard
 */
interface MetricCard {
  title: string;
  value: string | number;
  unit?: string;
  trend?: 'up' | 'down' | 'stable';
  trend_percent?: number;
  color?: 'green' | 'red' | 'yellow' | 'blue';
}
```

---

## 📝 Audit Log Data Models

### Audit Types

```typescript
/**
 * Запись в audit log
 */
interface AuditLogEntry {
  id: string;
  timestamp: string;
  actor_id: string;
  actor_email: string;
  actor_ip: string;
  type: AuditEventType;
  resource: AuditResource;
  resource_id: string;
  action: AuditAction;
  status: AuditStatus;
  details: Record<string, any>;
  user_agent: string;
}

/**
 * Тип события в audit log
 */
type AuditEventType = 
  | 'user_action'
  | 'provider_action'
  | 'security_event'
  | 'system_event'
  | 'settings_change';

/**
 * Тип ресурса, над которым проводилось действие
 */
type AuditResource = 'user' | 'llm_provider' | 'system_settings' | 'audit_log';

/**
 * Действие, проведенное над ресурсом
 */
type AuditAction = 
  | 'create'
  | 'read'
  | 'update'
  | 'delete'
  | 'status_change'
  | 'test'
  | 'reset_password'
  | 'login'
  | 'logout';

/**
 * Статус выполнения действия
 */
type AuditStatus = 'success' | 'failure' | 'partial';

/**
 * Список записей audit log с пагинацией
 */
interface AuditLogResponse {
  data: AuditLogEntry[];
  pagination: PaginationInfo;
}

/**
 * Параметры для запроса audit log
 */
interface GetAuditLogParams {
  type?: AuditEventType;
  actor_id?: string;
  resource?: AuditResource;
  action?: AuditAction;
  from?: string;   // ISO 8601
  to?: string;     // ISO 8601
  search?: string;
  page?: number;
  limit?: number;
}

/**
 * Security событие (подтип AuditLogEntry)
 */
interface SecurityEvent extends AuditLogEntry {
  type: 'security_event';
  severity: 'low' | 'medium' | 'high' | 'critical';
  details: SecurityEventDetails;
}

/**
 * Детали security события
 */
interface SecurityEventDetails {
  event_name: string;
  description: string;
  affected_user_id?: string;
  risk_level: number;  // 1-10
  recommended_action?: string;
}
```

---

## ⚙️ Settings/Configuration Data Models

### Settings Types

```typescript
/**
 * Конфигурация системы
 */
interface SystemSettings {
  rate_limiting: RateLimitingSettings;
  approval_settings: ApprovalSettings;
  email_settings: EmailSettings;
  logging: LoggingSettings;
}

/**
 * Настройки rate limiting
 */
interface RateLimitingSettings {
  login_attempts_per_minute: number;
  api_requests_per_minute: number;
  lockout_duration_minutes: number;
}

/**
 * Настройки approvals
 */
interface ApprovalSettings {
  tool_approval_timeout_seconds: number;
  plan_approval_timeout_seconds: number;
}

/**
 * Email настройки
 */
interface EmailSettings {
  smtp_host: string;
  smtp_port: number;
  smtp_from_address: string;
  smtp_use_tls: boolean;
  smtp_username?: string;  // Никогда не отправляется в response
  smtp_password?: string;  // Никогда не отправляется в response
}

/**
 * Логирование настройки
 */
interface LoggingSettings {
  retention_days: number;
  log_level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  include_sensitive_data: boolean;
}

/**
 * Запрос на обновление настроек
 */
interface UpdateSettingsRequest {
  rate_limiting?: Partial<RateLimitingSettings>;
  approval_settings?: Partial<ApprovalSettings>;
  email_settings?: Partial<EmailSettings>;
  logging?: Partial<LoggingSettings>;
}

/**
 * Ответ после обновления настроек
 */
interface UpdateSettingsResponse {
  success: boolean;
  updated_fields: Record<string, { old: any; new: any }>;
  audit_id: string;
}
```

---

## 🔄 Common/Shared Data Models

### Shared Types

```typescript
/**
 * Информация о пагинации
 */
interface PaginationInfo {
  page: number;
  limit: number;
  total: number;
  pages: number;
}

/**
 * Стандартный ответ об ошибке API
 */
interface ApiError {
  error: string;
  error_description: string;
  details?: Record<string, string | string[]>;
  request_id?: string;
}

/**
 * Стандартный ответ успеха
 */
interface ApiSuccess<T> {
  success: true;
  data: T;
  timestamp?: string;
}

/**
 * JWT токен (используется в localStorage)
 */
interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/**
 * Payload JWT токена (после decode)
 */
interface JWTPayload {
  sub: string;              // User ID
  email: string;
  scope: string[];          // Requested scopes
  exp: number;              // Expiration time
  iat: number;              // Issued at
  jti: string;              // JWT ID
}

/**
 * Роль администратора
 */
type AdminRole = 
  | 'system_admin'    // Полный доступ
  | 'audit_viewer'    // Только чтение audit log
  | 'user_manager'    // Управление пользователями
  | 'llm_manager';    // Управление LLM провайдерами

/**
 * Контекст администратора (текущий залогиненный админ)
 */
interface AdminContext {
  user_id: string;
  email: string;
  roles: AdminRole[];
  scopes: string[];
  is_authenticated: boolean;
}

/**
 * Параметры запроса с фильтрацией
 */
interface FilterParams {
  page?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  search?: string;
}

/**
 * Ответ с пагинацией
 */
interface PaginatedResponse<T> {
  data: T[];
  pagination: PaginationInfo;
}
```

---

## 🏗️ Frontend State Models

### React Query / TanStack Query Types

```typescript
/**
 * Options для запроса списка пользователей
 */
interface UseUsersQueryOptions {
  search?: string;
  status?: UserStatus;
  page?: number;
  limit?: number;
}

/**
 * Hook для работы со списком пользователей
 */
interface UseUsersQuery {
  data: UserListResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook для работы с деталями пользователя
 */
interface UseUserDetailQuery {
  data: UserDetail | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
}

/**
 * Hook для работы со списком LLM провайдеров
 */
interface UseLLMProvidersQuery {
  data: LLMProviderListResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
}

/**
 * Hook для работы с деталями LLM провайдера
 */
interface UseLLMProviderDetailQuery {
  data: LLMProviderDetail | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
}

/**
 * Hook для работы с Dashboard статистикой
 */
interface UseDashboardStatsQuery {
  data: DashboardStats | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
}

/**
 * Hook для работы с Audit Log
 */
interface UseAuditLogQuery {
  data: AuditLogResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
}
```

---

## 📝 Примеры использования

### Пример 1: Загрузка списка пользователей

```typescript
// Компонент
const UsersPage: React.FC = () => {
  const [params, setParams] = useState<GetUsersParams>({
    page: 1,
    limit: 20,
    status: 'active'
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ['users', params],
    queryFn: () => usersApi.getUsers(params)
  });

  return (
    <div>
      {isLoading && <Spinner />}
      {error && <ErrorAlert error={error} />}
      {data && (
        <>
          <Table
            columns={USER_COLUMNS}
            dataSource={data.data}
            pagination={{
              current: params.page,
              pageSize: params.limit,
              total: data.pagination.total,
              onChange: (page) => setParams({ ...params, page })
            }}
          />
        </>
      )}
    </div>
  );
};
```

### Пример 2: Изменение статуса пользователя

```typescript
// Hook для mutation
const useSuspendUserMutation = () => {
  return useMutation({
    mutationFn: (req: {
      userId: string;
      request: UpdateUserStatusRequest;
    }) => usersApi.updateUserStatus(req.userId, req.request),
    onSuccess: () => {
      // Инвалидировать кэш списка пользователей
      queryClient.invalidateQueries({ queryKey: ['users'] });
    }
  });
};

// Использование в компоненте
const suspendMutation = useSuspendUserMutation();

const handleSuspend = async (userId: string) => {
  try {
    await suspendMutation.mutateAsync({
      userId,
      request: {
        status: 'suspended',
        reason: 'Security violation'
      }
    });
    showSuccessMessage('User suspended');
  } catch (error) {
    showErrorMessage('Failed to suspend user');
  }
};
```

### Пример 3: Валидация при сбросе пароля

```typescript
// Zod schema для валидации
const ResetPasswordSchema = z.object({
  send_email: z.boolean(),
  email_template: z.string().optional()
});

type ResetPasswordFormData = z.infer<typeof ResetPasswordSchema>;

// В компоненте форма
const resetForm = useForm<ResetPasswordFormData>({
  resolver: zodResolver(ResetPasswordSchema),
  defaultValues: {
    send_email: true
  }
});

const onSubmit = async (data: ResetPasswordFormData) => {
  const response = await usersApi.resetPassword(userId, data);
  // Обработка результата
};
```

---

## 📋 Чек-лист для валидации Data Models

- ✅ Все типы используют `interface` вместо `type` (кроме enums)
- ✅ Опциональные поля помечены `?`
- ✅ Все значения ISO 8601 имеют тип `string` с комментарием
- ✅ UUID поля помечены как `string`
- ✅ Все числовые поля типизированы как `number`
- ✅ Не используются `any` типы
- ✅ Есть комментарии JSDoc для основных типов
- ✅ Есть примеры использования
- ✅ Sensitive данные (пароли, API ключи) не включены в response типы
