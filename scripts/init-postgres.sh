#!/bin/bash
set -e

# Скрипт для создания нескольких баз данных в PostgreSQL при инициализации
# Используется переменная окружения POSTGRES_MULTIPLE_DATABASES

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Создание базы данных для agent-runtime
    CREATE DATABASE agent_runtime;
    GRANT ALL PRIVILEGES ON DATABASE agent_runtime TO $POSTGRES_USER;

    -- Создание базы данных для auth-service
    CREATE DATABASE auth_db;
    GRANT ALL PRIVILEGES ON DATABASE auth_db TO $POSTGRES_USER;
EOSQL

echo "Databases agent_runtime and auth_db created successfully"
