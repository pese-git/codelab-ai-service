# Nginx Reverse Proxy для Codelab AI Service

## Описание

Nginx выступает в качестве reverse proxy для auth-service и gateway-service, обеспечивая единую точку входа для всех API запросов.

## Архитектура

```
Клиент → Nginx (порт 80) → auth-service (внутренний порт 8003)
                          → gateway (внутренний порт 8000)
```

## Маршрутизация

### Auth Service
- **`/oauth/*`** → `http://auth-service:8003/oauth/*`
  - OAuth2 endpoints (login, token, refresh и т.д.)
  - Пример: `http://localhost/oauth/token`
- **`/.well-known/*`** → `http://auth-service:8003/.well-known/*`
  - JWKS endpoints для публичных ключей
  - Пример: `http://localhost/.well-known/jwks.json`
- **`/auth-health`** → `http://auth-service:8003/health`
  - Health check endpoint

### Gateway Service
- **`/api/v1/*`** → `http://gateway:8000/api/v1/*`
  - REST API endpoints версии 1
  - Пример: `http://localhost/api/v1/sessions`
- **`/api/v1/ws/{session_id}`** → `http://gateway:8000/api/v1/ws/{session_id}`
  - WebSocket соединения для real-time коммуникации
  - Пример: `ws://localhost/api/v1/ws/my-session-id`
- **`/gateway-health`** → `http://gateway:8000/health`
  - Health check endpoint

### Служебные endpoints
- **`/`** - Информационная страница с описанием доступных endpoints
- **`/nginx-health`** - Health check самого nginx

## Конфигурация

### Основные настройки

- **Порт**: 80 (настраивается через `NGINX_PORT` в `.env`)
- **Worker connections**: 1024
- **Client max body size**: 10MB
- **Таймауты**:
  - Обычные запросы: 60s
  - Длительные операции (API): 300s
  - WebSocket: 3600s

### WebSocket поддержка

Nginx настроен для корректной работы с WebSocket соединениями:
- Автоматический upgrade HTTP → WebSocket
- Отключена буферизация для real-time передачи
- Увеличенные таймауты для долгоживущих соединений

## Использование

### Запуск

```bash
# Запуск всех сервисов включая nginx
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов nginx
docker-compose logs -f nginx
```

### Примеры запросов

#### Аутентификация (Auth Service)

```bash
# Получение токена (обратите внимание - без префикса /auth)
curl -X POST http://localhost/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=user&password=pass"

# Получение JWKS
curl http://localhost/.well-known/jwks.json

# Health check
curl http://localhost/auth-health
```

#### Gateway API

```bash
# REST API запрос
curl -X POST http://localhost/api/v1/sessions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data": "example"}'

# Health check
curl http://localhost/gateway-health
```

#### WebSocket соединение

```javascript
// JavaScript пример
const sessionId = 'my-session-id';
const ws = new WebSocket(`ws://localhost/api/v1/ws/${sessionId}`);

ws.onopen = () => {
  console.log('Connected');
  ws.send(JSON.stringify({
    type: 'user_message',
    content: 'Hello!'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Message:', data);
};
```

### Проверка работоспособности

```bash
# Проверка nginx
curl http://localhost/nginx-health

# Проверка всех сервисов
curl http://localhost/auth-health
curl http://localhost/gateway-health

# Информация о доступных endpoints
curl http://localhost/
```

## Безопасность

### Изоляция сервисов

- Auth-service и gateway больше не доступны напрямую извне
- Все запросы проходят через nginx
- Внутренние сервисы используют `expose` вместо `ports` в docker-compose

### Заголовки

Nginx автоматически добавляет следующие заголовки:
- `X-Real-IP` - реальный IP клиента
- `X-Forwarded-For` - цепочка прокси
- `X-Forwarded-Proto` - протокол (http/https)
- `X-Forwarded-Host` - оригинальный хост
- `X-Forwarded-Server` - сервер прокси

## Мониторинг

### Логи

```bash
# Все логи nginx
docker-compose logs nginx

# Access log (запросы) в реальном времени
docker-compose exec nginx tail -f /var/log/nginx/access.log

# Error log (ошибки) в реальном времени
docker-compose exec nginx tail -f /var/log/nginx/error.log
```

### Метрики

Health check endpoints для мониторинга:
- Nginx: `http://localhost/nginx-health`
- Auth: `http://localhost/auth-health`
- Gateway: `http://localhost/gateway-health`

## Troubleshooting

### Nginx не запускается

```bash
# Проверка конфигурации
docker-compose exec nginx nginx -t

# Перезагрузка конфигурации без перезапуска контейнера
docker-compose exec nginx nginx -s reload

# Полный перезапуск nginx
docker-compose restart nginx
```

### 502 Bad Gateway

Проверьте, что backend сервисы запущены и здоровы:
```bash
# Статус всех сервисов
docker-compose ps

# Логи auth-service
docker-compose logs auth-service

# Логи gateway
docker-compose logs gateway

# Проверка сетевого подключения
docker-compose exec nginx ping auth-service
docker-compose exec nginx ping gateway
```

### WebSocket не работает

Убедитесь, что:
1. Используется правильный протокол (`ws://` для HTTP, `wss://` для HTTPS)
2. Путь `/ws` указан корректно
3. Backend gateway поддерживает WebSocket на этом пути
4. Нет промежуточных прокси, которые блокируют WebSocket

```bash
# Проверка WebSocket через curl
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: test" \
  http://localhost/ws
```

### Проблемы с CORS

Если возникают проблемы с CORS, можно добавить заголовки в nginx:

```nginx
location /api/v1/ {
    # Добавить CORS заголовки
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type' always;
    
    if ($request_method = 'OPTIONS') {
        return 204;
    }
    
    proxy_pass http://gateway_backend/api/v1/;
}
```

## Расширение конфигурации

### Добавление SSL/TLS

Для production окружения рекомендуется добавить SSL:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # ... остальная конфигурация
}

# Редирект с HTTP на HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### Добавление rate limiting

```nginx
http {
    # Ограничение по IP адресу
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/s;
    
    server {
        # Rate limiting для API
        location /api/v1/ {
            limit_req zone=api_limit burst=20 nodelay;
            proxy_pass http://gateway_backend/api/v1/;
        }
        
        # Более строгое ограничение для аутентификации
        location /oauth/ {
            limit_req zone=auth_limit burst=10 nodelay;
            proxy_pass http://auth_backend/oauth/;
        }
    }
}
```

### Добавление кэширования

```nginx
http {
    proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=1g;
    
    server {
        # Кэширование статических данных
        location /.well-known/ {
            proxy_cache api_cache;
            proxy_cache_valid 200 1h;
            proxy_cache_key "$scheme$request_method$host$request_uri";
            add_header X-Cache-Status $upstream_cache_status;
            
            proxy_pass http://auth_backend/.well-known/;
        }
    }
}
```

### Добавление логирования в JSON формате

```nginx
http {
    log_format json_combined escape=json
    '{'
        '"time_local":"$time_local",'
        '"remote_addr":"$remote_addr",'
        '"request":"$request",'
        '"status": "$status",'
        '"body_bytes_sent":"$body_bytes_sent",'
        '"request_time":"$request_time",'
        '"http_referrer":"$http_referer",'
        '"http_user_agent":"$http_user_agent"'
    '}';
    
    access_log /var/log/nginx/access.log json_combined;
}
```

## Переменные окружения

В файле `.env` можно настроить:

```bash
# Порт nginx (по умолчанию 80)
NGINX_PORT=80

# Или использовать другой порт, например 8080
NGINX_PORT=8080
```

## Дополнительная информация

- [Nginx Documentation](https://nginx.org/en/docs/)
- [Nginx WebSocket Proxying](https://nginx.org/en/docs/http/websocket.html)
- [Docker Compose Networking](https://docs.docker.com/compose/networking/)
- [Nginx Reverse Proxy Guide](https://docs.nginx.com/nginx/admin-guide/web-server/reverse-proxy/)
