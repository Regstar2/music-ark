from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


download_page = Path("ui/musicark_ui/lib/download_page.dart")
text = download_page.read_text(encoding="utf-8")
text = replace_once(
    text,
    """  Future<void> _refreshCurrent({bool showSpinner = false}) async {
    if (_wantedTab) {
      await _loadWanted(showSpinner: showSpinner);
    } else {
      await _load(showSpinner: showSpinner);
    }
  }

""",
    "",
    "remove unused download refresh method",
)
download_page.write_text(text, encoding="utf-8")

localizations = Path("ui/musicark_ui/lib/v0111_localizations_ext.dart")
text = localizations.read_text(encoding="utf-8")
text = replace_once(
    text,
    "  String get v0111RoleUnavailable => _ru ? 'НЕДОСТУПНЫЕ' : 'UNAVAILABLE';\n",
    "",
    "remove retired unavailable role copy",
)
text = replace_once(
    text,
    """  String get v0111RecoveryRecoverable =>
      _ru ? 'Можно восстановить' : 'Recoverable';
""",
    """  String get v0111RecoveryRecoverable =>
      _ru ? 'Есть локальная копия' : 'Local copy available';
""",
    "rename diagnostic recovery filter",
)
localizations.write_text(text, encoding="utf-8")

sync_bridge = Path("ui/musicark_ui/lib/sync_bridge.dart")
text = sync_bridge.read_text(encoding="utf-8")
text = replace_once(
    text,
    "      'uploadByRole': {'censored': 0, 'unavailable': 0},\n",
    "      'uploadByRole': {'censored': 0},\n",
    "remove unavailable upload role from fake plan",
)
sync_bridge.write_text(text, encoding="utf-8")

print("Applied issue #54 UI/CI cleanup")
