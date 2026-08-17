# MusicArk

**Русский** · [English](README_EN.md)

**Текущая версия кода: 0.9.1 — Main Screen UI Polish.**  
**Текущая схема SQLite: 1.8.4.**

MusicArk — Windows desktop-приложение, связывающее cache-first библиотеку Яндекс Музыки с локальной музыкальной коллекцией. Local Library, Identity Matching, Variant, Coverage, Download и Controlled Sync остаются отдельными слоями. v0.9.1 не меняет музыкальную семантику и посвящена единому desktop UI главного экрана и Яндекс Музыки.

## Desktop shell и Yandex UI v0.9.1

MusicArk использует одну постоянную глобальную левую панель. Второй постоянный sidebar Яндекс Музыки удалён: `Треки`, `Плейлисты` и `Альбомы` доступны через верхнюю навигацию внутри основной рабочей области.

Вкладка `Альбомы` показывает **альбомы, которым пользователь явно поставил «Мне нравится» в Яндекс Музыке**. Это отдельная cache-first коллекция провайдера: индекс любимых альбомов обновляется вместе с библиотекой, а треки конкретного альбома загружаются лениво при открытии и затем сохраняются в локальном кэше MusicArk. Альбомы не выводятся из альбомных тегов любимых треков. Новая музыкальная SQLite-схема для этого не требуется: используется существующее универсальное хранилище provider collections.

Yandex workspace использует доступную ширину окна без прежнего обязательного `~920 px` horizontal-scroll layout. Search, sort и `Пометки версий` перестраиваются на узком desktop window; список треков использует table-like layout на широкой области и компактный row layout на меньшей ширине. В сортировке треков доступен вариант `Недоступные сначала`.

Обычный технический статус `available` не отображается у каждого трека. Недоступный трек визуально приглушён, playback отключён, а причина доступна через tooltip. ORIGINAL/CENSORED остаются app-level пометками: компактный chip показывается в строке, inline-редактирование и общий менеджер пометок сохранены.

В глобальной панели используются единые layout tokens и небольшой векторный MusicArk mark. `System / Light / Dark`, `System / Russian / English`, account control, Settings, Help и About сохраняются. Now Playing остаётся application-wide и получил responsive presentation без добавления queue/next/previous/shuffle/repeat.

## Основной цикл

```text
Yandex Library = desired state
        ↓
Local Library = actual files (обычный Scan только читает)
        ↓
Matching + Variant + Coverage
        ↓
Missing / Wanted → Download / Controlled Sync
```

Для файлов с плохими тегами используется отдельный ручной workflow:

```text
Local Library
  → Редактировать метаданные
  → локальная правка
      или
    Yandex Track search → Compare
  → Применить метаданные
      или
    Применить и связать
  → transactional MP3 write
  → single-file reindex + SHA-256
  → targeted Matching refresh
  → Coverage/UI refresh
```

## Metadata и Identity — разные сущности

**«Применить метаданные»** меняет только выбранные непустые поля, artwork и при явном выборе filename локального MP3. После записи выполняются single-file reindex, обновление SHA-256 и targeted Matching refresh. Даже высокая similarity сама по себе не становится подтверждённой identity.

**«Применить и связать»** выполняет ту же запись и дополнительно создаёт подтверждённую пользователем связь:

```text
provider   = yandex_music
external   = <Yandex Track ID>
local file = <Local File ID>
method     = exact_id
confidence = 1.0
reason     = user_confirmed
```

При таком bind MusicArk записывает доверенный provenance в ID3 TXXX. Зарезервированные provenance-теги нельзя редактировать через обычный раздел Advanced Tags.

## Безопасность изменения файлов

Scan, Matching, Coverage и Sync **не изменяют пользовательские аудиофайлы**. Существующий файл изменяется только после явного действия в Metadata Editor.

Для MP3 используется pipeline:

```text
original
  ↓
same-directory temporary copy
  ↓
ID3/artwork write
  ↓
MPEG audio validation
  ↓
metadata read-back validation
  ↓
atomic os.replace()
```

До atomic replace оригинал остаётся неизменным. Audio stream не транскодируется. Неизвестные/custom ID3 frames сохраняются, если пользователь явно не редактирует их.

## Artwork и Yandex Library playback

Local Library показывает thumbnail каждого трека. Приоритет: embedded artwork, затем уже cached Yandex artwork для подтверждённой identity, затем placeholder. Список локальной библиотеки не делает Yandex request для каждой строки.

В Yandex Library доступны artwork и встроенное воспроизведение. Backend готовит или переиспользует приватный playback cache под `.musicark/playback/yandex` и передаёт Flutter только локальный путь. Yandex token, Authorization headers и protected/signed provider media URL во Flutter не передаются. Playback cache не индексируется в Local Library и не влияет на Matching или Coverage.

## Content labels и Variant acceptance

App-level метки **ОРИГИНАЛ / ЦЕНЗУРА** можно задавать для local track и cached Yandex identity. Они не меняют Yandex, не переписывают audio metadata, не меняют Matching identity и не повышают confidence.

Для `ALTERED`, `DIFFERENT_VERSION` и `UNCERTAIN` пользователь может выбрать **«Эта версия меня устраивает»** и позднее отменить принятие. Решение хранится отдельно от analyzer result: исходный Variant status не превращается в `SAME`. Принятие действительно только для того же analysis evidence/fingerprint.

## Форматы

Архитектура использует format adapters. Полноценная безопасная запись реализована для **MP3/ID3**. Другие аудиоформаты остаются read-only в Metadata Editor.

## Controlled Sync

Sync не является двунаправленным filesystem mirror. Стандартный Apply остаётся безопасным:

```text
deleted local files = 0
renamed/moved local files = 0
modified existing local files/tags = 0
Yandex mutations = 0
```

Metadata Editor — отдельный explicit-write workflow и не вызывается Scan/Matching/Coverage/Sync автоматически.

## SQLite

Forward-only schema:

```text
1.3.0 — Local Library
1.4.0 — Identity Matching
1.5.0 — Variant Detection
1.6.0 — Coverage actions
1.7.0 — Download queue/settings
1.8.0 — Controlled Sync
1.8.1 — Rich Yandex download metadata/provenance
1.8.2 — Local artwork cache / Metadata Editor support
1.8.3 — app-level ORIGINAL/CENSORED labels
1.8.4 — variant user acceptance
```

v0.9.1 не повышает SQLite schema. Theme/locale preferences по-прежнему хранятся отдельно от музыкальной БД. Инициализация БД остаётся idempotent и не требует удаления существующей `.musicark/musicark.db`.

## Запуск для разработки на Windows

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
python -m unittest discover -s tests -p "test_*.py" -v

$env:MUSICARK_PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path
Set-Location .\ui\musicark_ui
flutter pub get
flutter analyze
flutter test
flutter run -d windows
```

## Roadmap

```text
v0.8.0 — Controlled Sync                               complete
v0.8.1 — Rich Yandex download metadata/provenance      complete
v0.8.2 — Local Metadata Editor / Yandex Metadata       complete
v0.9.0 — UI, Account & Settings                        complete
v0.9.1 — Main Screen UI Polish                         current
v0.10.x — Yandex Upload                                next
```

Yandex Upload в v0.9.1 не реализован. Это состояние исходного кода, а не заявление об опубликованном GitHub Release. См. `docs/versions/v0.9.1.md`, `docs/architecture/ui-design-system.md`, `docs/architecture/app-shell-settings.md`, `docs/architecture/metadata-editor.md`, `docs/architecture/content-labels.md` и `docs/architecture/variant-acceptance.md`.
