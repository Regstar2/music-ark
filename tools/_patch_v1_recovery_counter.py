from pathlib import Path

path = Path("ui/musicark_ui/lib/sync_page.dart")
text = path.read_text(encoding="utf-8")
old = '''      (\n        context.l10n.v0111Recoverable,\n        _int(summary['censoredRecoverable']),\n      ),\n'''
new = '''      (\n        context.l10n.v0111Recoverable,\n        _int(summary['unavailableRecoverable']) +\n            _int(summary['censoredRecoverable']),\n      ),\n'''
if old not in text:
    raise SystemExit("Recovery summary counter anchor not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
