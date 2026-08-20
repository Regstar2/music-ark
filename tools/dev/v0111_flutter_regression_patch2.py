from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


replace_once(
    "ui/musicark_ui/test/yandex_upload_local_library_test.dart",
    "    expect(find.text('Artist - Track.mp3'), findsWidgets);\n",
    "    expect(find.textContaining('Artist - Track.mp3'), findsOneWidget);\n",
)
replace_once(
    "ui/musicark_ui/test/sync_page_test.dart",
    "      scrollable: find.byKey(const Key('sync-page')),\n",
    "      scrollable: find.descendant(\n        of: find.byKey(const Key('sync-page')),\n        matching: find.byType(Scrollable),\n      ),\n",
)
replace_once(
    "ui/musicark_ui/test/local_library_page_test.dart",
    "      scrollable: find.byKey(const Key('local-track-list')),\n",
    "      scrollable: find.descendant(\n        of: find.byKey(const Key('local-track-list')),\n        matching: find.byType(Scrollable),\n      ),\n",
)

print("Final focused Flutter test patch applied")
