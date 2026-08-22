# MusicArk

**Русский** · [English](README_EN.md)

**Текущая версия кода: 0.15.0 — Installer, Auto-Update, Feedback & Packaging.**  
**Текущая схема SQLite: 1.9.0.**

MusicArk — Windows desktop-приложение для cache-first работы с библиотекой Яндекс Музыки и локальной музыкальной коллекцией. Проект сохраняет отдельные границы Local Library, Identity Matching, Variant, Coverage, Download, Metadata Editor, Controlled Sync и Yandex Upload. v0.12 добавила внешние metadata/network boundaries, v0.13 — multi-format audio и безопасную конвертацию для Yandex, а v0.14 замораживает feature scope и убирает доказанную лишнюю работу на больших библиотеках.

## Distribution, Updates & Feedback v0.15.0

v0.15.0 переводит MusicArk из developer-checkout в распространяемое Windows-приложение: release package включает Flutter desktop и замороженный backend runtime, поэтому пользователю не нужен отдельно установленный Python или `.venv`. Добавлены per-user Inno Setup installer, portable ZIP и SHA-256 manifests; пользовательские данные хранятся вне каталога программы и не удаляются обычным uninstall.

Проверка обновлений использует строгий HTTPS manifest: `check` только читает данные, `prepare` скачивает и проверяет точный размер + SHA-256, а `apply` запускает уже проверенный установщик только после явного подтверждения. В release-сборке проверка может запускаться автоматически; debug/tests остаются без фонового update-запроса. Публичный GitHub release/update channel подключается при публикации и не является требованием для сборки v0.15.

В Settings добавлены Bug report / Feature request. Автоматические diagnostics ограничены версией MusicArk, ОС и архитектурой и не включают токены, cookies, signed URLs, proxy secrets, пути к музыке или содержимое библиотеки. Подробнее: `docs/versions/v0.15.0.md`.

## Large Library Performance & Release Hardening v0.14.0

Local Library теперь открывается строго cache-first: обычная навигация читает SQLite и первую страницу, а recursive filesystem scan запускается только явной кнопкой Scan. Backend независимо от UI ограничивает страницу 250 строками; search/sort/root scope остаётся в SQLite до pagination.

Incremental scan не отправляет десятки тысяч unchanged paths в SQLite write path: metadata parser вызывается только для new/changed files, а storage получает delta `upserts + missing paths`. Неполный filesystem walk fail-closed и не удаляет файлы, отсутствие которых нельзя доказать.

Artwork cache делает batch lookup текущей страницы, запоминает отсутствие обложки по fingerprint size/mtime/provider identity и использует v0.13 format adapters вместо MP3-only fast path. Малые list images декодируются с bounded dimensions. Yandex track search получил 180 ms debounce, memoization текущего source/query/sort и lazy fixed-extent rows.

`tools/performance_smoke.py` генерирует deterministic 1k/10k/50k SQLite datasets и JSON report; CI сохраняет его как `musicark-performance-report`. Жёсткие acceptance assertions основаны на deterministic work metrics, а не на хрупких миллисекундных порогах.

Feature roadmap после этой версии ограничен v0.15.0 (Installer, Auto-Update, Feedback & Packaging) и v1.0.0 (Release Freeze & Public Release). Подробности: `docs/versions/v0.14.0.md`.

## Bulk Upload & Recovery Sync v0.11.1

Local Library поддерживает выбор по стабильному `local_file_id`, `Выбрать все видимые`, массовую панель и последовательную загрузку (`concurrency=1`). Одиночная кнопка загрузки перенесена из меню `...` прямо в действия строки рядом с Play/Edit. Ручная массовая загрузка по умолчанию использует управляемый плейлист **ЗАГРУЖЕННЫЕ ТРЕКИ**, если он настроен.

MusicArk хранит три роли управляемых плейлистов по `playlist kind`, а не по названию: **ЦЕНЗУРА**, **ЗАГРУЖЕННЫЕ ТРЕКИ**, **НЕДОСТУПНЫЕ**. Создание плейлистов остаётся fail-closed до отдельного ручного live-proof; без него пользователь назначает существующие собственные плейлисты. Реальный playlist API никогда не мутируется в CI.

Доступность трека Яндекс Музыки теперь отдельна от локального Coverage: `available / unavailable / unknown`. `available=false` является явным сигналом; простое исчезновение из плейлиста не считается недоступностью без дополнительного доказательства. История last-known state позволяет отслеживать переходы unavailable/available-again без сохранения сырых provider responses.

Controlled Sync умеет формировать `UPLOAD_LOCAL_TO_YANDEX` только для детерминированных случаев: недоступный provider track + существующий локальный MP3 → **НЕДОСТУПНЫЕ**; явно `censored` provider track + явно `original` локальный MP3 → **ЦЕНЗУРА**. `altered`, `different_version` и `uncertain` сами по себе не являются доказательством цензуры. Upload-only Sync не требует папку загрузок, но upload portion всегда требует новое подтверждение прав.

`YandexBatchUploadService` не содержит второго transport: каждый элемент проходит через `YandexSingleTrackUploadService`. Ошибка одного элемента не останавливает остальные; `delivery_unknown` не повторяется автоматически и требует сначала проверить плейлист. Persistent upload mapping + read-back делают повторный Sync идемпотентным для verified upload.

Подробности и ограничения: `docs/versions/v0.11.1.md`.

## Production Single-Track Yandex Upload v0.11.0

Проверенный live-контракт v0.10.0:

```text
Stage 1 HTTP 200
Stage 2 HTTP 201
playlist read-back verified=true
ambiguous=false
attemptsUsed=1
```

Production Stage 1 использует фиксированный endpoint:

```text
POST https://api.music.yandex.net/loader/upload-url
uid=<authenticated uid>
playlist-id=<uid>:<playlist kind>
path=<filename only>
```

MusicArk не добавляет `visibility`, Authorization, OAuth или Cookie. Stage 2 отправляет ровно один multipart `file` на dynamic `post-target` после проверки HTTPS/Yandex host. HTTPX работает с `http1=True`, `http2=True`, `trust_env=False`, `follow_redirects=False`, bounded timeout и без automatic retry.

В Local Library доступно явное действие **«Загрузить в Яндекс Музыку»** для одного трека. Пользователь выбирает собственный Yandex playlist и подтверждает право на загрузку файла. Backend принимает `local_file_id`, сам получает путь из локального индекса и до Stage 1 проверяет auth/UID, ownership плейлиста, существование и непустой MP3-файл, `confirm=true` и `rights_confirmed=true`.

После Stage 2 выполняется bounded playlist read-back. Сетевой сбой Stage 2 **не повторяет отправку автоматически**: MusicArk проверяет `ugc-track-id`; если результат нельзя подтвердить, возвращается `delivery_unknown` с требованием сначала проверить плейлист вручную. Это снижает риск duplicate UGC tracks.

`YandexMusicProvider.can_upload_tracks` и `supports_user_uploads` теперь `true`, но Controlled Sync по-прежнему не генерирует upload operations. Старый `experimental_yandex_upload` остаётся отдельным deprecated research/compatibility path и не превращается в production mutation. Подробности: `docs/versions/v0.11.0.md`.

Ограничения v0.11.0: MP3 only, один трек за действие, без bulk/queue/auto-sync upload/automatic retry/conversion/censorship replacement/background worker. Production release/installer в этой версии не создаётся.

## Settings / Help / About v0.9.7

`Настройки`, `Помощь` и `О приложении` используют ограниченную по ширине responsive desktop-компоновку вместо растягивания редкого utility-контента на всю рабочую область. Settings сохраняет текущие System/Light/Dark и System/Russian/English preferences, но размещает их в компактных responsive карточках, показывает status автосохранения и отдельную provider/account card на существующем `AccountSessionController`.

Help остаётся полностью локальной и теперь содержит 11 тем в группах `Библиотека / Анализ коллекции / Восстановление и действия / Приложение`. Она отдельно объясняет Identity/Metadata/Variant, Missing vs Different Version, ORIGINAL/CENSORED, Download states, Controlled Sync safety, Metadata Editor write boundary, artwork/playback cache и безопасность diagnostics.

About переиспользует существующий `MusicArkMark`, показывает версию/среду в responsive grid, безопасную diagnostics copy, стандартные Flutter dependency licenses и GitHub repository. Новая URL-launch dependency не добавляется: ссылка на GitHub доступна как selectable text и явное copy-link действие. Help/About имеют понятный возврат в Settings внутри существующего shell, поэтому Yandex workspace, account session и Now Playing не пересоздаются.

## Sync v0.9.6

Раздел `Синхронизация` строится как один последовательный desktop workflow: выбор области и папки загрузок, status/summary, текущее и прогнозируемое покрытие, пять основных метрик и единый `План синхронизации` с counted filters вместо нескольких больших `ExpansionTile`.

Фильтры `Все / Скачать / Решение / Сопоставление / Проверка версии / Локальная библиотека` работают только над уже полученными operations во Flutter и не пересоздают backend plan. На широкой области операции отображаются таблицей; на узкой — stacked rows. Если Sync payload не содержит artwork, используется theme-aware локальный placeholder без дополнительного provider request.

Apply по-прежнему пересчитывает актуальный diff, требует явного подтверждения и использует существующий Sync bridge/DownloadService boundary. v0.9.6 не добавляет удаление/перемещение локальных файлов, запись метаданных, Yandex mutation, reverse sync или автоматическую замену Different Version.

## Downloads v0.9.5

Раздел `Загрузки` использует компактные counted tabs `Загрузки` / `Нужные`, отдельные summary-метрики, поиск/status filters, компактные lazy-rendered track rows и contextual bulk actions. Ошибка показывается человекочитаемым сообщением по `errorCode`, а raw backend message, task/provider/external ID доступны отдельно в технических сведениях.

Для `failed` и `needs_review` доступно явное `Удалить`. Оно удаляет только запись download task; final audio file, Local Library, Matching, Coverage, Wanted state, provider cache и audit history не удаляются. Ожидаемый sibling `.part` может быть очищен best-effort только после проверки безопасного пути. `queued`/`running` удалять напрямую нельзя — для них используется существующая отмена.

Массовый выбор поддерживает retry ошибок, cancel активных задач, удаление ошибок и `Скачать выбранные` во вкладке Wanted. Batch bridge передаёт список ID одним Python process и возвращает частичный результат. `Повторить выбранные` и `Скачать выбранные` запускают только task IDs текущего действия и не будят старую unrelated queue.

## Coverage / Missing v0.9.4

Раздел `Недостающие` строится вокруг списка треков, а не длинной технической строки статистики. Сверху расположена компактная карточка локального покрытия с прогрессом и основными метриками, сворачиваемые детали Matching/Variant анализа, counted status tabs и responsive панель Collection/Search/Decision/Sort/Variant.

Строки Coverage показывают artwork из уже сохранённого `ProviderTrack.artwork_url` с локальным placeholder при отсутствии/ошибке картинки, затем название, исполнителя/альбом, membership в коллекциях и отдельные Coverage/Variant badges. Flutter не конструирует provider URL и не получает Yandex token/cookies/Authorization headers.

Для Missing сохраняются прежние действия: `Скачать` запускает существующий direct Download workflow и не меняет `userAction`; `Нужен`, `Игнорировать` и `Сбросить` остаются triage state. Master-checkbox выбирает все результаты активного Missing filter, а pagination скрывается, когда выдача помещается в одну страницу.

## Matching v0.9.3

Раздел `Сопоставление` показывает результаты как desktop-oriented comparison workspace:

```text
Яндекс Музыка | Локальный файл | Уверенность | Статус
```

Сверху расположены отдельные summary-карточки для количества Yandex/Local tracks, Matched, Needs review и Not found, затем действия Matching/Variant, counted filters, Search и Sort. Confidence отображается компактным процентом и progress meter вместо большого кругового индикатора.

Matching status и Variant status остаются разными сущностями: Matching отвечает за identity, а Variant — за проверку записи/версии. Строка открывает прежний detail workflow с Yandex/Local comparison, ORIGINAL/CENSORED, Variant verification/acceptance и ручными решениями для conflict candidates.

Search/Sort/filters продолжают использовать существующий bridge contract; pagination сохраняет текущий query scope и показывает `Показано X из Y`. На узком desktop window сравнительная таблица прокручивается горизонтально вместо разрушения структуры колонок. v0.9.3 не добавляет per-row network artwork, новый Matching/Variant algorithm или SQLite migration.

## Local Library v0.9.2

Local Library использует тот же desktop presentation layer, что и остальной интерфейс MusicArk: компактный header, единый toolbar, отдельный блок управления источниками и responsive table-like список треков.

Фильтр `Папки` позволяет отображать:

```text
Все папки
одну папку
произвольный набор нескольких папок
ни одной папки
```

Выбор папок — это **только область просмотра**, а не изменение конфигурации библиотеки. Добавление, сканирование и удаление source-root остаются отдельными явными действиями.

Фильтрация выполняется не по первым загруженным Flutter-строкам, а в SQLite до count/search/sort/pagination:

```text
Local Library UI
  → rootIds
  → Flutter process bridge
  → LocalLibraryService
  → SQLite library_root_id IN (?, ...)
  → COUNT / search / sort / LIMIT / OFFSET
```

Семантика query contract:

```text
rootIds = null    → все настроенные roots
rootIds = []      → 0 треков
rootIds = [1]     → только root 1
rootIds = [1,3]   → union roots 1 и 3
```

При первом открытии выбраны все roots. Если новый root добавляется, когда пользователь просматривает все roots, он автоматически входит в текущий просмотр; при пользовательском subset новый root не подключается сам. Удалённый root удаляется из selection.

Search, Sort и Load More всегда используют тот же выбранный root subset. Artwork, playback, Metadata Editor, подробности, открытие расположения файла и ORIGINAL/CENSORED сохраняются.

## Desktop shell и Yandex UI v0.9.1+

MusicArk использует одну постоянную глобальную левую панель. Второй постоянный sidebar Яндекс Музыки удалён: `Треки`, `Плейлисты` и `Альбомы` доступны через верхнюю навигацию внутри основной рабочей области.

Вкладка `Альбомы` показывает **альбомы, которым пользователь явно поставил «Мне нравится» в Яндекс Музыке**. Это отдельная cache-first коллекция провайдера: индекс любимых альбомов обновляется вместе с библиотекой, а треки конкретного альбома загружаются лениво при открытии и затем сохраняются в локальном кэше MusicArk. Альбомы не выводятся из альбомных тегов любимых треков. Новая музыкальная SQLite-схема для этого не требуется: используется существующее универсальное хранилище provider collections.

Yandex workspace использует доступную ширину окна без прежнего обязательного `~920 px` horizontal-scroll layout. Search, sort и `Пометки версий` перестраиваются на узком desktop window; список треков использует table-like layout на широкой области и компактный row layout на меньшей ширине. В сортировке треков доступен вариант `Недоступные сначала`.

Обычный технический статус `available` не отображается у каждого трека. Недоступный трек визуально приглушён, playback отключён, а причина доступна через tooltip. ORIGINAL/CENSORED остаются app-level пометками.

В глобальной панели используются единые layout tokens и небольшой векторный MusicArk mark. `System / Light / Dark`, `System / Russian / English`, account control, Settings, Help и About сохраняются. Now Playing остаётся application-wide и responsive без добавления queue/next/previous/shuffle/repeat.

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

Scan, root view filtering, Matching, Coverage и Sync **не изменяют пользовательские аудиофайлы**. Существующий файл изменяется только после явного действия в Metadata Editor. Удаление failed/needs-review download task в v0.9.5 также не удаляет final audio file.

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

Downloads v0.9.5 и Sync v0.9.6 используют локальный placeholder, если текущий payload не содержит готового artwork; отдельный сетевой запрос на каждую строку не добавляется.

## Content labels и Variant acceptance

App-level метки **ОРИГИНАЛ / ЦЕНЗУРА** можно задавать для local track и cached Yandex identity. Они не меняют Yandex, не переписывают audio metadata, не меняют Matching identity и не повышают confidence.

Для `ALTERED`, `DIFFERENT_VERSION` и `UNCERTAIN` пользователь может выбрать **«Эта версия меня устраивает»** и позднее отменить принятие. Решение хранится отдельно от analyzer result: исходный Variant status не превращается в `SAME`. Принятие действительно только для того же analysis evidence/fingerprint.

## Форматы

Архитектура использует format adapters. Полноценная безопасная запись реализована для **MP3/ID3**. Другие аудиоформаты остаются read-only в Metadata Editor. Manual Yandex upload v0.11.0 также ограничен MP3; конвертация форматов не входит в эту версию.

## Controlled Sync

Sync не является двунаправленным filesystem mirror. Стандартный Apply остаётся безопасным:

```text
deleted local files = 0
renamed/moved local files = 0
modified existing local files/tags = 0
Yandex mutations from Controlled Sync = 0
```

v0.9.6 меняет только presentation: plan filters работают над уже полученным operation snapshot, а Apply по-прежнему требует confirmation. Metadata Editor — отдельный explicit-write workflow и не вызывается Scan/Matching/Coverage/Sync автоматически. Manual upload v0.11.0 также является отдельным явным workflow и не вызывается SyncPlanner.

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

v0.10.0 и v0.11.0 не повышают SQLite schema. Manual one-track upload не добавляет upload queue/history tables и не сохраняет signed upload targets. Инициализация БД остаётся idempotent и не требует удаления существующей `.musicark/musicark.db`.

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
v0.9.1 — Main Screen UI Polish                         complete
v0.9.2 — Local Library UI & Multi-Root Selection       complete
v0.9.3 — Matching UI Redesign                          complete
v0.9.4 — Coverage / Missing UI Polish                  complete
v0.9.5 — Downloads UI, Safe Deletion & Bulk Actions    complete
v0.9.6 — Sync Page UI Polish                           complete
v0.9.7 — Settings, Help & About UI Polish              complete
v0.9.x — UI improvement line                           complete
v0.10.0 — Yandex Upload Feasibility / live proof       complete
v0.11.0 — Production Single-Track Yandex Upload        current
v0.12.0 — Upload queue / batch safety                  planned
```

v0.11.0 — это production-контур ручной загрузки одного MP3, а не GitHub Release. Bulk upload, upload queue, auto-sync upload, conversion и automatic retry остаются за пределами версии. См. `docs/versions/v0.11.0.md`.
