# Test Project Source Files

Этот проект содержит базовые файлы с намеренными ошибками и недостающим функционалом для тестирования benchmark задач.

## Существующие файлы

### Models
- `models/user.dart` - User модель (task_002: добавить getFullName())

### Screens
- `screens/home_screen.dart` - Экран с синтаксической ошибкой (task_003: исправить)
- `screens/product_list_screen.dart` - Экран с null safety ошибкой (task_008: исправить)

### Constants
- `constants/colors.dart` - Цветовые константы (task_005: добавить primaryColor)

### Utils
- `utils/calculator.dart` - Калькулятор (task_015: написать тесты)

## Файлы, которые будут созданы агентами

### Widgets (task_001, task_006, task_007, и др.)
- `widgets/user_card.dart`
- `widgets/login_form.dart`
- `widgets/animated_widget.dart`
- `widgets/chart_painter.dart`
- `widgets/searchable_list.dart`
- `widgets/responsive_layout.dart`
- `widgets/large_list.dart`

### BLoCs (task_007, task_012, task_018, task_024)
- `blocs/counter_bloc.dart`
- `blocs/state_management.dart`
- `blocs/infinite_loop_bloc.dart`

### Services (task_012, task_031)
- `services/api_service.dart`
- `services/external_api_service.dart`
- `services/concurrent_service.dart`

### Repositories (task_014)
- `repositories/user_repository.dart`

### Hooks (task_017)
- `hooks/use_form.dart`

### Localization (task_025)
- `l10n/app_localizations.dart`
- `l10n/app_en.arb`

### Legacy Code (task_039)
- `legacy/refactored_code.dart`

### Best Practices (task_038)
- `best_practices/code.dart`

### Plugins (task_033)
- `../packages/my_plugin/lib/my_plugin.dart`

## Документация (Architecture задачи)

Создается в `docs/`:
- `architecture/offline_design.md` (task_010)
- `architecture/repository_design.md` (task_014)
- `architecture/navigation_design.md` (task_021)
- `architecture/microservices_design.md` (task_026)
- `architecture/caching_strategy.md` (task_030)
- `architecture/enterprise_design.md` (task_036)
- `security/security_design.md` (task_034)
- `testing/testing_strategy.md` (task_040)
- `performance_analysis.md` (task_028)
- `null_safety_explanation.md` (task_029)
- `feature_implementation_guide.md` (task_035)
- `debugging_guide.md` (task_037)

## Тесты

Создаются в `test/`:
- `calculator_test.dart` (task_015)
- `utils_test.dart` (task_022)
- `module_test.dart` (task_027)

## Примечания

- Файлы с ошибками намеренно содержат баги для debug задач
- Агенты должны создавать недостающие файлы
- Валидация проверяет результаты через auto_check правила
