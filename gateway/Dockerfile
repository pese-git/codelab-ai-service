FROM python:3.12-slim as builder

WORKDIR /app

# Установка необходимых инструментов
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

# Установка UV в системный путь
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv

# Копируем файлы для установки зависимостей
COPY pyproject.toml .

# Создаем виртуальное окружение и устанавливаем зависимости
RUN uv venv .venv && \
    . .venv/bin/activate && \
    uv pip install -e .

# Основной образ
FROM python:3.12-slim

WORKDIR /app

# Установка curl для healthcheck
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

# Копируем виртуальное окружение из builder
COPY --from=builder /app/.venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Копируем код приложения
COPY ./app /app/app

# Настройка переменных окружения
ENV PYTHONPATH=/app
ENV PORT=8000

# Запуск приложения
CMD ["python", "app/main.py"]

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
