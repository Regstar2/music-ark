from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str, *, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual < count:
        raise RuntimeError(f"{path}: expected {count} occurrence(s), found {actual}: {old[:100]!r}")
    target.write_text(text.replace(old, new, count), encoding="utf-8")


# Matching: prevent a slower old search/filter reload from replacing a newer one.
replace(
    "ui/musicark_ui/lib/matching_workspace_page.dart",
    "  String _sort = 'confidence';\n  String? _error;",
    "  String _sort = 'confidence';\n  String? _error;\n  int _requestGeneration = 0;",
)
replace(
    "ui/musicark_ui/lib/matching_workspace_page.dart",
    "  Future<void> _reload() async {\n    setState(() {",
    "  Future<void> _reload() async {\n    final generation = ++_requestGeneration;\n    setState(() {",
)
replace(
    "ui/musicark_ui/lib/matching_workspace_page.dart",
    "      items = await _withContentLabels(items);\n      if (!mounted) return;",
    "      items = await _withContentLabels(items);\n      if (!mounted || generation != _requestGeneration) return;",
)
replace(
    "ui/musicark_ui/lib/matching_workspace_page.dart",
    "  Future<void> _loadMore() async {\n    if (_loadingMore || _items.length >= _total) return;\n    setState(() {",
    "  Future<void> _loadMore() async {\n    if (_loadingMore || _items.length >= _total) return;\n    final generation = _requestGeneration;\n    setState(() {",
)
replace(
    "ui/musicark_ui/lib/matching_workspace_page.dart",
    "      nextItems = await _withContentLabels(nextItems);\n      if (!mounted) return;",
    "      nextItems = await _withContentLabels(nextItems);\n      if (!mounted || generation != _requestGeneration) return;",
)

# Coverage: protect both initial/full loads and filter/search reloads.
replace(
    "ui/musicark_ui/lib/coverage_page.dart",
    "  bool _analysisExpanded = false;\n  String? _error;",
    "  bool _analysisExpanded = false;\n  String? _error;\n  int _requestGeneration = 0;",
)
replace(
    "ui/musicark_ui/lib/coverage_page.dart",
    "  Future<void> _load({bool initial = false}) async {\n    if (mounted) {",
    "  Future<void> _load({bool initial = false}) async {\n    final generation = ++_requestGeneration;\n    if (mounted) {",
)
replace(
    "ui/musicark_ui/lib/coverage_page.dart",
    "      ]);\n      if (!mounted) return;\n      final summary = Map<String, dynamic>.from(results[0]);",
    "      ]);\n      if (!mounted || generation != _requestGeneration) return;\n      final summary = Map<String, dynamic>.from(results[0]);",
)
replace(
    "ui/musicark_ui/lib/coverage_page.dart",
    "  }) async {\n    if (mounted) {\n      setState(() {\n        _loading = true;",
    "  }) async {\n    final generation = ++_requestGeneration;\n    if (mounted) {\n      setState(() {\n        _loading = true;",
)
replace(
    "ui/musicark_ui/lib/coverage_page.dart",
    "      final results = await Future.wait(futures);\n      if (!mounted) return;",
    "      final results = await Future.wait(futures);\n      if (!mounted || generation != _requestGeneration) return;",
)
replace(
    "ui/musicark_ui/lib/coverage_page.dart",
    "        );\n        if (!mounted) return;\n        items = _maps(tracks['items']);",
    "        );\n        if (!mounted || generation != _requestGeneration) return;\n        items = _maps(tracks['items']);",
)

# Downloads: periodic polling and manual reloads may overlap; only newest result wins.
replace(
    "ui/musicark_ui/lib/download_page.dart",
    "  int _wantedTotal = 0;\n  Timer? _pollTimer;",
    "  int _wantedTotal = 0;\n  Timer? _pollTimer;\n  int _loadGeneration = 0;\n  int _wantedLoadGeneration = 0;",
)
replace(
    "ui/musicark_ui/lib/download_page.dart",
    "  Future<void> _load({bool showSpinner = false}) async {\n    if (showSpinner && mounted) setState(() => _loading = true);",
    "  Future<void> _load({bool showSpinner = false}) async {\n    final generation = ++_loadGeneration;\n    if (showSpinner && mounted) setState(() => _loading = true);",
)
replace(
    "ui/musicark_ui/lib/download_page.dart",
    "      ]);\n      if (!mounted) return;\n      final rawItems = results[1]['items'];",
    "      ]);\n      if (!mounted || generation != _loadGeneration) return;\n      final rawItems = results[1]['items'];",
)
replace(
    "ui/musicark_ui/lib/download_page.dart",
    "  Future<void> _loadWanted({bool showSpinner = false}) async {\n    final bridge = widget.coverageBridge;",
    "  Future<void> _loadWanted({bool showSpinner = false}) async {\n    final generation = ++_wantedLoadGeneration;\n    final bridge = widget.coverageBridge;",
)
replace(
    "ui/musicark_ui/lib/download_page.dart",
    "      );\n      if (!mounted) return;\n      final rawItems = payload['items'];",
    "      );\n      if (!mounted || generation != _wantedLoadGeneration) return;\n      final rawItems = payload['items'];",
)

# README RU/EN: update only the release-line introduction, keep historical sections intact.
replace(
    "README.md",
    "**Текущая версия кода: 0.11.1 — Bulk Upload, Recovery Sync & Explicit Scope Context.**  \n**Текущая схема SQLite: 1.9.0.**\n\nMusicArk — Windows desktop-приложение, связывающее cache-first библиотеку Яндекс Музыки с локальной музыкальной коллекцией. Local Library, Identity Matching, Variant, Coverage, Download и Controlled Sync остаются отдельными слоями. v0.11.0 доказала production-загрузку одного MP3; v0.11.1 использует тот же `YandexSingleTrackUploadService` как единственный primitive передачи файла и расширяет его до безопасной массовой загрузки и восстановления целостности коллекции.\n\n## Bulk Upload & Recovery Sync v0.11.1",
    "**Текущая версия кода: 0.14.0 — Large Library Performance & Release Hardening.**  \n**Текущая схема SQLite: 1.9.0.**\n\nMusicArk — Windows desktop-приложение для cache-first работы с библиотекой Яндекс Музыки и локальной музыкальной коллекцией. Проект сохраняет отдельные границы Local Library, Identity Matching, Variant, Coverage, Download, Metadata Editor, Controlled Sync и Yandex Upload. v0.12 добавила внешние metadata/network boundaries, v0.13 — multi-format audio и безопасную конвертацию для Yandex, а v0.14 замораживает feature scope и убирает доказанную лишнюю работу на больших библиотеках.\n\n## Large Library Performance & Release Hardening v0.14.0\n\nLocal Library теперь открывается строго cache-first: обычная навигация читает SQLite и первую страницу, а recursive filesystem scan запускается только явной кнопкой Scan. Backend независимо от UI ограничивает страницу 250 строками; search/sort/root scope остаётся в SQLite до pagination.\n\nIncremental scan не отправляет десятки тысяч unchanged paths в SQLite write path: metadata parser вызывается только для new/changed files, а storage получает delta `upserts + missing paths`. Неполный filesystem walk fail-closed и не удаляет файлы, отсутствие которых нельзя доказать.\n\nArtwork cache делает batch lookup текущей страницы, запоминает отсутствие обложки по fingerprint size/mtime/provider identity и использует v0.13 format adapters вместо MP3-only fast path. Малые list images декодируются с bounded dimensions. Yandex track search получил 180 ms debounce, memoization текущего source/query/sort и lazy fixed-extent rows.\n\n`tools/performance_smoke.py` генерирует deterministic 1k/10k/50k SQLite datasets и JSON report; CI сохраняет его как `musicark-performance-report`. Жёсткие acceptance assertions основаны на deterministic work metrics, а не на хрупких миллисекундных порогах.\n\nFeature roadmap после этой версии ограничен v0.15.0 (Installer, Auto-Update, Feedback & Packaging) и v1.0.0 (Release Freeze & Public Release). Подробности: `docs/versions/v0.14.0.md`.\n\n## Bulk Upload & Recovery Sync v0.11.1",
)
replace(
    "README_EN.md",
    "**Current code version: 0.11.1 — Bulk Upload, Recovery Sync & Explicit Scope Context.**  \n**Current SQLite schema: 1.9.0.**\n\nMusicArk is a Windows desktop application connecting a cache-first Yandex Music library with a local music collection. Local Library, Identity Matching, Variant, Coverage, Download and Controlled Sync remain separate layers. v0.11.0 proved production upload of one MP3; v0.11.1 keeps `YandexSingleTrackUploadService` as the only one-file transfer primitive and extends it into safe bulk upload and collection recovery.\n\n## Bulk Upload & Recovery Sync v0.11.1",
    "**Current code version: 0.14.0 — Large Library Performance & Release Hardening.**  \n**Current SQLite schema: 1.9.0.**\n\nMusicArk is a Windows desktop application for cache-first Yandex Music and local-library workflows. Local Library, Identity Matching, Variant, Coverage, Download, Metadata Editor, Controlled Sync and Yandex Upload remain separate boundaries. v0.12 added external metadata/network boundaries, v0.13 added multi-format audio and safe Yandex conversion, and v0.14 freezes feature scope while removing demonstrated redundant work on large libraries.\n\n## Large Library Performance & Release Hardening v0.14.0\n\nLocal Library now opens strictly cache-first: normal navigation reads SQLite and the first page, while recursive filesystem scanning runs only after an explicit Scan action. The backend enforces a 250-row hard page cap independently of Flutter; search/sort/root scope stays in SQLite before pagination.\n\nIncremental scans no longer push tens of thousands of unchanged paths through the SQLite write path. Metadata parsing remains limited to new/changed files and persistence receives the `upserts + missing paths` delta. An incomplete filesystem walk fails closed and never removes files whose absence is uncertain.\n\nArtwork cache uses a batch lookup for the current page, caches no-cover results against size/mtime/provider identity and reuses the v0.13 format-adapter registry rather than an MP3-only shortcut. Small list artwork uses bounded decode dimensions. Yandex track search now has a 180 ms debounce, current source/query/sort memoization and lazy fixed-extent rows.\n\n`tools/performance_smoke.py` generates deterministic 1k/10k/50k SQLite datasets and a JSON report uploaded by CI as `musicark-performance-report`. Hard acceptance assertions use deterministic work metrics rather than fragile millisecond thresholds.\n\nAfter v0.14 the feature roadmap is limited to v0.15.0 (Installer, Auto-Update, Feedback & Packaging) and v1.0.0 (Release Freeze & Public Release). See `docs/versions/v0.14.0.md`.\n\n## Bulk Upload & Recovery Sync v0.11.1",
)

# Changelog: prepend the new source-state entry under the existing Unreleased heading.
replace(
    "CHANGELOG.md",
    "## Unreleased — after v0.10.0\n\n### v0.10.0 — Yandex Upload Feasibility Spike",
    "## Unreleased — release hardening\n\n### v0.14.0 — Large Library Performance & Release Hardening\n\n#### Added\n\n- deterministic 1k/10k/50k synthetic performance harness with machine-readable JSON output and query-plan evidence;\n- focused Python regressions for page bounds, unchanged/delta scan work, partial-walk safety, artwork batching/negative caching and repeated DB initialization;\n- focused Flutter regressions for cache-first Local Library activation, 250-row first page and Yandex search debounce/lazy row behavior;\n- separate self-hosted `performance-regression` CI job uploading `musicark-performance-report`.\n\n#### Changed\n\n- Local Library navigation is cache-first and no longer starts an implicit recursive scan;\n- backend Local Library page size is hard-capped at 250;\n- scan persistence accepts an explicit missing-path delta and avoids O(N) unchanged `last_seen_at` rewrites;\n- Local Library artwork cache uses one bounded batch read for cached page entries and persists invalidatable no-cover results through the v0.13 format adapter boundary;\n- Yandex track filtering/search avoids the default full-list copy, debounces text input and bounds list-image decode dimensions;\n- Local Library, Matching, Coverage and Downloads ignore stale async reload results using local request-generation tokens;\n- application/backend version advances to `0.14.0`, Flutter to `0.14.0+1`; core SQLite remains `1.9.0`.\n\n#### Safety / boundaries\n\n- no new metadata provider, audio format, Yandex API capability, Matching/Variant truth model, database engine, persistent Python daemon or Flutter state-management framework is introduced;\n- partial scans never delete uncertain files; normal navigation does not scan roots; normal scrolling does not initiate external metadata network lookup;\n- source audio and v0.11-v0.13 upload/conversion safety boundaries remain unchanged;\n- live Yandex mutation flags/tokens are cleared in automated v0.14 performance tests.\n\n#### Verification state\n\n- deterministic performance and hardening tests are part of the branch;\n- exact final GitHub Actions run, job conclusions and measured JSON values are recorded only after they run against the final PR head;\n- no GitHub Release, tag, installer or production auto-update is created by v0.14.\n\n### v0.10.0 — Yandex Upload Feasibility Spike",
)

print("v0.14 follow-up patch applied")
