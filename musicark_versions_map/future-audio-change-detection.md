# future-audio-change-detection

## Статус

Будущая исследовательская возможность.  
Не входит в обязательный MVP и не должна блокировать версии [[v0.1-core-foundation]], [[v0.2-provider-architecture]], [[v0.3-yandex-scan]], [[v0.4-local-library]], [[v0.5-download-system]], [[v0.6-yandex-download]], [[v0.7-matching]], [[v0.8-sync-planner]], [[v0.9-desktop-ui]], [[v1.0-stable-desktop-mvp]] и [[v1.1-android-mvp]].

## Идея

MusicArk может отслеживать изменения аудиосодержимого трека между локальной версией пользователя и текущей версией у провайдера без хранения второй полной копии аудиофайла.

Главная цель — не скачивать ещё одну коллекцию ради сравнения. Если у пользователя локальная библиотека занимает 60 ГБ, MusicArk не должен превращать её в 120 ГБ просто потому, что кому-то захотелось «аккуратно проверить изменения». Это был бы не дизайн, а преступление против SSD.

## Основной сценарий

У пользователя уже есть локальная коллекция:

- импортированная через [[v0.4-local-library]];
- скачанная через [[v0.5-download-system]] и [[v0.6-yandex-download]];
- сопоставленная с provider-треками через [[v0.7-matching]].

MusicArk использует локальный файл как эталонную версию, а текущую версию у провайдера читает потоком:

```text
local audio file
    ↓
create compact audio baseline
    ↓
provider audio stream
    ↓
streaming analysis without saving full file
    ↓
compare with baseline
    ↓
store only report
```

## Главный результат

MusicArk умеет:

- создать компактный аудио-слепок локального файла;
- получить потоковую версию трека от провайдера без сохранения полной копии;
- сравнить локальную версию и потоковую версию по аудиосодержимому;
- определить подозрительные изменения:
  - возможный вырезанный фрагмент;
  - возможный замьюченный фрагмент;
  - возможный запиканный фрагмент;
  - возможную замену explicit-версии на clean-версию;
  - неизвестное изменение аудио;
- сохранить отчёт об изменениях в [[storage]];
- записать событие в [[history-audit-log]].

## Входит

- новый модуль [[audio-baseline]];
- новый модуль [[audio-stream-provider]];
- новый модуль [[audio-change-detector]];
- новый модуль [[audio-change-report]];
- создание baseline для [[local-audio-file]];
- потоковое чтение аудио от provider backend;
- декодирование аудио в общий внутренний PCM-формат;
- сравнение аудио не по байтам, а по содержимому;
- сегментное сравнение аудио;
- определение изменения длительности;
- определение локальных отличий по таймкодам;
- определение участков с подозрительной тишиной;
- определение участков с подозрительным beep-сигналом;
- сохранение результатов проверки;
- UI-отчёт о найденных изменениях;
- настройки лимитов проверки по CPU, трафику и количеству треков.

## Не входит

- хранение второй полной копии аудиофайла;
- автоматическое скачивание всей коллекции повторно;
- юридическая классификация изменения как доказанной цензуры;
- распознавание конкретных слов в тексте песни;
- восстановление вырезанных или замьюченных слов;
- обход DRM или технических ограничений провайдера;
- публикация базы «цензурированных треков» без явного решения на уровне продукта;
- обязательная проверка всей библиотеки по расписанию.

## Зависимости

### Обязательные

- [[v0.4-local-library]] — нужны локальные файлы как эталон.
- [[v0.5-download-system]] — нужны общие download/source-абстракции.
- [[v0.6-yandex-download]] — нужен первый реальный backend, который потенциально может отдавать аудиопоток.
- [[v0.7-matching]] — нужно понимать, какой локальный файл соответствует какому provider-треку.
- [[storage]] — нужно хранить baseline и отчёты.
- [[history-audit-log]] — нужно логировать проверки и найденные изменения.
- [[track-source]] — нужно связывать аудио с конкретным источником.
- [[local-audio-file]] — нужен объект локального аудиофайла.

### Желательные

- [[metadata-editor]] — может помочь отображать и исправлять связи между локальным файлом и provider-треком.
- [[desktop-ui]] — нужен удобный отчёт по изменениям.
- [[sync-planner]] — может учитывать найденные изменения при планировании синхронизации.

## Новые модули

### [[audio-stream-provider]]

Отвечает за получение аудио от провайдера в виде потока без сохранения полной копии файла.

Примерная ответственность:

```text
AudioStreamProvider
- openStream(trackSource)
- checkStreamAvailable(trackSource)
- exposeCodecInfo(trackSource)
- closeStream()
```

Важно: [[audio-stream-provider]] не должен быть тем же самым, что [[download-provider]].

[[download-provider]] нужен для сохранения файла в библиотеку.  
[[audio-stream-provider]] нужен для временного анализа аудио.

Если смешать это в одну абстракцию, получится классический инженерный суп: всё умеет всё, а потом никто не понимает, почему проверка изменений внезапно скачала 60 ГБ.

### [[audio-baseline]]

Отвечает за создание компактного эталона локального аудиофайла.

Baseline не хранит аудио. Он хранит только признаки, достаточные для сравнения.

Возможные данные:

```text
AudioBaseline
- id
- track_id
- local_audio_file_id
- source_id
- duration_ms
- sample_rate_used
- channels_mode
- algorithm
- algorithm_version
- global_fingerprint
- segment_size_ms
- segment_fingerprints
- loudness_by_segment
- silence_map
- spectral_stats_by_segment
- created_at
- updated_at
```

### [[audio-change-detector]]

Сравнивает baseline и текущий поток провайдера.

Примерная ответственность:

```text
AudioChangeDetector
- compareBaselineWithStream(baseline, stream)
- detectDurationChange()
- detectCut()
- detectMute()
- detectBeep()
- detectLocalAudioChanges()
- estimateConfidence()
```

### [[audio-change-report]]

Хранит результат проверки.

Примерная модель:

```text
AudioChangeReport
- id
- track_id
- source_id
- baseline_id
- checked_at
- result
- confidence
- old_duration_ms
- new_duration_ms
- changed_segments
- notes
- raw_detector_output
```

Возможные значения `result`:

```text
same
metadata_changed_only
audio_changed
possible_cut
possible_mute
possible_beep
possible_clean_version
unknown_audio_change
stream_unavailable
check_failed
```

Пример сегмента:

```text
AudioChangedSegment
- start_ms
- end_ms
- change_type
- confidence
- old_loudness
- new_loudness
- details
```

## Почему нельзя сравнивать sha256

Побайтовый hash полезен только для ответа на вопрос: «это буквально тот же файл?»

Для этой задачи он почти бесполезен, потому что локальная версия и provider stream могут отличаться технически:

- другой контейнер;
- другой codec;
- другой bitrate;
- другая нормализация громкости;
- другой sample rate;
- другой encoder;
- FLAC локально и AAC/MP3 в потоке.

Поэтому сравнение должно идти по декодированному аудиосодержимому, приведённому к общему виду:

```text
provider stream / local file
    ↓
decode
    ↓
normalize format
    ↓
mono or normalized stereo
    ↓
fixed sample rate
    ↓
PCM chunks
    ↓
features / fingerprints
```

## Уровни проверки

### Уровень 1: metadata check

Проверяется только информация от провайдера:

- duration;
- explicit flag;
- album version;
- raw response hash;
- доступность stream;
- возможный provider revision id, если есть.

Плюсы:

- быстро;
- почти не тратит трафик;
- можно делать часто.

Минусы:

- не доказывает изменение аудио;
- легко пропускает цензуру без изменения метаданных.

### Уровень 2: global audio fingerprint

Проверяется общий отпечаток трека.

Плюсы:

- можно понять, что аудиосодержимое отличается;
- компактный baseline.

Минусы:

- плохо объясняет, где именно изменение;
- может быть чувствителен к ремастеру или перекодированию.

### Уровень 3: segment-level diff

Трек сравнивается по сегментам.

Пример:

```text
segment size: 1-5 seconds
local baseline segment N
vs
remote stream segment N
```

Плюсы:

- можно найти таймкод изменения;
- можно отличить локальные изменения от глобального ремастера;
- полезно для mute/beep/cut detection.

Минусы:

- дороже по CPU;
- сложнее реализация;
- нужны аккуратные threshold-значения.

### Уровень 4: specialized censorship heuristics

Поверх segment-level diff запускаются эвристики:

- возможная тишина вместо слова;
- короткий тональный beep;
- локальное отличие без изменения длительности;
- изменение в вокальных участках;
- много мелких отличий, похожих на clean-version.

Вывод должен быть осторожным:

```text
possible_clean_version
confidence: 0.82
```

Не нужно писать «цензура доказана». Приложение не суд, не экспертная лаборатория и не всевидящее ухо. Пусть люди хотя бы здесь не притворяются богами.

## Политика хранения

MusicArk не хранит вторую копию аудио.

Хранить можно:

- baseline;
- отчёты;
- таймкоды отличий;
- технические метрики;
- краткие временные буферы во время проверки.

Не хранить по умолчанию:

- полную remote-версию;
- фрагменты remote-аудио;
- подозрительные snippets.

Опционально, только если пользователь явно разрешил:

- сохранить короткий фрагмент для ручного сравнения;
- сохранить новую версию трека как отдельную версию в библиотеке.

## Ограничения

Без доступа к аудиопотоку нельзя надёжно определить изменение аудиосодержимого.

Если provider не отдаёт stream, MusicArk может сделать только metadata-level проверку.

Если локальный файл не сопоставлен с provider track, проверку делать нельзя.

Если локальный файл уже является clean-версией, MusicArk не сможет узнать, что раньше существовала explicit-версия, если у пользователя нет эталона.

Если provider отдаёт другую master-версию, live-версию или remaster, detector может найти изменения, но не обязан классифицировать их как цензуру.

## Производительность

Проверка всей библиотеки может быть дорогой по времени, CPU и трафику.

Для больших коллекций нужны лимиты:

```text
Audio change check settings
- max tracks per run
- max tracks per day
- check only favorites
- check only selected playlists
- check only tracks with suspicious metadata changes
- check only manually selected tracks
- pause on battery power
- pause on metered connection
```

Для коллекции на 4000 треков нормальная стратегия:

- создать baseline один раз;
- metadata check делать чаще;
- stream audio check запускать выборочно;
- не проверять всю библиотеку каждый день;
- показывать пользователю очередь проверок.

## UI

В [[desktop-ui]] можно добавить раздел:

```text
Audio Integrity / Проверка аудио
```

Возможные элементы:

- список последних проверок;
- фильтр по результатам;
- треки с подозрительными изменениями;
- таймкоды отличий;
- confidence score;
- кнопка ручной перепроверки;
- настройка уровня проверки;
- настройка лимитов.

Пример карточки:

```text
Track: Artist - Title
Result: possible_clean_version
Confidence: 0.78
Changed segments:
- 00:42.5–00:44.0 possible_beep
- 01:18.0–01:20.0 possible_mute
Checked source: yandex_music
Checked at: 2026-04-30 22:10
```

## История и аудит

В [[history-audit-log]] должны писаться события:

```text
AUDIO_BASELINE_CREATED
AUDIO_BASELINE_UPDATED
AUDIO_CHANGE_CHECK_STARTED
AUDIO_CHANGE_CHECK_FINISHED
AUDIO_CONTENT_CHANGED
POSSIBLE_CUT_DETECTED
POSSIBLE_MUTE_DETECTED
POSSIBLE_BEEP_DETECTED
POSSIBLE_CLEAN_VERSION_DETECTED
AUDIO_CHANGE_CHECK_FAILED
AUDIO_STREAM_UNAVAILABLE
```

## Интеграция с версиями

### [[v0.4-local-library]]

Добавить будущую связь:

```text
Локальные аудиофайлы могут использоваться как эталон для [[future-audio-change-detection]].
```

### [[v0.5-download-system]]

Добавить будущую связь:

```text
Download backend не должен автоматически использоваться для проверки изменений аудио. Для этого нужен отдельный [[audio-stream-provider]].
```

### [[v0.6-yandex-download]]

Добавить будущую связь:

```text
Yandex backend в будущем может предоставить потоковый доступ для [[future-audio-change-detection]], если это технически возможно и не нарушает ограничения провайдера.
```

### [[v0.7-matching]]

Добавить будущую связь:

```text
После сопоставления локального файла с provider-треком можно сравнивать локальную версию с текущей потоковой версией провайдера.
```

### [[v0.8-sync-planner]]

Добавить будущую связь:

```text
Sync planner может учитывать результаты [[audio-change-report]] и предупреждать пользователя, если provider-версия отличается от локального эталона.
```

## Возможный порядок реализации

### Этап 1: baseline без stream-проверки

- создать [[audio-baseline]];
- считать baseline для локальных файлов;
- хранить duration, loudness profile, silence map, basic fingerprint;
- добавить команды пересчёта baseline.

### Этап 2: metadata-only provider check

- сравнивать provider duration / explicit flag / raw response hash;
- писать подозрительные изменения в [[history-audit-log]];
- не анализировать аудио.

### Этап 3: stream provider abstraction

- создать [[audio-stream-provider]];
- отделить потоковый анализ от [[download-provider]];
- добавить проверку доступности потока;
- не сохранять remote audio на диск.

### Этап 4: global fingerprint comparison

- считать fingerprint remote stream на лету;
- сравнивать с локальным baseline;
- сохранять `same` / `audio_changed` / `check_failed`.

### Этап 5: segment-level diff

- считать признаки по сегментам;
- находить таймкоды локальных изменений;
- учитывать небольшой сдвиг дорожки;
- сохранять список changed segments.

### Этап 6: mute / beep / cut heuristics

- добавить эвристику возможной тишины;
- добавить эвристику возможного beep;
- добавить эвристику вырезанного фрагмента;
- добавить осторожную классификацию `possible_clean_version`.

### Этап 7: UI и настройки

- показать отчёты в [[desktop-ui]];
- добавить лимиты проверки;
- добавить ручную проверку выбранных треков;
- добавить настройки хранения.

## Тестирование

Нужны тестовые аудиофайлы с искусственными изменениями:

- оригинал;
- версия с вырезанными 2 секундами;
- версия с замьюченным словом;
- версия с beep-сигналом;
- версия с другим bitrate;
- версия с другим codec;
- версия с изменённой громкостью;
- версия с remaster-like EQ;
- версия с небольшим offset в начале.

Тесты должны проверять:

- baseline создаётся стабильно;
- перекодирование не считается автоматической цензурой;
- cut определяется по изменению длительности и alignment;
- mute определяется по локальному падению громкости;
- beep определяется по короткому тональному сигналу;
- отчёт содержит таймкоды;
- remote stream не сохраняется как полный файл;
- временные файлы удаляются после проверки.

## Риски

- false positive на remaster;
- false positive на другой master;
- false positive на radio edit;
- false negative при очень коротких изменениях;
- высокая нагрузка на CPU;
- высокий сетевой трафик;
- нестабильный stream provider;
- юридические и ToS-ограничения провайдера;
- сложность нормального UX для confidence score.

## Принципиальные решения

- Не хранить вторые копии аудио по умолчанию.
- Не называть изменение цензурой без достаточной уверенности.
- Не смешивать [[download-provider]] и [[audio-stream-provider]].
- Не блокировать MVP этой фичей.
- Не проверять всю библиотеку автоматически без лимитов.
- Хранить компактный baseline и отчёты, а не аудиофайлы.

## Краткий вывод

[[future-audio-change-detection]] — это будущая возможность MusicArk для проверки того, изменилась ли provider-версия трека относительно локального эталона пользователя.

Фича реализуема без хранения второй полной копии коллекции:

```text
local file = эталон
provider stream = временная проверяемая версия
baseline = компактное хранилище признаков
report = результат сравнения
```

Но без доступа к аудиопотоку надёжно определить изменение аудиосодержимого нельзя. Метаданные могут дать только слабый сигнал, а не доказательство.
