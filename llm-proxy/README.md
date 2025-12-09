# LLM Proxy Service

LLM Proxy — микросервис для унификации доступа к различным языковым моделям (LLM), реализующий защищённое API для сервисов экосистемы. Является частью мультисервисной архитектуры Codelab.

## Основные возможности

- Единое REST API для обращения к языковым моделям
- SSE (Server-Sent Events) для стриминговых ответов token-by-token
- Защита эндпоинтов через внутренний API-ключ (middleware)
- Лёгкое масштабирование и расширяемость архитектуры за счёт слоёв (api, services, models, middleware)
- Готовность к интеграции новых провайдеров LLM

---

## Архитектура

- `app/main.py` — точка входа, инициализация FastAPI и подключение маршрутов/слоёв/конфигов
- `app/api/v1/endpoints.py` — маршруты API (v1, легко расширить под v2)
- `app/models/schemas.py` — Pydantic-схемы входных и выходных данных
- `app/services/llm_service.py` — бизнес-логика взаимодействия с LLM (stream/fake, SSE)
- `app/middleware/internal_auth.py` — middleware с внутренней авторизацией
- `app/core/config.py` — централизованный доступ к переменным окружения и логированию

---

## Быстрый старт (разработка)

```bash
# Запуск с пересборкой через Docker Compose
docker compose up -d --build

# Запуск всех автотестов для сервиса llm-proxy
cd llm-proxy
uv run pytest --maxfail=3 --disable-warnings -v tests
```

## API

- `GET /health` — Проверка статуса сервиса
- `GET /llm/models` — Список поддерживаемых языковых моделей
- `POST /llm/chat` — Чат с LLM (может отвечать стримом, опциональный флаг `stream`)
- `POST /llm/stream` — Стримовое получение токенов (SSE)

> Для защищённых эндпоинтов требуется заголовок:  
`x-internal-auth: <INTERNAL_API_KEY>`

---

## Конфигурация (через переменные окружения)

- `INTERNAL_API_KEY` — Cекретный приватный ключ для доступа к API (по умолчанию "change-me-internal-key", переопределяется в .env/docker-compose)
- `LOG_LEVEL` — Уровень логирования (`INFO`/`DEBUG`/...)

---

## Расширение

- Для добавления новых моделей LLM — реализуйте их в `services/llm_service.py`
- Для поддержки новых версий API — создайте router в `api/v2/endpoints.py`
- Для внедрения нового способа авторизации/аудита — добавьте новый middleware в `middleware/`
- Все настройки и логи централизованы через `core/config.py` и AppConfig

---

## Тестирование

Тесты структурированы по слоям, запуск:
```bash
uv run pytest tests
```
или внутри контейнера.

---

## Authors & License

© 2025 Codelab Contributors  
MIT License
