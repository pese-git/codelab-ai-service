# Session Persistence Guide

## Обзор

Начиная с этой версии, agent-runtime поддерживает **персистентное хранение сессий** с использованием SQLite и SQLAlchemy. Это означает, что:

- ✅ Сессии сохраняются автоматически при каждом изменении
- ✅ История сообщений восстанавливается после перезапуска сервиса
- ✅ Контекст агентов (текущий агент, история переключений) сохраняется
- ✅ IDE может восстановить историю чата после перезагрузки

## Архитектура

### Компоненты

1. **Database Module** ([`app/services/database.py`](app/services/database.py))
   - SQLAlchemy модели для sessions и agent_contexts
   - Thread-safe операции с базой данных
   - Автоматическая инициализация схемы

2. **SessionManager** ([`app/services/session_manager.py`](app/services/session_manager.py))
   - Кэширование сессий в памяти
   - Автоматическая персистентность при изменениях
   - Загрузка всех сессий при старте

3. **AgentContextManager** ([`app/services/agent_context.py`](app/services/agent_context.py))
   - Кэширование контекстов агентов в памяти
   - Автоматическая персистентность при переключении агентов
   - Загрузка всех контекстов при старте

### База данных

**Расположение:** `data/agent_runtime.db` (SQLite)

**Таблицы:**

1. `sessions` - хранит состояние сессий
   - `session_id` (PK)
   - `messages` (JSON)
   - `last_activity` (DateTime)
   - `created_at` (DateTime)

2. `agent_contexts` - хранит контексты агентов
   - `session_id` (PK)
   - `current_agent` (String)
   - `agent_history` (JSON)
   - `context_metadata` (JSON)
   - `created_at` (DateTime)
   - `last_switch_at` (DateTime)
   - `switch_count` (Integer)

## API Endpoints для восстановления сессий

### 1. Получить историю сессии

**Endpoint:** `GET /api/v1/sessions/{session_id}/history`

**Описание:** Получить полную историю сообщений и информацию о текущем агенте для сессии.

**Пример запроса:**
```bash
curl http://localhost:8001/api/v1/sessions/my-session-123/history
```

**Пример ответа:**
```json
{
  "session_id": "my-session-123",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant"
    },
    {
      "role": "user",
      "content": "Hello, how are you?"
    },
    {
      "role": "assistant",
      "content": "I'm doing great! How can I help you?"
    }
  ],
  "message_count": 3,
  "last_activity": "2025-12-31T08:45:00.000Z",
  "current_agent": "coder",
  "agent_history": [
    {
      "from": "orchestrator",
      "to": "coder",
      "reason": "User requested coding task",
      "timestamp": "2025-12-31T08:44:00.000Z"
    }
  ]
}
```

**Коды ответа:**
- `200` - История успешно получена
- `404` - Сессия не найдена

### 2. Список всех сессий

**Endpoint:** `GET /api/v1/sessions`

**Описание:** Получить список всех активных сессий с базовой информацией.

**Пример запроса:**
```bash
curl http://localhost:8001/api/v1/sessions
```

**Пример ответа:**
```json
{
  "sessions": [
    {
      "session_id": "session-1",
      "message_count": 5,
      "last_activity": "2025-12-31T08:45:00.000Z",
      "current_agent": "coder"
    },
    {
      "session_id": "session-2",
      "message_count": 3,
      "last_activity": "2025-12-31T08:40:00.000Z",
      "current_agent": "architect"
    }
  ],
  "total": 2
}
```

### 3. Получить текущего агента

**Endpoint:** `GET /api/v1/agents/{session_id}/current`

**Описание:** Получить информацию о текущем активном агенте для сессии.

**Пример запроса:**
```bash
curl http://localhost:8001/api/v1/agents/my-session-123/current
```

**Пример ответа:**
```json
{
  "session_id": "my-session-123",
  "current_agent": "coder",
  "agent_history": [
    {
      "from": "orchestrator",
      "to": "coder",
      "reason": "User requested coding task",
      "timestamp": "2025-12-31T08:44:00.000Z"
    }
  ],
  "switch_count": 1
}
```

## Интеграция с IDE (Flutter Client)

### Настройка Dio + Retrofit + Freezed

#### 1. Добавьте зависимости в `pubspec.yaml`

```yaml
dependencies:
  dio: ^5.4.0
  retrofit: ^4.0.0
  freezed_annotation: ^2.4.1
  json_annotation: ^4.8.1

dev_dependencies:
  retrofit_generator: ^8.0.0
  build_runner: ^2.4.0
  freezed: ^2.4.6
  json_serializable: ^6.7.1
```

#### 2. Создайте модели данных с Freezed

**`lib/models/session_history.dart`:**
```dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'session_history.freezed.dart';
part 'session_history.g.dart';

@freezed
class ChatMessage with _$ChatMessage {
  const factory ChatMessage({
    required String role,
    required String content,
    String? name,
  }) = _ChatMessage;

  factory ChatMessage.fromJson(Map<String, dynamic> json) =>
      _$ChatMessageFromJson(json);
}

@freezed
class AgentSwitch with _$AgentSwitch {
  const factory AgentSwitch({
    required String from,
    required String to,
    required String reason,
    required String timestamp,
  }) = _AgentSwitch;

  factory AgentSwitch.fromJson(Map<String, dynamic> json) =>
      _$AgentSwitchFromJson(json);
}

@freezed
class SessionHistory with _$SessionHistory {
  const factory SessionHistory({
    @JsonKey(name: 'session_id') required String sessionId,
    required List<ChatMessage> messages,
    @JsonKey(name: 'message_count') required int messageCount,
    @JsonKey(name: 'last_activity') String? lastActivity,
    @JsonKey(name: 'current_agent') String? currentAgent,
    @JsonKey(name: 'agent_history') List<AgentSwitch>? agentHistory,
  }) = _SessionHistory;

  factory SessionHistory.fromJson(Map<String, dynamic> json) =>
      _$SessionHistoryFromJson(json);
}

@freezed
class SessionInfo with _$SessionInfo {
  const factory SessionInfo({
    @JsonKey(name: 'session_id') required String sessionId,
    @JsonKey(name: 'message_count') required int messageCount,
    @JsonKey(name: 'last_activity') required String lastActivity,
    @JsonKey(name: 'current_agent') String? currentAgent,
  }) = _SessionInfo;

  factory SessionInfo.fromJson(Map<String, dynamic> json) =>
      _$SessionInfoFromJson(json);
}

@freezed
class SessionListResponse with _$SessionListResponse {
  const factory SessionListResponse({
    required List<SessionInfo> sessions,
    required int total,
  }) = _SessionListResponse;

  factory SessionListResponse.fromJson(Map<String, dynamic> json) =>
      _$SessionListResponseFromJson(json);
}
```

**Преимущества Freezed:**
- ✅ Иммутабельные модели по умолчанию
- ✅ Автоматическая генерация `copyWith`, `==`, `hashCode`, `toString`
- ✅ Union types для сложных состояний
- ✅ Меньше boilerplate кода
- ✅ Лучшая type safety

#### 3. Создайте Retrofit API клиент

**`lib/api/agent_runtime_api.dart`:**
```dart
import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';
import '../models/session_history.dart';

part 'agent_runtime_api.g.dart';

@RestApi(baseUrl: 'http://localhost:8001/api/v1')
abstract class AgentRuntimeApi {
  factory AgentRuntimeApi(Dio dio, {String baseUrl}) = _AgentRuntimeApi;

  /// Получить историю сессии
  @GET('/sessions/{sessionId}/history')
  Future<SessionHistory> getSessionHistory(
    @Path('sessionId') String sessionId,
  );

  /// Получить список всех сессий
  @GET('/sessions')
  Future<SessionListResponse> listSessions();

  /// Получить текущего агента для сессии
  @GET('/agents/{sessionId}/current')
  Future<Map<String, dynamic>> getCurrentAgent(
    @Path('sessionId') String sessionId,
  );
}
```

#### 4. Сгенерируйте код

```bash
flutter pub run build_runner build --delete-conflicting-outputs
```

#### 5. Создайте сервис для работы с сессиями

**`lib/services/session_service.dart`:**
```dart
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../api/agent_runtime_api.dart';
import '../models/session_history.dart';

class SessionService {
  static const String _sessionIdKey = 'current_session_id';
  
  final AgentRuntimeApi _api;
  final SharedPreferences _prefs;
  
  String? _currentSessionId;
  
  SessionService({
    required AgentRuntimeApi api,
    required SharedPreferences prefs,
  })  : _api = api,
        _prefs = prefs;

  /// Инициализация - восстановление или создание сессии
  Future<void> initialize() async {
    _currentSessionId = _prefs.getString(_sessionIdKey);
    
    if (_currentSessionId != null) {
      final restored = await restoreSession(_currentSessionId!);
      if (!restored) {
        // Не удалось восстановить, создать новую
        await createNewSession();
      }
    } else {
      // Первый запуск
      await createNewSession();
    }
  }

  /// Восстановить сессию из базы данных
  Future<bool> restoreSession(String sessionId) async {
    try {
      final history = await _api.getSessionHistory(sessionId);
      
      print('Session restored: ${history.messageCount} messages');
      print('Current agent: ${history.currentAgent}');
      
      // Здесь можно вызвать callback для обновления UI
      // например: onSessionRestored?.call(history);
      
      return true;
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) {
        print('Session not found: $sessionId');
        return false;
      }
      print('Error restoring session: $e');
      return false;
    } catch (e) {
      print('Unexpected error restoring session: $e');
      return false;
    }
  }

  /// Создать новую сессию
  Future<void> createNewSession() async {
    _currentSessionId = _generateSessionId();
    await _prefs.setString(_sessionIdKey, _currentSessionId!);
    print('Created new session: $_currentSessionId');
  }

  /// Получить текущий session_id
  String? get currentSessionId => _currentSessionId;

  /// Получить список всех сессий
  Future<SessionListResponse> listAllSessions() async {
    return await _api.listSessions();
  }

  /// Получить полную историю текущей сессии
  Future<SessionHistory?> getCurrentSessionHistory() async {
    if (_currentSessionId == null) return null;
    
    try {
      return await _api.getSessionHistory(_currentSessionId!);
    } catch (e) {
      print('Error getting session history: $e');
      return null;
    }
  }

  /// Сбросить текущую сессию (создать новую)
  Future<void> resetSession() async {
    await createNewSession();
  }

  String _generateSessionId() {
    return 'session_${DateTime.now().millisecondsSinceEpoch}';
  }
}
```

#### 6. Настройте DI (например, с GetIt)

**`lib/di/service_locator.dart`:**
```dart
import 'package:dio/dio.dart';
import 'package:get_it/get_it.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../api/agent_runtime_api.dart';
import '../services/session_service.dart';

final getIt = GetIt.instance;

Future<void> setupServiceLocator() async {
  // Dio
  final dio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 30),
    receiveTimeout: const Duration(seconds: 30),
  ));
  
  // Добавить логирование (опционально)
  dio.interceptors.add(LogInterceptor(
    requestBody: true,
    responseBody: true,
  ));
  
  getIt.registerSingleton<Dio>(dio);

  // API клиент
  getIt.registerSingleton<AgentRuntimeApi>(
    AgentRuntimeApi(dio, baseUrl: 'http://localhost:8001/api/v1'),
  );

  // SharedPreferences
  final prefs = await SharedPreferences.getInstance();
  getIt.registerSingleton<SharedPreferences>(prefs);

  // Session Service
  getIt.registerSingleton<SessionService>(
    SessionService(
      api: getIt<AgentRuntimeApi>(),
      prefs: getIt<SharedPreferences>(),
    ),
  );
}
```

#### 7. Используйте в приложении

**`lib/main.dart`:**
```dart
import 'package:flutter/material.dart';
import 'di/service_locator.dart';
import 'services/session_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Настроить DI
  await setupServiceLocator();
  
  // Инициализировать сессию
  final sessionService = getIt<SessionService>();
  await sessionService.initialize();
  
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CodeLab IDE',
      home: ChatPage(),
    );
  }
}
```

**`lib/pages/chat_page.dart`:**
```dart
import 'package:flutter/material.dart';
import '../di/service_locator.dart';
import '../services/session_service.dart';
import '../models/session_history.dart';

class ChatPage extends StatefulWidget {
  @override
  _ChatPageState createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final SessionService _sessionService = getIt<SessionService>();
  List<ChatMessage> _messages = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() => _isLoading = true);
    
    try {
      final history = await _sessionService.getCurrentSessionHistory();
      
      if (history != null) {
        setState(() {
          _messages = history.messages
              .where((m) => m.role == 'user' || m.role == 'assistant')
              .toList();
        });
      }
    } catch (e) {
      print('Error loading history: $e');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('Chat - ${_sessionService.currentSessionId}'),
        actions: [
          IconButton(
            icon: Icon(Icons.refresh),
            onPressed: () async {
              await _sessionService.resetSession();
              await _loadHistory();
            },
          ),
        ],
      ),
      body: ListView.builder(
        itemCount: _messages.length,
        itemBuilder: (context, index) {
          final message = _messages[index];
          return ListTile(
            title: Text(message.role),
            subtitle: Text(message.content),
          );
        },
      ),
    );
  }
}
```

## Тестирование

Запустите тестовый скрипт для проверки персистентности:

```bash
cd codelab-ai-service/agent-runtime
uv run python test_persistence.py
```

Тест проверяет:
- ✅ Создание и сохранение сессий
- ✅ Добавление сообщений
- ✅ Переключение агентов
- ✅ Восстановление после "перезапуска"
- ✅ Удаление сессий

## Конфигурация

### Путь к базе данных

По умолчанию: `data/agent_runtime.db`

Можно изменить в [`app/services/database.py`](app/services/database.py):

```python
database = Database(db_url="sqlite:///custom/path/database.db")
```

### Очистка старых сессий

Автоматическая очистка сессий старше 24 часов:

```python
from app.services.database import get_db

db = get_db()
deleted_count = db.cleanup_old_sessions(max_age_hours=24)
print(f"Cleaned up {deleted_count} old sessions")
```

## Troubleshooting

### База данных не создается

Убедитесь, что директория `data/` существует и доступна для записи:

```bash
mkdir -p codelab-ai-service/agent-runtime/data
chmod 755 codelab-ai-service/agent-runtime/data
```

### Сессия не восстанавливается

1. Проверьте, что `session_id` совпадает
2. Проверьте логи: `grep "Loaded.*sessions" logs/agent-runtime.log`
3. Проверьте наличие записи в БД:
   ```bash
   sqlite3 data/agent_runtime.db "SELECT session_id FROM sessions;"
   ```

### Ошибка подключения из Flutter

Убедитесь, что:
- Agent runtime запущен на `localhost:8001`
- Для Android эмулятора используйте `10.0.2.2:8001` вместо `localhost:8001`
- Для iOS симулятора `localhost:8001` должен работать

## Заключение

Персистентность сессий значительно улучшает пользовательский опыт, позволяя:
- Продолжать работу после перезапуска IDE
- Сохранять контекст между сессиями
- Анализировать историю взаимодействий
- Восстанавливать состояние после сбоев

Все изменения обратно совместимы - существующий код продолжит работать без модификаций.
