# Технологический стек

## v0.2.0

- Flutter — Windows desktop UI;
- Dart `^3.11.5` — ограничение `ui/musicark_ui/pubspec.yaml`;
- Python `>=3.10` — core/provider runtime;
- SQLite — локальный snapshot/cache библиотеки;
- `yandex-music==3.0.0` — Yandex Music provider integration;
- `keyring==25.7.0` — доступ к системному credential store для сохранённого токена;
- `mutagen>=1.47.0` — legacy metadata subsystem, пока не подключён к v0.2 UI;
- `requests>=2.32.0` — Python HTTP dependency.

## Почему стек не переписывается

Проект уже подтвердил рабочий end-to-end Yandex provider на Python и Windows Flutter runner. v0.2 расширяет этот вертикальный срез persistence-слоем вместо добавления нового UI/runtime стека.

## Persistence boundary

### Секреты

Yandex token хранится через `keyring` в системном credential backend. Он не записывается в SQLite.

### Library cache

SQLite хранит только нормализованный snapshot полей, необходимых UI. Полный raw provider payload в persistent liked-cache не сохраняется.

## Зафиксированные версии

Фактические ограничения находятся в:

- `pyproject.toml`;
- `requirements-yandex.txt`;
- `ui/musicark_ui/pubspec.yaml`.

## Что сознательно не входит в v0.2 UI

- download system;
- matching engine;
- sync planner/executor;
- metadata editor;
- local library;
- playlists.

## Ограничение среды

Release exe пока не содержит Python runtime. Для запуска нужен checkout MusicArk и Python environment с установленными зависимостями. Устранение этого ограничения — цель отдельной версии v0.3.0.

## Сборка

```powershell
cd ui\musicark_ui
flutter build windows --release
```

## Запуск

```powershell
flutter run -d windows
```

## Тестирование

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
cd ui\musicark_ui
flutter analyze
flutter test
```
