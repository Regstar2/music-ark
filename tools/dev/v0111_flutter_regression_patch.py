from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


replace_once(
    "ui/musicark_ui/test/yandex_upload_local_library_test.dart",
    "    await tester.tap(find.byKey(const Key('local-track-menu-77')));\n    await tester.pumpAndSettle();\n    expect(find.byKey(const Key('local-upload-yandex-77')), findsOneWidget);\n    expect(find.text('Загрузить в Яндекс Музыку'), findsOneWidget);\n",
    "    expect(find.byKey(const Key('local-upload-yandex-77')), findsOneWidget);\n    expect(find.byTooltip('Загрузить в Яндекс Музыку'), findsOneWidget);\n",
)

replace_once(
    "ui/musicark_ui/test/sync_page_test.dart",
    "    expect(find.text(r'D:\\Music'), findsOneWidget);\n",
    "    expect(find.text(r'D:\\Music'), findsWidgets);\n",
)
replace_once(
    "ui/musicark_ui/test/sync_page_test.dart",
    "    expect(find.byKey(const Key('sync-plan-table-header')), findsNothing);\n    expect(find.byKey(const Key('sync-filter-download')), findsOneWidget);\n",
    "    expect(find.byKey(const Key('sync-plan-table-header')), findsNothing);\n    await tester.scrollUntilVisible(\n      find.byKey(const Key('sync-workspace-tabs')),\n      320,\n      scrollable: find.byKey(const Key('sync-page')),\n    );\n    await tester.pumpAndSettle();\n    expect(find.byKey(const Key('sync-filter-download')), findsOneWidget);\n",
)

replace_once(
    "ui/musicark_ui/test/yandex_upload_dialog_test.dart",
    "    await tester.tap(find.byKey(const Key('yandex-upload-submit')));\n    await tester.pumpAndSettle();\n    expect(\n      find.byKey(const Key('yandex-upload-state-processing')),",
    "    await tester.tap(find.byKey(const Key('yandex-upload-submit')));\n    await tester.pump(const Duration(milliseconds: 50));\n    expect(\n      find.byKey(const Key('yandex-upload-state-processing')),",
)

replace_once(
    "ui/musicark_ui/test/local_library_page_test.dart",
    "    expect(find.byKey(const Key('local-load-more')), findsOneWidget);\n    await tester.ensureVisible(find.byKey(const Key('local-load-more')));\n    await tester.tap(find.byKey(const Key('local-load-more')));\n",
    "    await tester.scrollUntilVisible(\n      find.byKey(const Key('local-load-more')),\n      500,\n      scrollable: find.byKey(const Key('local-track-list')),\n    );\n    await tester.pumpAndSettle();\n    expect(find.byKey(const Key('local-load-more')), findsOneWidget);\n    await tester.tap(find.byKey(const Key('local-load-more')));\n",
)
replace_once(
    "ui/musicark_ui/test/local_library_page_test.dart",
    "    expect(find.text('1 из 2 папок'), findsOneWidget);\n",
    "    expect(find.textContaining('1 из 2 папок'), findsOneWidget);\n",
)
replace_once(
    "ui/musicark_ui/test/local_library_page_test.dart",
    "    expect(find.text('1 из 4 папок'), findsOneWidget);\n",
    "    expect(find.textContaining('1 из 4 папок'), findsOneWidget);\n",
)

print("Flutter regression patch applied")
