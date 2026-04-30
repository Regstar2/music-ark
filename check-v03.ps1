$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "== MusicArk v0.3 manual check =="

if (-not (Test-Path "requirements-yandex.txt")) {
    throw "requirements-yandex.txt not found."
}

Write-Host "`n[1/6] Installing Yandex dependency"
python -m pip install -r requirements-yandex.txt

Write-Host "`n[2/6] Running health-check"
$env:PYTHONPATH = "src"
python -m musicark.cli --base-dir . health-check

Write-Host "`n[3/6] Initializing database schema"
python -m musicark.cli --base-dir . db-init

Write-Host "`n[4/6] Running yandex auth-check"
python -m musicark.cli --base-dir . yandex auth-check

Write-Host "`n[5/6] Running yandex scan-all twice (repeat scan test)"
python -m musicark.cli --base-dir . yandex scan-all *> $null
python -m musicark.cli --base-dir . yandex scan-all *> $null
Write-Host "scan-all executed twice"

Write-Host "`n[6/6] Verifying database counters and raw safety"
@'
import sqlite3

c = sqlite3.connect(".musicark/musicark.db")
tracks = c.execute("select count(*) from provider_tracks").fetchone()[0]
playlists = c.execute("select count(*) from provider_playlists").fetchone()[0]
sources = c.execute("select count(*) from track_sources").fetchone()[0]
raw = c.execute("select count(*) from provider_raw_responses").fetchone()[0]
audit = c.execute("select count(*) from audit_log where event_type='provider_scan'").fetchone()[0]
stypes = c.execute("select source_type, count(*) from track_sources group by source_type").fetchall()
payloads = [r[0] for r in c.execute("select payload_json from provider_raw_responses").fetchall()]
s = "\n".join(payloads)

print("provider_tracks:", tracks)
print("provider_playlists:", playlists)
print("track_sources:", sources)
print("provider_raw_responses:", raw)
print("audit provider_scan:", audit)
print("source types:", stypes)
print("raw_has_token_key:", "YANDEX_MUSIC_TOKEN" in s)
print("raw_has_auth_header:", "Authorization" in s)
c.close()
'@ | python

Write-Host "`nDone."
