#!/usr/bin/env bash
set -e

# Проверка аргумента
if [ -z "$1" ]; then
  echo "Ошибка: не указано имя модели."
  echo "Использование: $0 <имя_модели>"
  echo "Пример: $0 qwen3:0.6b"
  exit 1
fi

MODEL="$1"
SERVICE_NAME="ollama"

echo "📦 Попытка загрузить модель '$MODEL' в контейнере Ollama…"

# Проверяем, запущен ли сервис
if ! docker compose ps "$SERVICE_NAME" | grep -q "Up"; then
  echo "🚀 Сервис Ollama не запущен. Запускаем docker compose…"
  docker compose up -d "$SERVICE_NAME"
  sleep 3
fi

# Выполняем команду внутри контейнера
echo "🔍 Загружаем модель '$MODEL'…"
docker compose exec "$SERVICE_NAME" ollama pull "$MODEL"

echo "✅ Модель '$MODEL' успешно загружена!"
echo "📋 Список установленных моделей:"
docker compose exec "$SERVICE_NAME" ollama list
