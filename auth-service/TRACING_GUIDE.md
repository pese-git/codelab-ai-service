# Руководство по трейсингу Auth Service

## Обзор

В auth-service добавлена комплексная система трейсинга для отслеживания процесса авторизации пользователей и выдачи JWT токенов. Все трейсы помечены префиксом `[TRACE]` и содержат структурированные данные в поле `extra` для удобного анализа.

## Точки трейсинга

### 1. OAuth Endpoint (`app/api/v1/oauth.py`)

#### Token Endpoint
- **token_endpoint_start** - Начало обработки запроса токена
  - Параметры: `grant_type`, `client_id`, `username`, `ip_address`, `has_password`, `has_refresh_token`, `scope`
  
- **grant_type_parsed** - Успешный парсинг типа grant
- **grant_type_invalid** - Неподдерживаемый тип grant
- **token_request_created** - Создан объект запроса токена
- **route_password_grant** - Маршрутизация к password grant
- **route_refresh_grant** - Маршрутизация к refresh grant
- **token_endpoint_error** - Ошибка в endpoint

#### Password Grant Handler
- **password_grant_start** - Начало обработки password grant
- **password_grant_missing_params** - Отсутствуют обязательные параметры
- **brute_force_check** - Проверка защиты от брутфорса
- **brute_force_locked** - Аккаунт заблокирован
- **brute_force_passed** - Проверка пройдена
- **auth_service_call** - Вызов сервиса аутентификации
- **password_grant_auth_failed** - Аутентификация не удалась
- **failed_attempt_recorded** - Записана неудачная попытка
- **password_grant_auth_success** - Успешная аутентификация
- **save_refresh_token** - Сохранение refresh токена
- **password_grant_complete** - Завершение password grant

#### Refresh Grant Handler
- **refresh_grant_start** - Начало обработки refresh grant
- **refresh_grant_missing_token** - Отсутствует refresh токен
- **refresh_token_jwt_validation** - Валидация JWT refresh токена
- **refresh_token_jwt_valid** - JWT валиден
- **refresh_token_jwt_invalid** - JWT невалиден
- **refresh_token_db_check** - Проверка токена в БД
- **refresh_token_db_invalid** - Токен отозван или недействителен
- **refresh_token_validated** - Токен валидирован
- **auth_service_refresh_call** - Вызов сервиса для refresh
- **refresh_grant_auth_failed** - Аутентификация не удалась
- **refresh_grant_auth_success** - Успешная аутентификация
- **revoke_old_token** - Отзыв старого токена
- **save_new_refresh_token** - Сохранение нового токена
- **refresh_grant_complete** - Завершение refresh grant

### 2. Auth Service (`app/services/auth_service.py`)

#### Password Grant Authentication
- **auth_service_password_start** - Начало аутентификации password grant
- **validate_request** - Валидация запроса
- **request_validation_failed** - Валидация не прошла
- **validate_client** - Валидация OAuth клиента
- **client_validation_failed** - Клиент не валиден
- **client_validated** - Клиент валидирован
- **validate_grant_type** - Валидация типа grant
- **grant_type_not_allowed** - Grant type не разрешен
- **authenticate_user** - Аутентификация пользователя
- **user_auth_failed** - Аутентификация пользователя не удалась
- **user_authenticated** - Пользователь аутентифицирован
- **validate_scope** - Валидация scope
- **scope_validation_failed** - Scope невалиден
- **scope_validated** - Scope валидирован
- **create_token_pair** - Создание пары токенов
- **token_pair_created** - Токены созданы
- **auth_service_password_success** - Успешное завершение

#### Refresh Grant Authentication
- **auth_service_refresh_start** - Начало аутентификации refresh grant
- **validate_refresh_request** - Валидация запроса
- **refresh_request_validation_failed** - Валидация не прошла
- **validate_client_refresh** - Валидация клиента
- **client_validation_failed_refresh** - Клиент не валиден
- **client_validated_refresh** - Клиент валидирован
- **validate_refresh_grant_type** - Валидация grant type
- **refresh_grant_type_not_allowed** - Grant type не разрешен
- **validate_refresh_token_payload** - Валидация payload токена
- **refresh_token_payload_valid** - Payload валиден
- **refresh_token_payload_invalid** - Payload невалиден
- **verify_client_id_match** - Проверка соответствия client_id
- **client_id_mismatch** - Client ID не совпадает
- **fetch_user** - Получение пользователя
- **user_not_found_or_inactive** - Пользователь не найден или неактивен
- **user_found_active** - Пользователь найден и активен
- **create_token_pair_refresh** - Создание новой пары токенов
- **token_pair_created_refresh** - Токены созданы
- **auth_service_refresh_success** - Успешное завершение

### 3. User Service (`app/services/user_service.py`)

#### User Authentication
- **user_service_auth_start** - Начало аутентификации пользователя
- **lookup_by_username** - Поиск по username
- **lookup_by_email** - Поиск по email
- **user_not_found** - Пользователь не найден
- **user_found** - Пользователь найден
- **user_inactive** - Пользователь неактивен
- **verify_password** - Проверка пароля
- **invalid_password** - Неверный пароль
- **password_verified** - Пароль верен
- **user_service_auth_success** - Успешная аутентификация

### 4. OAuth Client Service (`app/services/oauth_client_service.py`)

#### Client Validation
- **oauth_client_validate_start** - Начало валидации клиента
- **fetch_client** - Получение клиента из БД
- **client_not_found** - Клиент не найден
- **client_found** - Клиент найден
- **client_inactive** - Клиент неактивен
- **client_active** - Клиент активен
- **validate_secret** - Валидация секрета (для confidential clients)
- **missing_secret** - Секрет отсутствует
- **invalid_secret** - Секрет невалиден
- **secret_validated** - Секрет валидирован
- **oauth_client_validate_success** - Успешная валидация

### 5. Token Service (`app/services/token_service.py`)

#### Token Pair Creation
- **token_service_create_pair_start** - Начало создания пары токенов
- **create_access_token** - Создание access токена
- **access_token_created** - Access токен создан
- **create_refresh_token** - Создание refresh токена
- **refresh_token_created** - Refresh токен создан
- **token_service_create_pair_success** - Пара токенов создана

#### Token Decoding
- **decode_token** - Декодирование JWT токена
- **token_decoded** - Токен декодирован
- **token_decode_failed** - Ошибка декодирования

#### Token Validation
- **validate_access_token** - Валидация access токена
- **invalid_access_token_type** - Неверный тип токена
- **access_token_validated** - Access токен валидирован
- **validate_refresh_token** - Валидация refresh токена
- **invalid_refresh_token_type** - Неверный тип токена
- **refresh_token_validated** - Refresh токен валидирован

## Использование трейсов

### Поиск по логам

Все трейсы можно найти по префиксу `[TRACE]`:

```bash
# Все трейсы
grep "\[TRACE\]" auth-service.log

# Трейсы конкретного пользователя
grep "\[TRACE\].*username.*testuser" auth-service.log

# Трейсы ошибок аутентификации
grep "\[TRACE\].*auth_failed" auth-service.log

# Трейсы по конкретной точке
grep "trace_point.*password_grant_start" auth-service.log
```

### Анализ проблем с авторизацией

#### Сценарий 1: Пользователь не может войти

1. Найдите начало запроса: `token_endpoint_start`
2. Проверьте валидацию клиента: `client_validation_failed`
3. Проверьте аутентификацию пользователя: `user_auth_failed`
4. Проверьте конкретную причину:
   - `user_not_found` - пользователь не существует
   - `user_inactive` - пользователь деактивирован
   - `invalid_password` - неверный пароль
   - `brute_force_locked` - аккаунт заблокирован

#### Сценарий 2: Не выдается JWT токен

1. Проверьте успешность аутентификации: `user_authenticated`
2. Проверьте валидацию scope: `scope_validation_failed`
3. Проверьте создание токенов: `token_pair_created`
4. Проверьте сохранение refresh токена: `save_refresh_token`

#### Сценарий 3: Проблемы с refresh токеном

1. Проверьте валидацию JWT: `refresh_token_jwt_invalid`
2. Проверьте статус в БД: `refresh_token_db_invalid`
3. Проверьте соответствие client_id: `client_id_mismatch`
4. Проверьте статус пользователя: `user_not_found_or_inactive`

## Структурированные данные

Каждый трейс содержит поле `extra` со структурированными данными:

```python
{
    "trace_point": "password_grant_auth_failed",
    "username": "testuser",
    "client_id": "web-app",
    "ip_address": "192.168.1.100"
}
```

Это позволяет использовать системы логирования (ELK, Grafana Loki) для:
- Фильтрации по полям
- Построения метрик
- Создания дашбордов
- Настройки алертов

## Примеры запросов

### Успешная авторизация (password grant)

```
[TRACE] Token endpoint called: grant_type=password, client_id=web-app, username=testuser
[TRACE] Grant type parsed successfully: password
[TRACE] Token request created
[TRACE] Routing to password grant handler
[TRACE] Password grant handler started
[TRACE] Checking brute-force protection
[TRACE] Brute-force check passed
[TRACE] Calling auth service for password grant authentication
[TRACE] AuthService.authenticate_password_grant started
[TRACE] Validating password grant request
[TRACE] Request validation passed, validating OAuth client
[TRACE] OAuthClientService.validate_client started
[TRACE] Fetching client from database
[TRACE] Client found in database
[TRACE] Client is active
[TRACE] Client validated successfully
[TRACE] OAuth client validated
[TRACE] Validating grant type for client
[TRACE] Grant type validated, authenticating user
[TRACE] UserService.authenticate started
[TRACE] Looking up user by username
[TRACE] User found
[TRACE] User is active, verifying password
[TRACE] Password verified
[TRACE] Authentication successful
[TRACE] User authenticated successfully
[TRACE] Validating and normalizing scope
[TRACE] Scope validated and normalized
[TRACE] Creating token pair
[TRACE] TokenService.create_token_pair started
[TRACE] Creating access token
[TRACE] Access token created
[TRACE] Creating refresh token
[TRACE] Refresh token created
[TRACE] Token pair created successfully
[TRACE] Password grant authentication completed successfully
[TRACE] Authentication successful, resetting failed attempts
[TRACE] Saving refresh token to database
[TRACE] Password grant completed successfully
```

### Неудачная авторизация (неверный пароль)

```
[TRACE] Token endpoint called: grant_type=password, client_id=web-app, username=testuser
[TRACE] Password grant handler started
[TRACE] Brute-force check passed
[TRACE] Calling auth service for password grant authentication
[TRACE] AuthService.authenticate_password_grant started
[TRACE] OAuth client validated
[TRACE] Grant type validated, authenticating user
[TRACE] UserService.authenticate started
[TRACE] User found
[TRACE] User is active, verifying password
[TRACE] Authentication failed: invalid password
[TRACE] User authentication failed
[TRACE] Authentication failed for password grant
[TRACE] Failed attempt recorded
```

## Рекомендации

1. **Мониторинг**: Настройте алерты на критические точки отказа
2. **Метрики**: Собирайте статистику по `trace_point` для анализа производительности
3. **Безопасность**: Не логируйте пароли и секреты (уже реализовано)
4. **Производительность**: В production можно снизить уровень DEBUG трейсов
5. **Корреляция**: Используйте `user_id`, `client_id`, `jti` для связывания событий

## Настройка уровня логирования

В `.env` файле:

```env
# Для детального трейсинга
AUTH_SERVICE__LOG_LEVEL=DEBUG

# Для production (только важные события)
AUTH_SERVICE__LOG_LEVEL=INFO

# Только ошибки
AUTH_SERVICE__LOG_LEVEL=WARNING
```
