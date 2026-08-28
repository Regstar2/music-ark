# Yandex Upload Protocol — V4 Call-Site Findings

## Status

Research only. Production upload capabilities remain disabled.

The V4 call-site report narrows the official desktop client's UGC upload flow enough to confirm a two-stage request architecture, but the exact response field and authentication requirements still need to be recovered before a live MusicArk upload PoC is justified.

## Source artifact

Official desktop `app.asar` SHA-256:

```text
8e7f4cec0776c39f194dee0a94086548d13f1465d46aa05d3e00a21624cbe80a
```

No raw ASAR, source window, credential, cookie, Authorization value, or audio payload is committed.

## Stage one — request upload URL

In:

```text
app/_next/static/chunks/2248.c548ad7dd602472d.js
```

V4 puts the first concrete `getUploadUrl` occurrences in the same small structural window as:

- `POST loader/upload-url`;
- `playlist-id`;
- `x-retry-count`;
- `searchParams`;
- playlist/playlistId identifiers.

This is stronger than the V3 member-wide association. The likely request builder is now localized to the first `getUploadUrl` call sites around member positions `12072` / `12180`.

The report does not yet prove whether `playlist-id` is nested under `searchParams` or another request option. V5 exists specifically to recover this relationship without emitting source code.

## Stage two — upload file to dynamic URL

The same API chunk contains later `uploadFile` occurrences around positions `89934` / `90026` with:

- a direct `POST` whose target is an identifier (`t` in the minified bundle), not a fixed endpoint literal;
- `body` / `json` option identifiers nearby;
- `x-retry-count`;
- abort/retry identifiers.

Separately, the upload-model chunk:

```text
app/_next/static/chunks/959-1d400e8429175934.js
```

links `uploadFile` to:

- `uploadUrl`;
- `FormData.append("file", ...)` represented by the safe field name `file`;
- `AbortController`;
- `retryUpload` / `abortUpload`;
- `runUpload` / `runUploadTracksQueue`.

The strongest source-supported interpretation is therefore:

```text
getUploadUrl(playlist target)
  -> POST loader/upload-url
  -> obtain dynamic URL
  -> create FormData(file)
  -> uploadFile(dynamic URL, form body, retry/abort state)
  -> POST dynamic URL
```

## Processing and playlist completion

The model chunk also confirms that transport completion is not final success. It tracks:

```text
preparingTracks
uploadingTracks
processingTracks
```

and then uses:

- `checkProcessingTracks`;
- `getTracksMeta` / track identifiers;
- `moveTracksFromUploadCenterToPlaylist`.

A MusicArk implementation must therefore verify the uploaded UGC track after processing instead of treating the file POST response alone as success.

## Existing MusicArk credential boundary

`YandexMusicProvider` already resolves `YANDEX_MUSIC_TOKEN` and creates `yandex_music.Client(token).init()` for authenticated provider operations.

That token is the only credential candidate that should be tried by a future experimental transport. V4 does **not** establish that `loader/upload-url` accepts it, so no production capability is enabled and no separate browser-cookie/session flow is introduced.

## Remaining blockers

Before an experimental live request:

1. prove whether `playlist-id` is a search parameter, header, or body key;
2. recover the stage-one response field used as the dynamic upload URL;
3. recover the exact stage-two option shape (`body` versus `json`, headers, abort signal);
4. identify the authentication style applied to stage one;
5. determine whether stage two uses a pre-signed unauthenticated URL or reuses Music API auth;
6. determine how processing completion exposes the uploaded track identity.

## V5 contract-shape probe

`tools/yandex_upload_contract_probe.py` extracts source-free relationships from the selected ASAR members:

- selected function parameter names;
- direct `httpClient` targets and methods;
- request option keys;
- nested `searchParams` and `headers` key names;
- `body` / `json` / `signal` presence;
- argument shapes for `getUploadUrl`, `uploadFile`, and `runUpload`;
- relevant member access such as a returned `.url` field;
- `FormData.append` field names.

Suggested Windows run:

```powershell
python .\tools\yandex_upload_contract_probe.py `
  "<YandexMusic install dir>\resources\app.asar" `
  --offset 10176266 `
  --offset 16146222 `
  --output .\.musicark\research\yandex-upload-contract-v5.json
```

Focused test:

```powershell
python -m unittest discover -s tests -p "test_yandex_upload_contract_probe.py" -v
```

Only the generated sanitized JSON should be shared for analysis.
