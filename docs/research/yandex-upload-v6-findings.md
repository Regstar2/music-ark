# Yandex Upload Protocol — V6 Bindings and Live PoC Gate

## Status

Static request binding recovery is complete enough for an isolated, explicitly opt-in live proof of concept. Production upload capabilities remain disabled.

Official desktop `app.asar` SHA-256:

```text
8e7f4cec0776c39f194dee0a94086548d13f1465d46aa05d3e00a21624cbe80a
```

## V6 confirmed bindings

The official desktop client API-layer function `getUploadUrl(t, e)` reads:

- `t.uid`;
- `t.playlistId`;
- `t.visibility`;
- `t.path`.

The same function performs:

```text
POST loader/upload-url
```

Its recovered request-object structure contains bindings:

```text
uid         <- t.uid
playlist-id <- t.playlistId
visibility  <- t.visibility
path        <- t.path
```

The official API-layer function `uploadFile(t, e)` reads:

- `t.url`;
- `t.formData`.

It performs:

```text
POST t.url
body <- t.formData
```

The same function contains `excludeHeaders` / `withoutHeaders` structure. This is strong evidence that normal Yandex Music API headers are intentionally excluded from the dynamic upload request.

Earlier V5 model-level evidence established:

```text
getUploadUrl({playlistId, uid, path})
uploadFile({url, formData}, {...})
FormData field = file
```

Taken together, V3-V6 establish the transport shape without raw Electron source or credential extraction.

## Pinned client authentication boundary

MusicArk uses `yandex-music==3.0.0`.

That client uses:

```text
base URL: https://api.music.yandex.net
Authorization: OAuth <existing user token>
```

for normal Music API requests. The live PoC reuses the already-saved MusicArk token only for stage one. It does not accept a token on the command line.

## Experimental transport

`src/musicark/providers/yandex_upload_transport.py` implements only the recovered two-stage wire boundary:

1. authenticated stage-one request to `loader/upload-url` with the recovered query fields;
2. multipart `POST` to the returned dynamic URL using field `file` and without copying Yandex OAuth/session headers.

The transport does not enable any provider capability and is not used by Sync or the UI.

## Live runner

`tools/yandex_upload_live_poc.py` is the only live entry point added by this research.

Safety gates:

- existing MusicArk credential store / provider token resolution only;
- no `--token` argument;
- experimental upload config/env opt-in required;
- explicit local file required;
- `--confirm-owned-file` required;
- `prepare` requires `--confirm-prepare` and sends stage one only;
- `upload` additionally requires `MUSICARK_YANDEX_UPLOAD_LIVE=1` and `--confirm-upload`;
- signed dynamic upload URL is never printed;
- response output is structural/sanitized;
- a 2xx upload response is not considered final success;
- final success requires playlist read-back to observe a new track identity.

## Playlist identifier uncertainty

The static bundle distinguishes upload `playlistId` from upload-center `playlistKind`, while the public Python model exposes both playlist `kind` and `playlist_uuid`.

The PoC therefore makes this choice explicit:

```text
--playlist-id-source uuid
--playlist-id-source kind
```

The default is `uuid`, but `prepare` performs no file upload and exists specifically to validate the stage-one contract before mutation. There is no automatic fallback that could hide a protocol mismatch.

## Path field uncertainty

The recovered API receives a `path` value, but static structure alone does not prove whether the official caller supplies an absolute local path or only a file name in every packaging mode.

The PoC therefore exposes the explicit research choice:

```text
--path-mode full
--path-mode name
```

The default is `full`, matching the desktop-file interpretation. Again, `prepare` is used before file upload.

## Success gate

Do not change:

```text
can_upload_tracks = false
supports_user_uploads = false
```

until one explicit user-owned test file completes all of these steps:

```text
stage one accepted
-> dynamic URL obtained
-> stage two accepted
-> server processing completes
-> target playlist read-back shows a new track identity
```

Only that read-back result can change the feasibility outcome from blocked-for-production to experimentally validated.
