# Документация CodeLab AI Service

**Версия:** 1.0.0  
**Дата:** 20 января 2026  
**Статус:** ✅ Актуально

---

## 📚 Структура документации

### Основная документация

1. **[Главный README](../README.md)** - Обзор проекта, установка, быстрый старт
2. **[CHANGELOG](../CHANGELOG.md)** - История изменений проекта

### Технические требования

3. **[Требования к Gateway](tech-req-gateway.md)** - Спецификация Gateway Service
4. **[Требования к Agent Runtime](tech-req-agent-runtime-service.md)** - Спецификация Agent Runtime Service
5. **[Требования к LLM Proxy](tech-req-llm-proxy-service.md)** - Спецификация LLM Proxy Service

### Мультиагентная система

6. **[Обзор мультиагентной системы](MULTI_AGENT_README.md)** - Главный документ по мультиагентам
7. **[Быстрый старт](multi-agent-quick-start.md)** - Примеры использования агентов
8. **[Архитектура](multi-agent-architecture-plan.md)** - Детальный план архитектуры
9. **[Диаграммы](multi-agent-architecture-diagram.md)** - Визуализация архитектуры

### Протоколы и интеграция

10. **[WebSocket Protocol](websocket-protocol.md)** - Протокол WebSocket взаимодействия
11. **[Agent Extended Protocol](agent_extended_protocol.md)** - Расширенный протокол агента
12. **[HITL Implementation](HITL_IMPLEMENTATION.md)** - Human-in-the-Loop реализация

### Конфигурация и развертывание

13. **[Конфигурация БД](DATABASE_CONFIGURATION.md)** - Настройка PostgreSQL/SQLite

---

## 🗂️ Документация по сервисам

### Agent Runtime
- **[README](../agent-runtime/README.md)** - Основная документация
- **[Event-Driven Architecture](../agent-runtime/doc/EVENT_DRIVEN_ARCHITECTURE.md)** - Руководство по событийной архитектуре
- **[LLM Metrics Quickstart](../agent-runtime/doc/LLM_METRICS_QUICKSTART.md)** - Быстрый старт по метрикам
- **[Metrics Collection Guide](../agent-runtime/doc/METRICS_COLLECTION_GUIDE.md)** - Руководство по сбору метрик
- **[Session Metrics Proposal](../agent-runtime/doc/SESSION_METRICS_PROPOSAL.md)** - Предложение по метрикам сессий

### Gateway
- **[README](../gateway/README.md)** - Основная документация Gateway Service

### LLM Proxy
- **[README](../llm-proxy/README.md)** - Основная документация LLM Proxy Service

### Auth Service
- **[Project Summary](../auth-service/docs/PROJECT_SUMMARY.md)** - Резюме проекта
- **[Technical Specification](../auth-service/docs/TECHNICAL_SPECIFICATION.md)** - Техническая спецификация
- **[Integration Points](../auth-service/docs/INTEGRATION_POINTS.md)** - Точки интеграции
- **[Implementation Plan](../auth-service/docs/IMPLEMENTATION_PLAN.md)** - План реализации

### Nginx
- **[README](../nginx/README.md)** - Конфигурация Nginx reverse proxy

---

## 🚀 Быстрая навигация

### Для начинающих
1. Начните с [главного README](../README.md)
2. Изучите [WebSocket Protocol](websocket-protocol.md)
3. Прочитайте [быстрый старт по мультиагентам](multi-agent-quick-start.md)

### Для разработчиков
1. Изучите [технические требования](tech-req-agent-runtime-service.md)
2. Прочитайте [архитектуру мультиагентов](multi-agent-architecture-plan.md)
3. Изучите [Event-Driven Architecture](../agent-runtime/doc/EVENT_DRIVEN_ARCHITECTURE.md)

### Для DevOps
1. Изучите [конфигурацию БД](DATABASE_CONFIGURATION.md)
2. Прочитайте [главный README](../README.md) раздел "Установка"
3. Изучите документацию по каждому сервису

### Для архитекторов
1. Изучите [диаграммы архитектуры](multi-agent-architecture-diagram.md)
2. Прочитайте [технические требования](tech-req-agent-runtime-service.md)
3. Изучите [план архитектуры](multi-agent-architecture-plan.md)

---

## 📖 Темы документации

### Архитектура
- Мультиагентная система (5 агентов)
- Event-Driven Architecture
- Domain-Driven Design
- Микросервисная архитектура

### Функциональность
- WebSocket коммуникация
- SSE streaming
- HITL (Human-in-the-Loop)
- OAuth2 аутентификация
- Session persistence

### Интеграция
- Gateway ↔ Agent Runtime
- Agent Runtime ↔ LLM Proxy
- IDE ↔ Gateway
- Auth Service ↔ Gateway

### Операции
- Развертывание через Docker Compose
- Конфигурация баз данных
- Мониторинг и метрики
- Логирование и трейсинг

---

## 🔍 Поиск по темам

### Мультиагентная система
- [MULTI_AGENT_README.md](MULTI_AGENT_README.md)
- [multi-agent-quick-start.md](multi-agent-quick-start.md)
- [multi-agent-architecture-plan.md](multi-agent-architecture-plan.md)
- [multi-agent-architecture-diagram.md](multi-agent-architecture-diagram.md)

### Event-Driven Architecture
- [EVENT_DRIVEN_ARCHITECTURE.md](../agent-runtime/doc/EVENT_DRIVEN_ARCHITECTURE.md)

### HITL
- [HITL_IMPLEMENTATION.md](HITL_IMPLEMENTATION.md)
- [websocket-protocol.md](websocket-protocol.md) (раздел HITL)

### Протоколы
- [websocket-protocol.md](websocket-protocol.md)
- [agent_extended_protocol.md](agent_extended_protocol.md)

### Конфигурация
- [DATABASE_CONFIGURATION.md](DATABASE_CONFIGURATION.md)
- Файлы .env.example в каждом сервисе

### Метрики
- [LLM_METRICS_QUICKSTART.md](../agent-runtime/doc/LLM_METRICS_QUICKSTART.md)
- [METRICS_COLLECTION_GUIDE.md](../agent-runtime/doc/METRICS_COLLECTION_GUIDE.md)

---

## 📝 Соглашения по документации

### Формат документов
- Все документы в формате Markdown
- Заголовки с версией и датой
- Статус актуальности (✅ Актуально / ✅ Реализовано)
- Разделители между секциями (`---`)

### Структура документа
```markdown
# Название документа

**Версия:** X.Y.Z  
**Дата:** DD месяца YYYY  
**Статус:** ✅ Статус

---

## Содержание
...
```

### Ссылки
- Относительные пути для внутренних ссылок
- Абсолютные URL для внешних ресурсов
- Markdown синтаксис для ссылок на код: `[filename](path/to/file.py)`

---

## 🔄 Обновление документации

При внесении изменений в код:
1. Обновите соответствующий README сервиса
2. Обновите CHANGELOG.md
3. Обновите дату в заголовке документа
4. Проверьте актуальность примеров кода
5. Обновите диаграммы при необходимости

---

## 📞 Поддержка

Для вопросов по документации:
- Проверьте [главный README](../README.md)
- Изучите документацию конкретного сервиса
- Обратитесь к примерам в quick-start документах

---

© 2026 CodeLab Contributors
