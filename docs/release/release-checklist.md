# Release checklist

Публичный релиз v0.2.0 не создаётся, пока не выполнены пункты ниже.

```text
[ ] Python tests проходят.
[ ] flutter analyze проходит.
[ ] flutter test проходит.
[ ] flutter build windows --release проходит.
[ ] Release exe запускается из checkout.
[ ] keyring использует secure Windows backend.
[ ] Первый реальный Yandex login проходит.
[ ] Token не присутствует в SQLite/config/logs/argv.
[ ] Повторный запуск не требует token.
[ ] Cached library показывается до/при failed refresh.
[ ] Offline launch с существующим cache проверен.
[ ] Добавление Liked membership проверено.
[ ] Удаление Liked membership проверено.
[ ] Search title/artist/album проверен.
[ ] Sort original/title/artist проверен.
[ ] Logout удаляет credential и cache.
[ ] README.md и README_EN.md синхронизированы.
[ ] CHANGELOG.md обновлён.
[ ] Ограничение bundled Python явно указано.
```
