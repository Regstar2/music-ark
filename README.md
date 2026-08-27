# MusicArk

**Русский** · [English](README_EN.md)

**Версия кода: 1.0.0**  
**SQLite schema: 1.9.0**  
**Платформа: Windows x64**

MusicArk — desktop-приложение для управления локальной музыкальной коллекцией и её сопоставления с библиотекой Яндекс Музыки. Основная задача проекта — помочь сохранить целостность коллекции: найти отсутствующие локально треки, обнаружить требующие проверки версии, восстановить метаданные и выполнять только явно подтверждённые действия.

> `v1.0.0` — release-freeze версия первого публичного релиза. Исходники могут содержать финальные release-правки до появления тега и GitHub Release; наличие версии `1.0.0` в коде само по себе не означает, что релиз уже опубликован.

## Что умеет MusicArk

- вход в Яндекс Музыку через пользовательский токен без хранения токена в репозитории;
- cache-first просмотр любимых треков, плейлистов и понравившихся альбомов;
- индексирование нескольких локальных папок без изменения исходных файлов во время обычного Scan;
- Identity Matching между треками Яндекс Музыки и локальными файлами;
- отдельный Variant-анализ записи/версии и пользовательские метки `ORIGINAL / CENSORED`;
- Coverage / Missing для поиска отсутствующих и требующих проверки треков;
- очередь загрузок с Wanted, retry/cancel/remove и массовыми действиями;
- встроенное воспроизведение локальных и подготовленных Yandex-треков;
- Metadata Editor для безопасной записи MP3/ID3, artwork и подтверждённого связывания с Yandex identity;
- ручная загрузка собственных/разрешённых MP3 в Яндекс Музыку и recovery workflows;
- Controlled Sync с явным планом и подтверждением перед применением;
- System / Direct / Custom proxy network modes;
- RU/EN интерфейс, System/Light/Dark theme;
- portable Windows package, per-user Inno Setup installer, SHA-256 и проверяемый update manifest.

## Основной цикл

```text
Yandex Library = желаемая коллекция
        ↓
Local Library = фактические локальные файлы
        ↓
Identity Matching + Variant + Coverage
        ↓
Missing / Wanted
        ↓
Download / Metadata / подтверждённые Sync или Upload действия
```

MusicArk специально разделяет **identity**, **metadata**, **variant** и **coverage**. Высокая похожесть названий сама по себе не превращается в подтверждённое совпадение.

## Безопасность локальной коллекции

Обычные Scan, Matching, Variant, Coverage и просмотр Sync-плана не изменяют пользовательские аудиофайлы.

Существующий MP3 меняется только после явного действия в Metadata Editor. Запись выполняется через временную копию в том же каталоге, проверку MPEG/metadata и атомарную замену. Неизвестные/custom ID3 frames сохраняются, если пользователь явно их не редактирует.

Удаление failed/needs-review задачи загрузки удаляет запись очереди, а не готовый аудиофайл.

## Форматы

Чтение локальной библиотеки использует format adapters. Полноценная безопасная запись метаданных реализована для **MP3/ID3**; остальные поддерживаемые форматы остаются read-only в Metadata Editor, если для них нет отдельного безопасного writer path.

Yandex upload использует только явно выбранные пользователем файлы и требует подтверждения прав. Пользователь отвечает за законность загрузки и использования контента.

## Большие библиотеки

Release-кандидат прошёл отдельный цикл оптимизации для коллекций в несколько тысяч треков:

- Local Library открывается cache-first и не запускает recursive scan при обычной навигации;
- страницы и массовые операции ограничены bounded chunks;
- Matching сохраняет batches через активное соединение без второго SQLite writer в hot loop;
- Select All / массовые решения показывают processed/total progress;
- Downloads обновляет Wanted/queue state при открытии и возврате на страницу;
- Download All сначала создаёт видимую persisted queue, затем выполняет её последовательным worker;
- Yandex download worker переиспользует одну service/client session и имеет bounded retry/circuit-breaker для системных ошибок;
- повторное Yandex playback использует cache short-circuit до дорогой provider preparation.

## Сеть

MusicArk поддерживает три режима:

```text
System  — системные сетевые настройки
Direct  — прямое соединение
Custom  — пользовательский proxy
```

Встроенное управление Cloudflare WARP удалено из release runtime. MusicArk не устанавливает и не удаляет WARP автоматически.

Сетевые ошибки внешних metadata/download источников должны деградировать локально и не блокировать работу с уже сохранённой библиотекой.

## Windows distribution

Финальный release pipeline создаёт:

```text
MusicArk-1.0.0-win-x64.zip
MusicArk-Setup-1.0.0-x64.exe
SHA256SUMS.txt
update-manifest.json
```

Portable и installer включают Flutter desktop и frozen MusicArk backend runtime. Отдельно установленный Python или developer checkout пользователю не требуется.

Установщик per-user размещает приложение в `%LOCALAPPDATA%\Programs\Music Ark`. Пользовательские данные хранятся отдельно в `%LOCALAPPDATA%\MusicArk` и не должны удаляться обычным uninstall.

### Обновления

Stable updater использует:

```text
https://github.com/Regstar2/music-ark/releases/latest/download/update-manifest.json
```

`MUSICARK_UPDATE_MANIFEST_URL` может переопределить endpoint для тестирования/развёртывания.

Update flow разделён:

```text
check   → только получить и проверить manifest
prepare → скачать installer и проверить размер + SHA-256
apply   → после явного подтверждения повторно проверить и запустить installer
```

Ошибка update endpoint не должна мешать обычному запуску MusicArk.

## Данные и приватность

- токены, cookies, signed media URLs и proxy passwords не должны попадать в Git;
- Flutter не получает Yandex token или защищённые provider media URLs для playback/download;
- автоматические diagnostics для feedback ограничены версией MusicArk, ОС и архитектурой и не включают музыкальную библиотеку, локальные пути или credentials;
- mutable state установленной версии хранится в пользовательском каталоге, а не рядом с program files.

## Ограничения v1.0.0

- Windows x64 — единственная release-платформа;
- полноценная запись metadata — MP3/ID3;
- часть provider-функций зависит от внешних API и доступности сервисов;
- автоматическое определение `ORIGINAL / CENSORED` не считается абсолютной истиной: сомнительные случаи требуют проверки;
- MusicArk не является двунаправленным filesystem mirror и не должен автоматически удалять/переименовывать существующие локальные треки;
- update/install действия не выполняются без явного пользовательского шага;
- код-сайнинг должен указываться в release notes фактически: подписан только реально проверенный подписанный artifact; иначе installer считается `UNSIGNED`.

## Запуск для разработки

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt

.\scripts\ci.ps1

$env:MUSICARK_PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path
Set-Location .\ui\musicark_ui
flutter run -d windows
```

Финальная Windows-упаковка:

```powershell
.\scripts\release.ps1 -Version v1.0.0
```

Она должна запускаться только из source state, где `VERSION` уже равен `1.0.0`.

## Документация

- [CHANGELOG.md](CHANGELOG.md) — история изменений;
- [docs/versions/v1.0.0.md](docs/versions/v1.0.0.md) — границы первого публичного релиза;
- [docs/release/release-checklist.md](docs/release/release-checklist.md) — финальный release gate;
- [docs/testing/release-regression-matrix.md](docs/testing/release-regression-matrix.md) — regression mapping;
- [GitHub Issues](https://github.com/Regstar2/music-ark/issues) — ошибки и предложения.

## Public release gate

До публикации стабильного `v1.0.0` должны быть подтверждены финальный CI/tag/artifacts, публичная доступность feedback/update links, фактическое состояние подписи installer и выбранная владельцем проекта лицензия (`LICENSE`) с необходимой проверкой third-party notices. Эти пункты не считаются выполненными только потому, что release-код уже присутствует в `main`.