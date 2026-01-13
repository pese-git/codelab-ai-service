# Benchmark Test Project

Этот Flutter проект используется для автоматической проверки выполнения benchmark задач.

## Назначение

- Служит рабочей директорией для агентов
- Позволяет проверять создание/изменение файлов
- Используется для запуска `dart analyze` и `flutter test`
- Валидирует результаты выполнения задач

## Структура

```
test_project/
├── lib/              # Исходный код (создается агентами)
├── test/             # Тесты (создаются агентами)
├── docs/             # Документация (создается агентами)
└── pubspec.yaml      # Зависимости проекта
```

## Использование

### С автоматической проверкой

```bash
cd codelab-ai-service/agent-runtime
uv run python ../benchmark/scripts/run_poc_experiment_integrated.py \
  --mode multi-agent \
  --task-id task_001 \
  --enable-validation
```

### Без проверки (быстрее)

```bash
cd codelab-ai-service/agent-runtime
uv run python ../benchmark/scripts/run_poc_experiment_integrated.py \
  --mode multi-agent \
  --task-id task_001
```

## Auto-check валидаторы

### file_exists
Проверяет существование файла:
```yaml
auto_check:
  - type: "file_exists"
    params:
      path: "lib/widgets/user_card.dart"
```

### syntax_valid
Проверяет синтаксис через `dart analyze`:
```yaml
auto_check:
  - type: "syntax_valid"
    params:
      path: "lib/widgets/user_card.dart"
```

### contains_text
Проверяет наличие текста в файле:
```yaml
auto_check:
  - type: "contains_text"
    params:
      path: "lib/models/user.dart"
      text: "String getFullName()"
```

### test_passes
Запускает тесты через `flutter test`:
```yaml
auto_check:
  - type: "test_passes"
    params:
      pattern: "calculator_test.dart"
```

## Очистка проекта

После каждого эксперимента рекомендуется очистить созданные файлы:

```bash
cd codelab-ai-service/benchmark/test_project
git clean -fdx lib/ test/ docs/
```

Или сбросить весь проект:

```bash
cd codelab-ai-service/benchmark
rm -rf test_project
flutter create test_project --empty
```

## Примечания

- Проект создается с `--empty` флагом (минимальная структура)
- Агенты создают файлы в процессе выполнения задач
- Валидация запускается после завершения задачи
- Результаты валидации сохраняются в метриках
