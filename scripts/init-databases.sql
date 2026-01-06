-- Создание баз данных для codelab-ai-service
-- Этот скрипт выполняется автоматически при первом запуске PostgreSQL

-- Создание базы данных для agent-runtime
SELECT 'CREATE DATABASE agent_runtime'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'agent_runtime')\gexec

-- Создание базы данных для auth-service
SELECT 'CREATE DATABASE auth_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'auth_db')\gexec
