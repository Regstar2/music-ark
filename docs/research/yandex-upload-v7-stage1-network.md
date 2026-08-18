# Yandex Upload Protocol — V7 Stage-One Network Gate

## Status

The first account-owned `prepare` run reached the stage-one request boundary but did not receive an HTTP response. Production upload remains disabled.

## Local verification reported by the project owner

Focused offline suites on Windows completed successfully:

```text
test_yandex_upload_binding_probe.py   2/2 OK
test_yandex_upload_transport.py       4/4 OK
```

This confirms the local V6 parser regression was fixed and the isolated transport unit contract still passes.

## First live stage-one result

The project owner selected an existing user playlist and an existing local MP3, enabled only the research flag, explicitly kept `MUSICARK_YANDEX_UPLOAD_LIVE` unset, and ran `prepare`.

Observed result:

```text
RemoteDisconnected('Remote end closed connection without response')
```

No stage-two request was sent and no audio bytes were uploaded by the PoC runner.

## What this proves

- local file validation succeeded;
- user-playlist resolution succeeded;
- authenticated Yandex client construction succeeded;
- execution reached the stage-one HTTP request;
- the remote side closed the connection before the current client received a normal HTTP response.

It does **not** prove:

- that the OAuth token was rejected;
- that the recovered query bindings are wrong;
- that the playlist UUID/kind choice is wrong;
- that the path form is wrong;
- that `https://api.music.yandex.net` is the official desktop upload resource host.

## Corrected host assumption

Earlier notes used the pinned `yandex-music==3.0.0` base URL (`https://api.music.yandex.net`) as the stage-one PoC host. That base URL is verified for the Python library's normal Music API requests, but V3-V6 did not independently prove that the desktop `UgcUploadHttpClient` resolves `loader/upload-url` against the same host.

The live disconnect means this must remain a hypothesis until the official desktop HTTP-client configuration is recovered.

## Python client fingerprint

Pinned `yandex-music==3.0.0` sends normal requests with a Python/Android-oriented client fingerprint, including:

```text
User-Agent: Yandex-Music-API
X-Yandex-Music-Client: YandexMusicAndroid/...
Authorization: OAuth <existing token>
```

The credential value is not part of research output. The relevant uncertainty is whether the desktop-only upload resource accepts the same host/header profile.

## V7 static probe

`tools/yandex_upload_http_client_probe.py` is the next non-mutating step.

It inspects only already identified official `app.asar` members and emits:

- sanitized absolute URL literals (scheme + host + path only);
- Yandex host-like literals;
- HTTP header **names** only;
- protocol-related identifiers near upload HTTP-client anchors;
- anchor offsets/member identity.

It does not emit:

- source-code contexts;
- header values;
- OAuth/cookie/session values;
- query values;
- raw application/audio contents;
- network requests.

## Decision gate

Do not retry live stage one with guessed User-Agent/header/host combinations.

Next sequence:

```text
V7 desktop HTTP-client structure
-> establish or reject current host/header hypothesis
-> update isolated prepare transport
-> one stage-one prepare retry
-> only after upload URL is obtained consider stage two
```

Production capabilities remain:

```text
can_upload_tracks = false
supports_user_uploads = false
```
