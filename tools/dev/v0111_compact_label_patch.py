from pathlib import Path

path = Path(__file__).resolve().parents[2] / "ui/musicark_ui/lib/local_library_page.dart"
text = path.read_text(encoding="utf-8")
old = """        child: Chip(\n          key: Key('local-content-label-${track['id']}'),\n          visualDensity: VisualDensity.compact,\n          label: Row(\n            mainAxisSize: MainAxisSize.min,\n            children: [\n              Text(text),\n              const SizedBox(width: 2),\n              const Icon(Icons.arrow_drop_down, size: 16),\n            ],\n          ),\n        ),\n"""
new = """        child: Chip(\n          key: Key('local-content-label-${track['id']}'),\n          visualDensity: VisualDensity.compact,\n          label: Text(\n            text,\n            maxLines: 1,\n            overflow: TextOverflow.ellipsis,\n          ),\n        ),\n"""
if text.count(old) != 1:
    raise RuntimeError(f"expected one content label chip block, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
print("compact content label patched")
