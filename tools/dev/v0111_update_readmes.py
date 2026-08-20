from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def update(path: str, replacements: list[tuple[str, str]]) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    for old, new in replacements:
        if old not in text:
            raise RuntimeError(f"{path}: expected anchor not found: {old[:80]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8", newline="\n")


ru_intro_old = """**Текущая версия кода: 0.11.0 — Production Single-Track Yandex Upload.**  
**Текущая схема SQLite: 1.8.4.**

MusicArk — Windows desktop-приложение, связывающее cache-first библиотеку Яндекс Музыки с локальной музыкальной коллекцией. Local Library, Identity Matching, Variant, Coverage, Download и Controlled Sync остаются отдельными слоями. Ветка v0.9.x завершена. v0.10.0 завершила feasibility-фазу и подтвердила direct-Python загрузку end-to-end; v0.11.0 переносит этот доказанный протокол в production manual workflow для одного локального MP3.

## Production Single-Track Yandex Upload v0.11.0
"""
ru_intro_new = """**Текущая версия кода: 0.11.1 — Bulk Upload, Recovery Sync & Explicit Scope Context.**  
**Текущая схема SQLite: 1.9.0.**

MusicArk — Windows desktop-приложение, связывающее cache-first библиотеку Яндекс Музыки с локальной музыкальной коллекцией. Local Library, Identity Matching, Variant, Coverage, Download и Controlled Sync остаются отдельными слоями. v0.11.0 доказала production-загрузку одного MP3; v0.11.1 использует тот же `YandexSingleTrackUploadService` как единственный primitive передачи файла и расширяет его до безопасной массовой загрузки и восстановления целостности коллекции.

## Bulk Upload & Recovery Sync v0.11.1

Local Library поддерживает выбор по стабильному `local_file_id`, `Выбрать все видимые`, массовую панель и последовательную загрузку (`concurrency=1`). Одиночная кнопка загрузки перенесена из меню `...` прямо в действия строки рядом с Play/Edit. Ручная массовая загрузка по умолчанию использует управляемый плейлист **ЗАГРУЖЕННЫЕ ТРЕКИ**, если он настроен.

MusicArk хранит три роли управляемых плейлистов по `playlist kind`, а не по названию: **ЦЕНЗУРА**, **ЗАГРУЖЕННЫЕ ТРЕКИ**, **НЕДОСТУПНЫЕ**. Создание плейлистов остаётся fail-closed до отдельного ручного live-proof; без него пользователь назначает существующие собственные плейлисты. Реальный playlist API никогда не мутируется в CI.

Доступность трека Яндекс Музыки теперь отдельна от локального Coverage: `available / unavailable / unknown`. `available=false` является явным сигналом; простое исчезновение из плейлиста не считается недоступностью без дополнительного доказательства. История last-known state позволяет отслеживать переходы unavailable/available-again без сохранения сырых provider responses.

Controlled Sync умеет формировать `UPLOAD_LOCAL_TO_YANDEX` только для детерминированных случаев: недоступный provider track + существующий локальный MP3 → **НЕДОСТУПНЫЕ**; явно `censored` provider track + явно `original` локальный MP3 → **ЦЕНЗУРА**. `altered`, `different_version` и `uncertain` сами по себе не являются доказательством цензуры. Upload-only Sync не требует папку загрузок, но upload portion всегда требует новое подтверждение прав.

`YandexBatchUploadService` не содержит второго transport: каждый элемент проходит через `YandexSingleTrackUploadService`. Ошибка одного элемента не останавливает остальные; `delivery_unknown` не повторяется автоматически и требует сначала проверить плейлист. Persistent upload mapping + read-back делают повторный Sync идемпотентным для verified upload.

Подробности и ограничения: `docs/versions/v0.11.1.md`.

## Production Single-Track Yandex Upload v0.11.0
"""

en_intro_old = """**Current code version: 0.11.0 — Production Single-Track Yandex Upload.**  
**Current SQLite schema: 1.8.4.**

MusicArk is a Windows desktop application connecting a cache-first Yandex Music library with a local music collection. Local Library, Identity Matching, Variant, Coverage, Download and Controlled Sync remain separate layers. The v0.9.x line is complete. v0.10.0 completed the feasibility phase and confirmed direct-Python upload end to end; v0.11.0 promotes that proven protocol into a production manual workflow for one local MP3.

## Production Single-Track Yandex Upload v0.11.0
"""
en_intro_new = """**Current code version: 0.11.1 — Bulk Upload, Recovery Sync & Explicit Scope Context.**  
**Current SQLite schema: 1.9.0.**

MusicArk is a Windows desktop application connecting a cache-first Yandex Music library with a local music collection. Local Library, Identity Matching, Variant, Coverage, Download and Controlled Sync remain separate layers. v0.11.0 proved production upload of one MP3; v0.11.1 keeps `YandexSingleTrackUploadService` as the only one-file transfer primitive and extends it into safe bulk upload and collection recovery.

## Bulk Upload & Recovery Sync v0.11.1

Local Library now selects tracks by stable `local_file_id`, supports Select all visible, a bulk toolbar and sequential upload (`concurrency=1`). The single-track upload action is no longer hidden in the overflow menu; it is a direct row action beside Play/Edit. Manual bulk upload defaults to the managed **UPLOADED TRACKS** playlist when configured.

MusicArk persists three managed playlist roles by playlist `kind`, not title: **CENSORED**, **UPLOADED TRACKS**, and **UNAVAILABLE**. Playlist creation stays fail-closed until a separate manual live proof succeeds; without that proof the user assigns existing owned playlists. CI never performs real playlist mutations.

Yandex provider availability is now independent from local Coverage: `available / unavailable / unknown`. Explicit `available=false` is evidence of unavailability; disappearance from a playlist alone is not. Lightweight last-known history tracks unavailable/available-again transitions without copying raw provider responses.

Controlled Sync can create `UPLOAD_LOCAL_TO_YANDEX` only for deterministic recovery: unavailable provider track + existing local MP3 → **UNAVAILABLE**; explicitly `censored` provider track + explicitly `original` local MP3 → **CENSORED**. `altered`, `different_version`, and `uncertain` do not prove censorship by themselves. Upload-only Sync does not require a download folder, but every upload apply requires fresh rights confirmation.

`YandexBatchUploadService` is not a second transport: every item calls `YandexSingleTrackUploadService`. One item failure does not stop safe later items; `delivery_unknown` is never blindly retried and requires playlist inspection first. Persistent upload mappings plus read-back make repeated Sync idempotent for verified uploads.

See `docs/versions/v0.11.1.md` for the full architecture, safety rules, research status, and limitations.

## Production Single-Track Yandex Upload v0.11.0
"""

update("README.md", [(ru_intro_old, ru_intro_new)])
update("README_EN.md", [(en_intro_old, en_intro_new)])
print("v0.11.1 README updates applied")
