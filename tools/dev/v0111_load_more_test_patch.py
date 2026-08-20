from pathlib import Path

path = Path(__file__).resolve().parents[2] / "ui/musicark_ui/test/local_library_page_test.dart"
text = path.read_text(encoding="utf-8")
old = """    await tester.scrollUntilVisible(\n      find.byKey(const Key('local-load-more')),\n      500,\n      scrollable: find.descendant(\n        of: find.byKey(const Key('local-track-list')),\n        matching: find.byType(Scrollable),\n      ),\n    );\n    await tester.pumpAndSettle();\n"""
new = """    final trackList = find.byKey(const Key('local-track-list'));\n    final loadMore = find.byKey(const Key('local-load-more'));\n    for (var i = 0; i < 12 && loadMore.evaluate().isEmpty; i++) {\n      await tester.drag(trackList, const Offset(0, -4000));\n      await tester.pump();\n    }\n    await tester.pumpAndSettle();\n"""
if text.count(old) != 1:
    raise RuntimeError(f"expected one load-more block, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
print("load-more regression test patched")
