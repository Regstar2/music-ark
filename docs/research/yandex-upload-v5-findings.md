# Yandex Upload Protocol — V5 Contract Findings

## Status

Research only. Production upload capabilities remain disabled.

V5 moves the static evidence from call-site proximity to source-free invocation and HTTP target relationships. It is now clear how the upload model calls the two upload API methods, but the exact nested request-option bindings still need one final static pass before a live PoC is justified.

## Source artifact

Official desktop `app.asar` SHA-256:

```text
8e7f4cec0776c39f194dee0a94086548d13f1465d46aa05d3e00a21624cbe80a
```

No raw `app.asar`, JavaScript source window, credential value, cookie, authorization value, or audio payload is committed.

## High-confidence V5 findings

The API/resource chunk:

```text
app/_next/static/chunks/2248.c548ad7dd602472d.js
```

exposes source-free function signatures:

```text
getUploadUrl(t, e)
uploadFile(t, e)
```

and contains these directly observed HTTP relationships:

```text
POST loader/upload-url
POST t.url
```

The second relationship is important: the upload-file transport posts to the `url` member of its first argument rather than to a fixed Music API path.

The upload-model chunk:

```text
app/_next/static/chunks/959-1d400e8429175934.js
```

calls the API layer with these argument shapes:

```text
getUploadUrl({
  playlistId,
  uid,
  path
})

uploadFile({
  url,
  formData
}, {})
```

The same model contains:

- `FormData.append("file", ...)` shape, represented by field name `file`;
- `uploadUrl`;
- `.url` member accesses in the upload flow;
- `file.trackId` accesses after upload/processing;
- `playlistKind` and processing-state machinery.

## Current source-supported transport model

```text
explicit playlist/local file context
  -> getUploadUrl({playlistId, uid, path})
  -> POST loader/upload-url
  -> receive/use dynamic URL (exact response binding still to confirm)
  -> FormData field: file
  -> uploadFile({url, formData}, options)
  -> POST firstArgument.url
  -> asynchronous server processing
  -> track identity becomes available
  -> move processed UGC track into target playlist
```

## What V5 proves vs. what remains inferred

Proven statically:

- stage one is a POST to `loader/upload-url`;
- the upload model provides `playlistId`, `uid`, and `path` to `getUploadUrl`;
- stage two receives an object containing `url` and `formData`;
- stage two POSTs to the supplied `.url`;
- the multipart form field is `file`;
- processing continues after the byte upload.

Still not proven at exact binding precision:

- whether `playlistId`, `uid`, and `path` are search parameters, body fields, headers, or transformed before stage one;
- exact response property returned by stage one and how it becomes the model's `uploadUrl`;
- whether stage two maps `formData` directly to `body`;
- exact retry and abort-signal option bindings;
- authentication type required by stage one;
- whether stage two is a pre-signed URL with no Yandex authorization requirement;
- processing completion response and final UGC track identity contract.

## V6 binding probe

`tools/yandex_upload_binding_probe.py` analyzes only the bodies of the selected `getUploadUrl` and `uploadFile` methods. It emits:

- parameter names;
- accesses such as `t.playlistId`, `t.uid`, `t.path`, `t.url`, `t.formData`;
- direct HTTP call shape inside each function body;
- nested object bindings such as `searchParams.playlist-id -> t.playlistId` when present;
- `body`, `signal`, retry-header and related option bindings;
- form-field names.

It does not emit raw JavaScript or ordinary string values.

Suggested Windows run:

```powershell
python .\tools\yandex_upload_binding_probe.py `
  "C:\Users\Царь\AppData\Local\Programs\YandexMusic\resources\app.asar" `
  --offset 10176266 `
  --output .\.musicark\research\yandex-upload-binding-v6.json
```

## Decision gate

Do not implement the live transport solely from V5. If V6 proves the stage-one and stage-two option bindings, the next step can be an isolated opt-in `YandexUploadTransport` PoC using MusicArk's existing `YANDEX_MUSIC_TOKEN` boundary, with production capabilities still disabled until one real upload is followed by successful playlist read-back verification.
