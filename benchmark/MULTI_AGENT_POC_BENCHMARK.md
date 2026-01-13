# MULTI_AGENT_POC_BENCHMARK

## 1. Введение

### Назначение benchmark suite
Этот набор тестовых задач предназначен для оценки эффективности Multi-Agent системы по сравнению с Single-Agent подходом в контексте разработки Flutter приложений. Benchmark позволяет измерить ключевые метрики: Task Success Rate (TSR), Time To Useful Answer (TTUA), Hallucination Rate и Cost per Successful Task.

### Принципы отбора задач
- **Реалистичность**: Задачи основаны на типичных сценариях разработки Flutter приложений
- **Воспроизводимость**: Каждая задача имеет четкие критерии успеха и ожидаемые результаты
- **Разнообразие**: Покрытие разных типов задач и уровней сложности
- **Измеримость**: Возможность автоматической проверки результатов
- **Баланс**: Равномерное распределение по категориям и типам задач

### Категории задач
- **Категория A (Простые)**: 1-2 шага, без переключения контекста, решение за минуты
- **Категория B (Средние)**: 3-5 шагов, возможно переключение агентов, умеренная сложность
- **Категория C (Сложные)**: Множественные шаги, координация агентов, комплексные задачи
- **Категория D (Специализированные)**: Задачи, требующие конкретного типа агента

## 2. Категории задач

### Категория A: Простые задачи (10 задач)
Задачи, решаемые в 1-2 шага без переключения контекста. Подходят для оценки базовой функциональности агентов.

### Категория B: Средние задачи (15 задач)
Задачи средней сложности, требующие 3-5 шагов и потенциального переключения между агентами.

### Категория C: Сложные задачи (10 задач)
Комплексные задачи, требующие планирования, множественных шагов и эффективной координации между агентами.

### Категория D: Специализированные задачи (5 задач)
Задачи, явно требующие конкретного агента для достижения оптимального результата.

## 3. Формат описания задачи

Каждая задача описывается в следующем YAML формате:

```yaml
id: task_001
category: simple|medium|complex|specialized
type: coding|architecture|debug|question|mixed
title: "Краткое название"
description: "Детальное описание задачи"
expected_agent: "Какой агент должен быть выбран (для multi-agent)"
expected_files: ["список файлов, которые должны быть созданы/изменены"]
success_criteria:
  - "Критерий 1"
  - "Критерий 2"
auto_check:
  - type: "file_exists|syntax_valid|test_passes|contains_text"
    params: {...}
estimated_time: "1-5 минут"
complexity_score: 1-10
```

## 4. Список задач

### Категория A: Простые задачи

```yaml
id: task_001
category: simple
type: coding
title: "Создание простого StatelessWidget"
description: "Создать новый файл lib/widgets/user_card.dart с StatelessWidget UserCard, который принимает параметры name (String) и avatar (String) и отображает их в Column с CircleAvatar и Text"
expected_agent: "Coder"
expected_files: ["lib/widgets/user_card.dart"]
success_criteria:
  - "Файл создан с правильной структурой"
  - "Виджет компилируется без ошибок"
  - "Параметры корректно используются в UI"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/widgets/user_card.dart"}
  - type: "syntax_valid"
    params: {"path": "lib/widgets/user_card.dart"}
estimated_time: "1-2 минуты"
complexity_score: 2
```

```yaml
id: task_002
category: simple
type: coding
title: "Добавление метода в класс"
description: "В файле lib/models/user.dart добавить метод String getFullName() который возвращает '$firstName $lastName'"
expected_agent: "Coder"
expected_files: ["lib/models/user.dart"]
success_criteria:
  - "Метод добавлен с правильной сигнатурой"
  - "Реализация корректна"
  - "Код компилируется"
auto_check:
  - type: "contains_text"
    params: {"path": "lib/models/user.dart", "text": "String getFullName()"}
  - type: "syntax_valid"
    params: {"path": "lib/models/user.dart"}
estimated_time: "1 минута"
complexity_score: 1
```

```yaml
id: task_003
category: simple
type: debug
title: "Исправление синтаксической ошибки"
description: "В файле lib/screens/home_screen.dart исправить отсутствующую точку с запятой в строке 25 после вызова setState(()"
expected_agent: "Debug"
expected_files: ["lib/screens/home_screen.dart"]
success_criteria:
  - "Синтаксическая ошибка исправлена"
  - "Код компилируется без ошибок"
auto_check:
  - type: "syntax_valid"
    params: {"path": "lib/screens/home_screen.dart"}
estimated_time: "30 секунд"
complexity_score: 1
```

```yaml
id: task_004
category: simple
type: question
title: "Поиск определения функции"
description: "Найти определение функции buildUserList в проекте и указать в каком файле и на какой строке оно находится"
expected_agent: "Ask"
expected_files: []
success_criteria:
  - "Правильно указан файл и строка"
  - "Функция существует в указанном месте"
auto_check:
  - type: "contains_text"
    params: {"path": "expected_file", "text": "buildUserList"}
estimated_time: "1 минута"
complexity_score: 2
```

```yaml
id: task_005
category: simple
type: coding
title: "Создание константы"
description: "В файле lib/constants/colors.dart добавить константу const Color primaryColor = Color(0xFF6200EE)"
expected_agent: "Coder"
expected_files: ["lib/constants/colors.dart"]
success_criteria:
  - "Константа добавлена с правильным значением"
  - "Файл компилируется"
auto_check:
  - type: "contains_text"
    params: {"path": "lib/constants/colors.dart", "text": "primaryColor"}
  - type: "syntax_valid"
    params: {"path": "lib/constants/colors.dart"}
estimated_time: "1 минута"
complexity_score: 1
```

```yaml
id: task_006
category: simple
type: coding
title: "Добавление импорта"
description: "В файле lib/screens/profile_screen.dart добавить импорт 'package:flutter/material.dart' если его нет"
expected_agent: "Coder"
expected_files: ["lib/screens/profile_screen.dart"]
success_criteria:
  - "Необходимый импорт добавлен"
  - "Код компилируется"
auto_check:
  - type: "contains_text"
    params: {"path": "lib/screens/profile_screen.dart", "text": "import 'package:flutter/material.dart'"}
estimated_time: "30 секунд"
complexity_score: 1
```

```yaml
id: task_007
category: simple
type: debug
title: "Исправление опечатки в строке"
description: "В файле lib/utils/helpers.dart исправить 'recieve' на 'receive' в комментарии на строке 15"
expected_agent: "Debug"
expected_files: ["lib/utils/helpers.dart"]
success_criteria:
  - "Опечатка исправлена"
auto_check:
  - type: "contains_text"
    params: {"path": "lib/utils/helpers.dart", "text": "receive"}
estimated_time: "30 секунд"
complexity_score: 1
```

```yaml
id: task_008
category: simple
type: question
title: "Подсчет строк кода"
description: "Посчитать количество строк в файле lib/main.dart без учета пустых строк и комментариев"
expected_agent: "Ask"
expected_files: []
success_criteria:
  - "Правильный подсчет строк"
auto_check:
  - type: "custom_check"
    params: {"expected": "calculated_lines"}
estimated_time: "2 минуты"
complexity_score: 2
```

```yaml
id: task_009
category: simple
type: coding
title: "Создание enum"
description: "Создать enum UserRole в файле lib/models/user_role.dart со значениями admin, user, moderator"
expected_agent: "Coder"
expected_files: ["lib/models/user_role.dart"]
success_criteria:
  - "Enum создан с правильными значениями"
  - "Код компилируется"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/models/user_role.dart"}
  - type: "syntax_valid"
    params: {"path": "lib/models/user_role.dart"}
estimated_time: "1 минута"
complexity_score: 2
```

```yaml
id: task_010
category: simple
type: coding
title: "Добавление параметра в конструктор"
description: "В классе Product в файле lib/models/product.dart добавить параметр price (double) в конструктор"
expected_agent: "Coder"
expected_files: ["lib/models/product.dart"]
success_criteria:
  - "Параметр добавлен в конструктор"
  - "Класс компилируется"
auto_check:
  - type: "contains_text"
    params: {"path": "lib/models/product.dart", "text": "double price"}
  - type: "syntax_valid"
    params: {"path": "lib/models/product.dart"}
estimated_time: "1 минута"
complexity_score: 2
```

### Категория B: Средние задачи

```yaml
id: task_011
category: medium
type: coding
title: "Создание формы с валидацией"
description: "Создать StatefulWidget LoginForm с полями email и password, добавить базовую валидацию и кнопку входа"
expected_agent: "Coder"
expected_files: ["lib/widgets/login_form.dart"]
success_criteria:
  - "Форма создана с необходимыми полями"
  - "Валидация работает"
  - "Виджет компилируется"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/widgets/login_form.dart"}
  - type: "syntax_valid"
    params: {"path": "lib/widgets/login_form.dart"}
estimated_time: "5 минут"
complexity_score: 4
```

```yaml
id: task_012
category: medium
type: coding
title: "Добавление BLoC для управления состоянием"
description: "Создать CounterBloc в lib/blocs/counter_bloc.dart с событиями increment/decrement и состояниями для счетчика"
expected_agent: "Coder"
expected_files: ["lib/blocs/counter_bloc.dart"]
success_criteria:
  - "BLoC создан с правильными событиями и состояниями"
  - "Логика работы корректна"
  - "Код компилируется"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/blocs/counter_bloc.dart"}
  - type: "syntax_valid"
    params: {"path": "lib/blocs/counter_bloc.dart"}
estimated_time: "7 минут"
complexity_score: 5
```

```yaml
id: task_013
category: medium
type: debug
title: "Исправление null pointer exception"
description: "В файле lib/screens/product_list_screen.dart исправить ошибку где product может быть null при доступе к product.name"
expected_agent: "Debug"
expected_files: ["lib/screens/product_list_screen.dart"]
success_criteria:
  - "Null check добавлен"
  - "Ошибка исправлена"
auto_check:
  - type: "syntax_valid"
    params: {"path": "lib/screens/product_list_screen.dart"}
estimated_time: "3 минуты"
complexity_score: 3
```

```yaml
id: task_014
category: medium
type: mixed
title: "Рефакторинг виджета с тестами"
description: "Разбить большой виджет в lib/widgets/complex_form.dart на меньшие компоненты и добавить unit тесты"
expected_agent: "Coder + Debug"
expected_files: ["lib/widgets/complex_form.dart", "test/widgets/complex_form_test.dart"]
success_criteria:
  - "Виджет разбит на компоненты"
  - "Тесты написаны и проходят"
auto_check:
  - type: "test_passes"
    params: {"pattern": "*complex_form_test.dart"}
estimated_time: "10 минут"
complexity_score: 6
```

```yaml
id: task_015
category: medium
type: architecture
title: "Создание сервиса для API вызовов"
description: "Создать ApiService класс в lib/services/api_service.dart для GET/POST запросов с обработкой ошибок"
expected_agent: "Coder"
expected_files: ["lib/services/api_service.dart"]
success_criteria:
  - "Сервис создан с методами для HTTP запросов"
  - "Обработка ошибок реализована"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/services/api_service.dart"}
  - type: "syntax_valid"
    params: {"path": "lib/services/api_service.dart"}
estimated_time: "8 минут"
complexity_score: 5
```

```yaml
id: task_016
category: medium
type: coding
title: "Добавление локализации"
description: "Добавить поддержку английского и русского языков в приложение, создать файлы локализации"
expected_agent: "Coder"
expected_files: ["lib/l10n/app_en.arb", "lib/l10n/app_ru.arb"]
success_criteria:
  - "Файлы локализации созданы"
  - "Ключи определены"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/l10n/app_en.arb"}
  - type: "file_exists"
    params: {"path": "lib/l10n/app_ru.arb"}
estimated_time: "6 минут"
complexity_score: 4
```

```yaml
id: task_017
category: medium
type: debug
title: "Исправление утечки памяти"
description: "В файле lib/screens/chat_screen.dart исправить утечку памяти в StreamSubscription, добавить dispose"
expected_agent: "Debug"
expected_files: ["lib/screens/chat_screen.dart"]
success_criteria:
  - "Subscription отменен в dispose"
  - "Утечка исправлена"
auto_check:
  - type: "contains_text"
    params: {"path": "lib/screens/chat_screen.dart", "text": "subscription.cancel()"}
estimated_time: "4 минуты"
complexity_score: 4
```

```yaml
id: task_018
category: medium
type: mixed
title: "Интеграция с Provider"
description: "Создать ChangeNotifier для управления темой приложения и интегрировать его в MaterialApp"
expected_agent: "Coder"
expected_files: ["lib/providers/theme_provider.dart"]
success_criteria:
  - "Provider создан"
  - "Интегрирован в MaterialApp"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/providers/theme_provider.dart"}
  - type: "syntax_valid"
    params: {"path": "lib/providers/theme_provider.dart"}
estimated_time: "6 минут"
complexity_score: 5
```

```yaml
id: task_019
category: medium
type: question
title: "Анализ архитектуры проекта"
description: "Проанализировать текущую архитектуру проекта и предложить улучшения для scalability"
expected_agent: "Architect"
expected_files: []
success_criteria:
  - "Архитектура проанализирована"
  - "Предложения сформулированы"
auto_check:
  - type: "custom_check"
    params: {"type": "architecture_analysis"}
estimated_time: "8 минут"
complexity_score: 6
```

```yaml
id: task_020
category: medium
type: coding
title: "Создание кастомного виджета"
description: "Создать AnimatedButton виджет с анимацией нажатия и конфигурируемыми цветами"
expected_agent: "Coder"
expected_files: ["lib/widgets/animated_button.dart"]
success_criteria:
  - "Виджет создан с анимацией"
  - "Параметры конфигурируемы"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/widgets/animated_button.dart"}
  - type: "syntax_valid"
    params: {"path": "lib/widgets/animated_button.dart"}
estimated_time: "7 минут"
complexity_score: 5
```

```yaml
id: task_021
category: medium
type: debug
title: "Исправление race condition"
description: "В файле lib/services/data_service.dart исправить race condition при одновременных запросах к кэшу"
expected_agent: "Debug"
expected_files: ["lib/services/data_service.dart"]
success_criteria:
  - "Race condition исправлено"
  - "Безопасный доступ к shared ресурсам"
auto_check:
  - type: "syntax_valid"
    params: {"path": "lib/services/data_service.dart"}
estimated_time: "5 минут"
complexity_score: 5
```

```yaml
id: task_022
category: medium
type: mixed
title: "Добавление offline поддержки"
description: "Добавить кэширование данных в SharedPreferences для работы без интернета"
expected_agent: "Coder"
expected_files: ["lib/services/cache_service.dart"]
success_criteria:
  - "Кэширование реализовано"
  - "Работает без интернета"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/services/cache_service.dart"}
  - type: "syntax_valid"
    params: {"path": "lib/services/cache_service.dart"}
estimated_time: "9 минут"
complexity_score: 6
```

```yaml
id: task_023
category: medium
type: architecture
title: "Проектирование навигации"
description: "Спроектировать систему навигации с deep linking и state management для большого приложения"
expected_agent: "Architect"
expected_files: ["lib/navigation/router.dart"]
success_criteria:
  - "Router спроектирован"
  - "Deep linking поддерживается"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/navigation/router.dart"}
estimated_time: "10 минут"
complexity_score: 7
```

```yaml
id: task_024
category: medium
type: coding
title: "Создание модели данных"
description: "Создать Freezed модель для User с вложенными объектами Address и Preferences"
expected_agent: "Coder"
expected_files: ["lib/models/user.freezed.dart"]
success_criteria:
  - "Модель создана с Freezed"
  - "Вложенные объекты определены"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/models/user.freezed.dart"}
  - type: "syntax_valid"
    params: {"path": "lib/models/user.freezed.dart"}
estimated_time: "6 минут"
complexity_score: 4
```

```yaml
id: task_025
category: medium
type: debug
title: "Исправление UI бага"
description: "В файле lib/widgets/list_view.dart исправить баг с неправильным отображением элементов при прокрутке"
expected_agent: "Debug"
expected_files: ["lib/widgets/list_view.dart"]
success_criteria:
  - "Баг с прокруткой исправлен"
  - "Элементы отображаются корректно"
auto_check:
  - type: "syntax_valid"
    params: {"path": "lib/widgets/list_view.dart"}
estimated_time: "5 минут"
complexity_score: 4
```

### Категория C: Сложные задачи

```yaml
id: task_026
category: complex
type: mixed
title: "Миграция с Provider на Riverpod"
description: "Полная миграция состояния приложения с Provider на Riverpod включая все провайдеры и consumers"
expected_agent: "Architect + Coder"
expected_files: ["lib/providers/*", "lib/riverpod/*"]
success_criteria:
  - "Все провайдеры мигрированы"
  - "Приложение работает корректно"
  - "Тесты проходят"
auto_check:
  - type: "test_passes"
    params: {"pattern": "*"}
estimated_time: "45 минут"
complexity_score: 9
```

```yaml
id: task_027
category: complex
type: architecture
title: "Проектирование offline-first архитектуры"
description: "Спроектировать полную offline-first архитектуру с синхронизацией, conflict resolution и cache management"
expected_agent: "Architect"
expected_files: ["docs/architecture/offline_design.md"]
success_criteria:
  - "Архитектура спроектирована"
  - "Все аспекты учтены"
auto_check:
  - type: "file_exists"
    params: {"path": "docs/architecture/offline_design.md"}
estimated_time: "30 минут"
complexity_score: 8
```

```yaml
id: task_028
category: complex
type: coding
title: "Создание комплексного экрана"
description: "Создать экран интернет-магазина с каталогом, корзиной, поиском и фильтрами с полной функциональностью"
expected_agent: "Coder + Architect"
expected_files: ["lib/screens/shop_screen.dart", "lib/widgets/*", "lib/models/*"]
success_criteria:
  - "Экран полностью функционален"
  - "Все фичи работают"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/screens/shop_screen.dart"}
  - type: "syntax_valid"
    params: {"path": "lib/screens/shop_screen.dart"}
estimated_time: "60 минут"
complexity_score: 10
```

```yaml
id: task_029
category: complex
type: debug
title: "Комплексная отладка производительности"
description: "Найти и исправить все bottlenecks производительности в приложении, оптимизировать рендеринг и память"
expected_agent: "Debug"
expected_files: ["lib/*"]
success_criteria:
  - "Производительность улучшена"
  - "Bottlenecks устранены"
auto_check:
  - type: "custom_check"
    params: {"type": "performance_improved"}
estimated_time: "40 минут"
complexity_score: 9
```

```yaml
id: task_030
category: complex
type: mixed
title: "Интеграция с внешним API"
description: "Интегрировать REST API с аутентификацией, pagination, error handling и кэшированием"
expected_agent: "Coder + Debug"
expected_files: ["lib/services/api_client.dart", "lib/repositories/*"]
success_criteria:
  - "API полностью интегрирован"
  - "Все edge cases обработаны"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/services/api_client.dart"}
  - type: "syntax_valid"
    params: {"path": "lib/services/api_client.dart"}
estimated_time: "50 минут"
complexity_score: 9
```

```yaml
id: task_031
category: complex
type: architecture
title: "Архитектурный рефакторинг"
description: "Провести полный рефакторинг архитектуры для поддержки microservices подхода с разделением на модули"
expected_agent: "Architect"
expected_files: ["packages/*", "docs/architecture/refactoring_plan.md"]
success_criteria:
  - "Архитектура рефакторена"
  - "Модули разделены"
auto_check:
  - type: "file_exists"
    params: {"path": "docs/architecture/refactoring_plan.md"}
estimated_time: "35 минут"
complexity_score: 8
```

```yaml
id: task_032
category: complex
type: coding
title: "Создание SDK для внешних разработчиков"
description: "Создать Flutter SDK с публичным API, документацией, примерами и CI/CD pipeline"
expected_agent: "Coder + Architect"
expected_files: ["packages/sdk/*", "README.md", "examples/*"]
success_criteria:
  - "SDK создан и документирован"
  - "Примеры работают"
auto_check:
  - type: "file_exists"
    params: {"path": "packages/sdk/pubspec.yaml"}
  - type: "syntax_valid"
    params: {"path": "packages/sdk/lib/sdk.dart"}
estimated_time: "55 минут"
complexity_score: 10
```

```yaml
id: task_033
category: complex
type: debug
title: "Отладка многопоточности"
description: "Исправить все race conditions и deadlocks в многопоточном коде с isolate communication"
expected_agent: "Debug"
expected_files: ["lib/services/*", "lib/utils/concurrency.dart"]
success_criteria:
  - "Все concurrency issues исправлены"
  - "Код thread-safe"
auto_check:
  - type: "syntax_valid"
    params: {"path": "lib/utils/concurrency.dart"}
estimated_time: "45 минут"
complexity_score: 9
```

```yaml
id: task_034
category: complex
type: mixed
title: "Добавление аналитики и мониторинга"
description: "Интегрировать Firebase Analytics, Crashlytics и performance monitoring с custom events"
expected_agent: "Coder"
expected_files: ["lib/services/analytics_service.dart", "lib/services/crash_service.dart"]
success_criteria:
  - "Аналитика интегрирована"
  - "Мониторинг работает"
auto_check:
  - type: "file_exists"
    params: {"path": "lib/services/analytics_service.dart"}
  - type: "syntax_valid"
    params: {"path": "lib/services/analytics_service.dart"}
estimated_time: "40 минут"
complexity_score: 8
```

```yaml
id: task_035
category: complex
type: architecture
title: "Проектирование CI/CD pipeline"
description: "Спроектировать полный CI/CD pipeline с automated testing, code quality, deployment и monitoring"
expected_agent: "Architect"
expected_files: [".github/workflows/*", "docs/ci_cd_design.md"]
success_criteria:
  - "Pipeline спроектирован"
  - "Все этапы покрыты"
auto_check:
  - type: "file_exists"
    params: {"path": ".github/workflows/ci.yml"}
estimated_time: "30 минут"
complexity_score: 7
```

### Категория D: Специализированные задачи

```yaml
id: task_036
category: specialized
type: architecture
title: "Проектирование масштабируемой архитектуры"
description: "Спроектировать архитектуру для приложения с 1M+ пользователей с учетом scalability, reliability и maintainability"
expected_agent: "Architect"
expected_files: ["docs/architecture/scalable_design.md"]
success_criteria:
  - "Архитектура спроектирована"
  - "Все требования учтены"
auto_check:
  - type: "file_exists"
    params: {"path": "docs/architecture/scalable_design.md"}
estimated_time: "25 минут"
complexity_score: 8
```

```yaml
id: task_037
category: specialized
type: debug
title: "Отладка production issues"
description: "Анализировать crash reports и performance issues в production, найти root causes и предложить fixes"
expected_agent: "Debug"
expected_files: ["docs/debug/production_issues_analysis.md"]
success_criteria:
  - "Issues проанализированы"
  - "Root causes найдены"
auto_check:
  - type: "file_exists"
    params: {"path": "docs/debug/production_issues_analysis.md"}
estimated_time: "35 минут"
complexity_score: 9
```

```yaml
id: task_038
category: specialized
type: question
title: "Техническое интервью по Flutter"
description: "Провести техническое интервью кандидата на позицию Senior Flutter Developer, оценить знания и навыки"
expected_agent: "Ask"
expected_files: ["docs/interview/flutter_senior_interview.md"]
success_criteria:
  - "Вопросы подготовлены"
  - "Критерии оценки определены"
auto_check:
  - type: "file_exists"
    params: {"path": "docs/interview/flutter_senior_interview.md"}
estimated_time: "20 минут"
complexity_score: 6
```

```yaml
id: task_039
category: specialized
type: architecture
title: "Анализ конкурентов"
description: "Проанализировать архитектуру и технический стек основных конкурентов, выявить strengths и weaknesses"
expected_agent: "Architect"
expected_files: ["docs/analysis/competitor_analysis.md"]
success_criteria:
  - "Конкуренты проанализированы"
  - "Сравнение проведено"
auto_check:
  - type: "file_exists"
    params: {"path": "docs/analysis/competitor_analysis.md"}
estimated_time: "30 минут"
complexity_score: 7
```

```yaml
id: task_040
category: specialized
type: debug
title: "Performance profiling и оптимизация"
description: "Провести глубокий performance profiling всего приложения и оптимизировать критические bottlenecks"
expected_agent: "Debug"
expected_files: ["docs/performance/profiling_report.md"]
success_criteria:
  - "Profiling проведен"
  - "Оптимизации применены"
auto_check:
  - type: "file_exists"
    params: {"path": "docs/performance/profiling_report.md"}
estimated_time: "40 минут"
complexity_score: 9
```

## 5. Распределение задач по типам

- **Coding задачи**: 16 (40%) - task_001,002,005,006,009,010,011,012,015,016,018,020,024,026,028,032
- **Architecture задачи**: 8 (20%) - task_019,023,027,031,035,036,039
- **Debug задачи**: 8 (20%) - task_003,007,013,017,021,025,029,033,037,040
- **Question задачи**: 4 (10%) - task_004,008,038
- **Mixed задачи**: 4 (10%) - task_014,022,030,034

Всего: 40 задач

---

**Создано:** Architect Mode  
**Дата:** 2026-01-12  
**Статус:** Готов к использованию