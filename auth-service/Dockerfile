# Используем официальный Python образ
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей
COPY pyproject.toml ./

# Устанавливаем uv для управления зависимостями
RUN pip install --no-cache-dir uv

# Устанавливаем зависимости проекта
RUN uv pip install --system --no-cache -e .

# Копируем код приложения
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Создаем директории для данных и ключей
RUN mkdir -p /app/data /app/keys

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Открываем порт
EXPOSE 8003

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8003}/health || exit 1

# Запускаем приложение
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
