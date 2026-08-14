# Технологический стек

## Выбранный стек

- Flutter — Windows desktop UI;
- Dart `^3.11.5` — ограничение текущего `pubspec.yaml`;
- Python `>=3.10` — core/provider runtime;
- `yandex-music==3.0.0` — текущая закреплённая интеграционная зависимость.

## Почему выбран именно он

Проект уже содержит рабочую Yandex provider-реализацию на Python и Windows Flutter runner. Перезапуск использует эти части, а не добавляет новый стек.

## Что сознательно не используем

В v0.1.0 для основного сценария не используются SQLite, sync planner, download system и metadata engine.

## Зафиксированные версии

Фактические ограничения находятся в:

- `pyproject.toml`;
- `requirements-yandex.txt`;
- `ui/musicark_ui/pubspec.yaml`.

## Ограничения среды

Release exe пока не содержит Python runtime. Для запуска нужен доступ к исходному checkout и Python с установленным MusicArk.

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
