"""One-shot idempotent patch for large root release documents.

This file is intentionally temporary during v0.15 authoring. It modifies only
known v0.14 release-header anchors and inserts the v0.15 changelog section;
historical documentation below those anchors is left untouched.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _replace_once(path: Path, old: str, new: str) -> str:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Expected release anchor was not found in {path.name}")
    return text.replace(old, new, 1)


def main() -> int:
    readme = ROOT / "README.md"
    ru = _replace_once(
        readme,
        "**Текущая версия кода: 0.14.0 — Large Library Performance & Release Hardening.**",
        "**Текущая версия кода: 0.15.0 — Installer, Auto-Update, Feedback & Packaging.**",
    )
    marker_ru = "## Distribution, Updates & Feedback v0.15.0"
    if marker_ru not in ru:
        anchor = "## Large Library Performance & Release Hardening v0.14.0\n"
        section = """## Distribution, Updates & Feedback v0.15.0

v0.15.0 переводит MusicArk из developer-checkout в распространяемое Windows-приложение: release package включает Flutter desktop и замороженный backend runtime, поэтому пользователю не нужен отдельно установленный Python или `.venv`. Добавлены per-user Inno Setup installer, portable ZIP и SHA-256 manifests; пользовательские данные хранятся вне каталога программы и не удаляются обычным uninstall.

Проверка обновлений использует строгий HTTPS manifest: `check` только читает данные, `prepare` скачивает и проверяет точный размер + SHA-256, а `apply` запускает уже проверенный установщик только после явного подтверждения. В release-сборке проверка может запускаться автоматически; debug/tests остаются без фонового update-запроса. Публичный GitHub release/update channel подключается при публикации и не является требованием для сборки v0.15.

В Settings добавлены Bug report / Feature request. Автоматические diagnostics ограничены версией MusicArk, ОС и архитектурой и не включают токены, cookies, signed URLs, proxy secrets, пути к музыке или содержимое библиотеки. Подробнее: `docs/versions/v0.15.0.md`.

"""
        if anchor not in ru:
            raise SystemExit("README.md v0.14 section anchor was not found")
        ru = ru.replace(anchor, section + anchor, 1)
    readme.write_text(ru, encoding="utf-8")

    readme_en = ROOT / "README_EN.md"
    en = _replace_once(
        readme_en,
        "**Current code version: 0.14.0 — Large Library Performance & Release Hardening.**",
        "**Current code version: 0.15.0 — Installer, Auto-Update, Feedback & Packaging.**",
    )
    marker_en = "## Distribution, Updates & Feedback v0.15.0"
    if marker_en not in en:
        anchor = "## Large Library Performance & Release Hardening v0.14.0\n"
        section = """## Distribution, Updates & Feedback v0.15.0

v0.15.0 turns MusicArk from a developer-checkout application into a distributable Windows app. The release package contains the Flutter desktop client and a frozen backend runtime, so users do not need a separately installed Python or `.venv`. The milestone adds a per-user Inno Setup installer, portable ZIP and SHA-256 manifests; mutable user data stays outside the program directory and survives ordinary uninstall.

Update discovery uses a strict HTTPS manifest: `check` is read-only, `prepare` downloads and verifies exact size + SHA-256, and `apply` launches the already verified installer only after explicit confirmation. Release builds may check automatically; debug/tests do not perform the background update request. The public GitHub release/update channel is connected at publication time and is not required to build v0.15.

Settings now exposes Bug report / Feature request actions. Automatic diagnostics are limited to MusicArk version, OS and architecture and exclude tokens, cookies, signed URLs, proxy secrets, music paths and library contents. See `docs/versions/v0.15.0.md`.

"""
        if anchor not in en:
            raise SystemExit("README_EN.md v0.14 section anchor was not found")
        en = en.replace(anchor, section + anchor, 1)
    readme_en.write_text(en, encoding="utf-8")

    changelog = ROOT / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    marker = "### v0.15.0 — Installer, Auto-Update, Feedback & Packaging"
    if marker not in text:
        anchor = "## Unreleased — release hardening\n\n"
        section = """### v0.15.0 — Installer, Auto-Update, Feedback & Packaging

#### Added

- canonical `VERSION` contract with automated consistency checks across Python and Flutter release metadata;
- standalone frozen MusicArk backend runtime and deterministic Windows packaging pipeline;
- per-user Inno Setup installer definition, portable ZIP, SHA-256 output and update-manifest generator;
- strict update manifest parsing, HTTPS/GitHub host validation, bounded redirects, exact size/SHA-256 verification and explicit Check → Prepare → Apply flow;
- Settings update/feedback card with release-only automatic checking, explicit installer confirmation and RU/EN presentation;
- privacy-aware GitHub Bug/Feature Issue Forms and safe diagnostic links;
- focused backend/Flutter distribution tests plus self-hosted `v0.15 Distribution` CI packaging evidence.

#### Changed

- application/backend version advances to `0.15.0`, Flutter to `0.15.0+1`; core SQLite remains `1.9.0`;
- packaged mutable state is redirected outside the installation directory to the per-user MusicArk data root;
- old Flutter process bridges remain compatible with the packaged runtime without requiring a developer checkout or system Python;
- v0.14 is complete and feature scope remains frozen through the v1.0 release gate.

#### Safety / boundaries

- update checking never installs; download preparation never launches; installer launch requires explicit confirmation and re-verification;
- failed/untrusted/hash-mismatched update downloads fail closed and are never promoted as prepared installers;
- uninstall does not silently delete MusicArk user data or external software such as Cloudflare WARP;
- feedback diagnostics exclude credentials, protected URLs, account identifiers, local music paths and library contents;
- no Matching/Variant/Coverage/Download/Sync/Metadata/Yandex mutation semantics are expanded by v0.15.

#### Publication state

- no tag, GitHub Release, stable update manifest, public installer or repository visibility change is created by this PR;
- public update/feedback endpoints are deployment-time configuration and may remain unavailable while the repository is private;
- signing and clean-machine installer acceptance are reported only from actual release validation; unsigned/unverified artifacts are never described as signed.

"""
        if anchor not in text:
            raise SystemExit("CHANGELOG Unreleased anchor was not found")
        text = text.replace(anchor, anchor + section, 1)
        changelog.write_text(text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
