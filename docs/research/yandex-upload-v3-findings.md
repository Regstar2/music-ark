# Yandex Upload Protocol — V3 Static Findings

## Status

Research only. Production upload capabilities remain disabled.

The targeted ASAR report generated from the official Yandex Music desktop client establishes a substantially stronger internal upload shape than the earlier broad binary scan, but it still does not prove the complete authenticated request/response contract.

## Source artifact

The analyzed local report was generated from the official desktop client's `app.asar` with SHA-256:

```text
8e7f4cec0776c39f194dee0a94086548d13f1465d46aa05d3e00a21624cbe80a
```

No `app.asar`, raw source window, token, cookie, Authorization value, or audio payload is committed to the repository.

## High-confidence findings

The API/resource chunk:

```text
app/_next/static/chunks/2248.c548ad7dd602472d.js
```

contains all of the following structural evidence:

- `getUploadUrl`;
- `uploadFile`;
- `POST loader/upload-url`;
- `playlist-id`;
- `multipart/form-data`;
- `x-retry-count`;
- `ugc/tracks/`;
- playlist and UGC resources.

The upload-model chunk:

```text
app/_next/static/chunks/959-1d400e8429175934.js
```

contains:

- `TrackUgcUploadModel`;
- `UgcUploadCenterModel`;
- `getUploadUrl`;
- `uploadFile`;
- `runUpload` / `runUploadTracksQueue`;
- `retryUpload` / `abortUpload`;
- `FormData.append("file", ...)` shape, represented by the sanitized field name `file`;
- `uploadUrl`;
- `preparingTracks`, `uploadingTracks`, and `processingTracks` state identifiers;
- `checkProcessingTracks`;
- `moveTracksFromUploadCenterToPlaylist`;
- `FILE_TOO_LARGE` and `TOO_MANY_FILES` error identifiers.

The route-level bundles also reference `UgcUploadHttpClient`, confirming that the upload client is shared application infrastructure rather than a one-off UI string.

## Current transport model

The strongest source-supported model is:

```text
selected local file
  -> TrackUgcUploadModel
  -> getUploadUrl
  -> POST loader/upload-url
  -> receive/use uploadUrl
  -> FormData field: file
  -> uploadFile(uploadUrl, ...)
  -> uploading state
  -> processing state
  -> checkProcessingTracks
  -> moveTracksFromUploadCenterToPlaylist
```

This strongly supports a two-stage upload transport: obtain an upload URL through the Music API, then send the file to the returned dynamic URL, followed by asynchronous processing.

## Still unverified

Do not implement or enable production upload from V3 alone. The following relationships are not yet proven at call-site precision:

- whether `playlist-id` is an HTTP header, body field, or another request option of `loader/upload-url`;
- exact response JSON shape of `loader/upload-url` and the property containing the dynamic URL;
- exact method/options used for the dynamic upload URL;
- whether `multipart/form-data` is applied to the dynamic request directly;
- exact role of `x-retry-count`;
- credential type required for stage one;
- whether stage two is a pre-signed URL requiring no Yandex authorization header or still uses client authentication;
- processing-poll endpoint and success response shape;
- stable uploaded track identity returned or observed after processing.

## V4 call-site probe

`tools/yandex_upload_callsite_probe.py` narrows the same ASAR member to small sanitized structural windows around the concrete occurrences of:

- `getUploadUrl`;
- `uploadFile`;
- `runUpload`;
- `retryUpload`;
- `abortUpload`;
- `checkProcessingTracks`;
- `moveTracksFromUploadCenterToPlaylist`.

The report still excludes raw JavaScript and ordinary strings. Its purpose is to establish which HTTP call, protocol literals, MIME types and object keys occur in the immediate neighborhood of each method.

Suggested Windows run:

```powershell
python .\tools\yandex_upload_callsite_probe.py `
  "<YandexMusic install dir>\resources\app.asar" `
  --offset 10176266 `
  --offset 16146222 `
  --radius 1800 `
  --output .\.musicark\research\yandex-upload-callsite-v4.json
```

## Local validation evidence

The project owner ran the focused offline suites on Windows/Python 3.12:

```text
test_yandex_upload_target_probe.py   3/3 OK
test_yandex_upload_protocol_probe.py 3/3 OK
```

The subsequent full-suite invocation was not a valid application-suite result because the command used the global Python environment without the editable `musicark` package installed. Most failures were `ModuleNotFoundError: No module named 'musicark'`. The repository CI workflow installs the package with `pip install -e .` before running discovery.

For a comparable local full-suite run, use an isolated environment and install the project first:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

If `.venv` does not exist, create it before running these commands.
