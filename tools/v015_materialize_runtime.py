"""One-shot source migration for the v0.15 central Flutter runtime resolver.

This helper is executed by the temporary materialization workflow on the real
checkout because the connected GitHub API can edit files but cannot apply a
multi-file textual patch. It is deterministic and fails if an expected legacy
bridge shape cannot be migrated safely.
"""

from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "ui" / "musicark_ui" / "lib"

CALL_RE = re.compile(
    r"final (?P<root>repoRoot|root) = _resolveRepoRoot\(\);\s*"
    r"final python = await _resolvePython(?:Command)?\((?P=root)\);"
)
HELPER_RE = re.compile(
    r"\n  String _resolveRepoRoot\(\).*?\n  \}\n\}\n\nclass _PythonCommand",
    re.DOTALL,
)


def patch_bridge(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    if "_resolveRepoRoot()" not in original:
        return False

    text = original
    if "import 'runtime_resolver.dart';" not in text:
        # Keep local imports grouped after other relative imports.
        import_matches = list(re.finditer(r"^import '[^']+';\s*$", text, re.MULTILINE))
        if not import_matches:
            raise RuntimeError(f"No import insertion point in {path}")
        pos = import_matches[-1].end()
        text = text[:pos] + "\nimport 'runtime_resolver.dart';" + text[pos:]

    match = CALL_RE.search(text)
    if match is None:
        raise RuntimeError(f"Legacy runtime call shape not recognized in {path}")
    root_name = match.group("root")
    replacement = (
        "final runtime = await MusicArkRuntimeResolver().resolve();\n"
        f"    final {root_name} = runtime.dataBaseDir;\n"
        "    final python = _PythonCommand(\n"
        "      runtime.pythonExecutable,\n"
        "      prefixArgs: runtime.pythonPrefixArgs,\n"
        "    );\n"
        f"    Directory({root_name}).createSync(recursive: true);"
    )
    text = CALL_RE.sub(replacement, text, count=1)

    # Installed builds must not inherit an arbitrary developer PYTHONPATH. The
    # legacy bridge maps remain valid for repository development.
    if "if (runtime.packaged)" not in text:
        for env_name in ("bridgeEnv", "environment"):
            marker = f"    {env_name}.remove('YANDEX_MUSIC_TOKEN');"
            if marker in text:
                text = text.replace(
                    marker,
                    f"    if (runtime.packaged) {env_name}.remove('PYTHONPATH');\n{marker}",
                    1,
                )
                break

    text = text.replace(
        f"workingDirectory: {root_name},",
        "workingDirectory: runtime.workingDirectory,",
        1,
    )

    # Remove the now-unused per-bridge repository/Python discovery methods. The
    # tiny private command value remains because it is used to preserve the
    # existing argument-building code with minimal semantic churn.
    text, count = HELPER_RE.subn("\n}\n\nclass _PythonCommand", text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not remove legacy resolver helpers in {path}")

    if text == original:
        raise RuntimeError(f"Migration made no changes in {path}")
    path.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    changed: list[str] = []
    for path in sorted(LIB.glob("*.dart")):
        if patch_bridge(path):
            changed.append(path.relative_to(ROOT).as_posix())
    if not changed:
        raise RuntimeError("No legacy Flutter bridges were migrated.")
    print("Migrated central runtime policy into:")
    for item in changed:
        print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
