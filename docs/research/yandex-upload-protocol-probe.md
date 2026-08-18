# Yandex Upload Protocol Probe

## Purpose

This tool exists to recover enough of the normal Yandex Music own-track upload contract to evaluate whether MusicArk can implement a compatible Python upload client.

It is **not** an uploader and does not send network requests.

The probe intentionally keeps production provider capabilities disabled until a real one-file upload can be reproduced and verified through MusicArk's existing authentication boundary.

## Why this approach

The public `yandex-music==3.0.0` client used by MusicArk has no verified own-file upload method. Yandex Music nevertheless exposes own-track upload in its official website/desktop UI.

The most reliable next source of evidence is therefore the normal official client behavior rather than guessed endpoint names.

Two complementary inputs are supported:

1. static scan of an official Electron `app.asar` / `yandex-music.asar` bundle;
2. local sanitization of a HAR captured while the project owner performs one normal upload in the official UI.

Neither mode extracts browser cookies or credentials for reuse.

## Safety model

The generated report contains only protocol structure:

- HTTP method when available;
- URL/path with query **values removed**;
- request/response header **names**;
- media/content type without multipart boundary;
- multipart/form field names;
- uploaded filename extension only, not the filename;
- JSON key/type shape, not scalar values;
- static endpoint candidates and source-context hashes.

The report does not include:

- `Authorization` values;
- Cookie values;
- OAuth tokens;
- CSRF/XSRF/signature values;
- raw multipart bodies;
- raw JSON values;
- uploaded audio bytes;
- raw response bodies;
- Electron source-code contexts.

A raw HAR can contain sensitive session data. **Never commit, upload, paste, or share the raw HAR.** Keep it local, sanitize it with the tool, inspect the resulting JSON, then delete the raw capture when it is no longer needed.

## Mode 1 — scan an official Electron bundle

From the MusicArk repository root:

```powershell
python .\tools\yandex_upload_protocol_probe.py scan-binary `
  "C:\path\to\Yandex Music\resources\app.asar" `
  --output .\.musicark\research\yandex-upload-static.json
```

The exact installation path is deliberately not hard-coded because Yandex desktop packaging can change.

A possible local search on Windows is:

```powershell
Get-ChildItem $env:LOCALAPPDATA -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object {
    $_.Name -in @('app.asar', 'yandex-music.asar') -and
    $_.FullName -match '(?i)yandex|music'
  } |
  Select-Object FullName, Length
```

The scan reads the bundle as bytes. Extraction with `asar`/Node is not required for the first pass.

Useful evidence in the resulting report includes combinations such as:

```text
upload + FormData + POST + /.../upload
playlistUuid + multipart/form-data
api.music.yandex.* + upload-related path
```

A string hit alone is not sufficient to declare the protocol solved. The HAR path is used to confirm the real runtime request.

## Mode 2 — sanitize one normal upload HAR

Use the official Yandex Music website or desktop DevTools and perform a normal upload of a small audio file that you own and are willing to use as a test artifact.

Capture only the shortest useful interval:

```text
clear Network log
  -> start capture
  -> perform one upload into a test playlist
  -> wait for success/failure response
  -> stop capture
```

Export the capture to a local HAR file. Treat that HAR as a credential-bearing secret until sanitized.

Then run:

```powershell
python .\tools\yandex_upload_protocol_probe.py sanitize-har `
  "C:\private\yandex-upload.har" `
  --output .\.musicark\research\yandex-upload-sanitized.json
```

Only `yandex-upload-sanitized.json` is intended to be shared for analysis.

## What the sanitized HAR can answer

If the runtime request is present in the HAR, the report should let the project determine:

- host and endpoint path;
- HTTP method;
- whether the body is multipart, JSON or another type;
- upload form field names;
- whether a playlist UUID/ID is a body field, query field or path component;
- names of authentication/session-related headers without their values;
- response status;
- response JSON structure and whether it appears to return track/playlist identity fields.

It deliberately does **not** answer whether MusicArk's current token value is accepted. That requires a later minimal live PoC after the request contract is understood.

## Criteria for implementing an experimental uploader

Do not add a real upload request until the evidence identifies, at minimum:

1. target host/path and method;
2. body content type and file field;
3. playlist target semantics;
4. required authentication/session mechanism at the level of credential type;
5. success/failure response shape;
6. a way to verify the uploaded item by reading the target playlist afterward.

If normal upload requires browser-only cookies/CSRF state that cannot be reproduced through MusicArk's existing credential boundary, the result remains blocked rather than silently importing browser credentials.

## Planned experimental client boundary

If the contract is recovered, the first implementation should stay isolated from Sync and production capabilities:

```text
explicit local file
  -> experimental YandexUploadTransport
  -> one explicit user playlist
  -> one upload request
  -> parse server result
  -> read playlist through existing provider
  -> verify uploaded item
```

Only after a repeatable one-file validation should `can_upload_tracks` or `supports_user_uploads` be reconsidered.
