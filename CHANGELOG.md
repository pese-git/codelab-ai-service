# История изменений CodeLab AI Service

Все значимые изменения в проекте документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
и проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

## [1.0.0] - 2026-01-20

### Реализовано

#### Мультиагентная система
- ✅ 5 специализированных агентов (Orchestrator, Coder, Architect, Debug, Ask)
- ✅ LLM-based маршрутизация через Orchestrator с fallback на ключевые слова
- ✅ Автоматическое переключение между агентами с сохранением контекста
- ✅ Ограничения доступа к инструментам и файлам для каждого агента
- ✅ История переключений агентов

#### Event-Driven Architecture
- ✅ Централизованная шина событий (EventBus)
- ✅ Типизированные события для всех операций
- ✅ Подписчики для метрик и аудита
- ✅ Поддержка correlation ID для трейсинга
- ✅ Middleware для обработки событий

#### Персистентность данных
- ✅ Async database (PostgreSQL/SQLite)
- ✅ Session persistence с автоматической очисткой
- ✅ Agent context persistence
- ✅ HITL approvals persistence
- ✅ Миграция на асинхронную архитектуру

#### Аутентификация и безопасность
- ✅ OAuth2 аутентификация (auth-service)
- ✅ JWT токены (access и refresh)
- ✅ JWKS endpoints для публичных ключей
- ✅ Внутренняя авторизация между микросервисами (X-Internal-Auth)
- ✅ Rate limiting middleware

#### Инфраструктура
- ✅ Nginx reverse proxy как единая точка входа
- ✅ Docker Compose для всех сервисов
- ✅ Health checks для всех компонентов
- ✅ Structured logging
- ✅ Prometheus metrics

#### API
- ✅ WebSocket для real-time коммуникации
- ✅ SSE (Server-Sent Events) для streaming
- ✅ REST API для управления сессиями и агентами
- ✅ OpenAPI документация

### Архитектура

#### Микросервисы
- **nginx** - Reverse proxy для маршрутизации запросов
- **auth-service** - OAuth2 аутентификация и управление пользователями
- **gateway** - WebSocket прокси между IDE и Agent Runtime
- **agent-runtime** - Основная AI логика с мультиагентной системой
- **llm-proxy** - Унифицированный доступ к LLM провайдерам
- **postgres** - База данных для персистентности
- **redis** - Кэш и хранилище сессий

#### Поддерживаемые LLM провайдеры
- OpenAI (GPT-3.5, GPT-4)
- Anthropic (Claude)
- Ollama (локальные модели)
- OpenRouter
- DeepSeek
- Qwen

### Документация
- ✅ Актуализированы README для всех сервисов
- ✅ Документация по Event-Driven Architecture
- ✅ Руководство по мультиагентной системе
- ✅ Примеры использования API
- ✅ Инструкции по развертыванию

### Тестирование
- ✅ Unit тесты для всех компонентов
- ✅ Integration тесты
- ✅ E2E тесты через API
- ✅ Покрытие тестами > 80%

## [0.9.0] - 2026-01-17

### Добавлено
- Event-Driven Architecture (Фаза 1)
- Session metrics collector
- Audit logging для критичных событий
- Session cleanup service

## [0.8.0] - 2026-01-14

### Добавлено
- Мультиагентная система (5 агентов)
- Agent switching механизм
- LLM-based routing

## [0.7.0] - 2026-01-12

### Добавлено
- Async database migration
- PostgreSQL поддержка
- Session persistence

## [0.6.0] - 2026-01-11

### Добавлено
- OAuth2 аутентификация
- JWT токены
- JWKS endpoints

## [0.5.0] - 2026-01-10

### Добавлено
- Nginx reverse proxy
- Внутренняя авторизация между сервисами
- Rate limiting

## [0.4.0] - 2025-12-30

### Добавлено
- HITL (Human-in-the-Loop) с database persistence
- Tool approval механизм
- WebSocket поддержка в Gateway

## [0.3.0] - 2025-12-28

### Добавлено
- LLM Proxy Service
- Поддержка множественных LLM провайдеров
- SSE streaming

## [0.2.0] - 2025-12-25

### Добавлено
- Agent Runtime Service
- Tool registry (9 инструментов)
- Session management

## [0.1.0] - 2025-12-20

### Добавлено
- Базовая архитектура микросервисов
- Gateway Service
- Docker Compose конфигурация

---

## Типы изменений

- **Добавлено** - новая функциональность
- **Изменено** - изменения в существующей функциональности
- **Устарело** - функциональность, которая скоро будет удалена
- **Удалено** - удаленная функциональность
- **Исправлено** - исправления ошибок
- **Безопасность** - изменения, связанные с безопасностью

## Ссылки

- [Документация проекта](./doc/)
- [README](./README.md)
- [Лицензия](./LICENSE)
