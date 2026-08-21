from __future__ import annotations

from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".github" / "workflows" / "tests.yml"
text = path.read_text(encoding="utf-8")
old = '''      - name: Generate 1k/10k/50k performance report
        shell: pwsh
        run: '& py "-$env:MUSICARK_PYTHON_VERSION" .\\tools\\performance_smoke.py --output .\\.musicark\\performance\\v014.json'
      - name: Upload performance report
        uses: actions/upload-artifact@v4
        with:
          name: musicark-performance-report
          path: .musicark/performance/v014.json
          if-no-files-found: error
          retention-days: 14
'''
new = '''      - name: Generate 1k/10k/50k performance report
        shell: pwsh
        run: '& py "-$env:MUSICARK_PYTHON_VERSION" .\\tools\\performance_smoke.py --output .\\.musicark\\performance\\v014.json'
      - name: Audit SQLite hot-query plans
        shell: pwsh
        run: '& py "-$env:MUSICARK_PYTHON_VERSION" .\\tools\\sqlite_query_audit.py --output .\\.musicark\\performance\\sqlite-query-audit.json'
      - name: Upload performance report
        uses: actions/upload-artifact@v4
        with:
          name: musicark-performance-report
          path: .musicark/performance/*.json
          if-no-files-found: error
          retention-days: 14
'''
if text.count(old) != 1:
    raise RuntimeError("performance workflow block not found exactly once")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("CI query-audit step added")
