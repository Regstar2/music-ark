# Yandex Upload Protocol Probe

## Purpose

This toolchain exists to recover enough of the normal Yandex Music own-track upload contract to evaluate whether MusicArk can implement a compatible Python upload client.

It is **not** an uploader and does not send network requests.

Production provider capabilities remain disabled until a real one-file upload can be reproduced and verified through MusicArk's existing authentication boundary.

## Safety model

Generated reports contain protocol structure only. They must not contain raw JavaScript source, ordinary source strings, credentials, cookies, authorization values, raw multipart bodies, raw response bodies, uploaded audio bytes, or browser-session data.

Never upload or commit the raw `app.asar` or a raw HAR. Only sanitized JSON reports are intended for sharing.

## Current recovered architecture

Static analysis of the official desktop client now supports this model:

```text
getUploadUrl({playlistId, uid, path})
  -> POST loader/upload-url
  -> dynamic upload URL
  -> FormData field: file
  -> uploadFile({url, formData}, options)
  -> POST firstArgument.url
  -> asynchronous processing
  -> UGC track identity
  -> target playlist
```

The exact nested stage-one/stage-two request bindings and runtime authentication still require verification.

## Mode 1 — broad binary scan

```powershell
python .\tools\yandex_upload_protocol_probe.py scan-binary `
  "C:\path\to\Yandex Music\resources\app.asar" `
  --output .\.musicark\research\yandex-upload-static.json
```

## Mode 2 — targeted ASAR-member scan

```powershell
python .\tools\yandex_upload_target_probe.py `
  "C:\path\to\Yandex Music\resources\app.asar" `
  --offset 10113299 `
  --offset 10113545 `
  --offset 10176266 `
  --offset 16146222 `
  --offset 16146348 `
  --offset 17782754 `
  --offset 18726605 `
  --radius 65536 `
  --output .\.musicark\research\yandex-upload-target-v3.json
```

## Mode 3 — call-site scan

```powershell
python .\tools\yandex_upload_callsite_probe.py `
  "C:\path\to\Yandex Music\resources\app.asar" `
  --offset 10176266 `
  --offset 16146222 `
  --radius 1800 `
  --output .\.musicark\research\yandex-upload-callsite-v4.json
```

## Mode 4 — contract-shape scan (V5)

```powershell
python .\tools\yandex_upload_contract_probe.py `
  "C:\path\to\Yandex Music\resources\app.asar" `
  --offset 10176266 `
  --offset 16146222 `
  --output .\.musicark\research\yandex-upload-contract-v5.json
```

V5 can recover function signatures, named invocation argument shapes, HTTP targets, member-access shapes, form fields, and safe protocol literals.

## Mode 5 — function binding scan (V6)

Use V6 after V5 has identified the upload API methods. V6 analyzes only the bodies of `getUploadUrl` and `uploadFile` and records safe parameter/member/object relationships.

```powershell
python .\tools\yandex_upload_binding_probe.py `
  "C:\path\to\Yandex Music\resources\app.asar" `
  --offset 10176266 `
  --output .\.musicark\research\yandex-upload-binding-v6.json
```

Expected high-value relationships include shapes such as:

```text
searchParams.playlist-id -> t.playlistId
searchParams.uid         -> t.uid
searchParams.path        -> t.path
body                     -> t.formData
signal                   -> e.signal
```

These are examples of what the probe is designed to recover, not assumptions about the final protocol.

## Optional runtime HAR fallback

Only if static analysis cannot establish the remaining request shape, perform one normal user-owned upload in the official UI while DevTools Network is recording. Keep the raw HAR local and sanitize it before sharing:

```powershell
python .\tools\yandex_upload_protocol_probe.py sanitize-har `
  "C:\private\yandex-upload.har" `
  --output .\.musicark\research\yandex-upload-sanitized.json
```

## Local verification

The `tests` directory is intentionally used via discovery and is not required to be a Python package.

Focused probe suites:

```powershell
python -m unittest discover -s tests -p "test_yandex_upload_target_probe.py" -v
python -m unittest discover -s tests -p "test_yandex_upload_protocol_probe.py" -v
python -m unittest discover -s tests -p "test_yandex_upload_callsite_probe.py" -v
python -m unittest discover -s tests -p "test_yandex_upload_contract_probe.py" -v
python -m unittest discover -s tests -p "test_yandex_upload_binding_probe.py" -v
```

For the complete application suite, install MusicArk into the active interpreter first:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

## Gate for an experimental live uploader

Do not send a real upload request until the evidence identifies, at minimum:

1. stage-one target/method and playlist/user/path parameter placement;
2. stage-one response field containing the dynamic upload URL;
3. stage-two body/form-data binding and relevant request options;
4. credential type required for stage one;
5. whether stage two is pre-signed or needs Yandex authorization;
6. processing/success identity sufficient for playlist read-back verification.

The first live implementation must remain isolated and opt-in:

```text
explicit local file
  -> experimental YandexUploadTransport
  -> one explicit user playlist
  -> obtain upload URL
  -> upload one file
  -> wait for processing
  -> re-read target playlist
  -> verify uploaded UGC entity
```

Only a repeatable successful upload plus read-back verification can justify reconsidering `can_upload_tracks` or `supports_user_uploads`.
