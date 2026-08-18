# Yandex Upload Protocol — V8 HTTP-client configuration bindings

## Why V8 exists

The first account-owned `prepare` request reached stage one but ended with a connection close before any HTTP response:

```text
RemoteDisconnected('Remote end closed connection without response')
```

No stage-two request was sent and no audio bytes were uploaded.

V7 then established that the official desktop upload area contains configuration identifiers including:

- `customApiPrefixUrl`;
- `customApiToken`;
- `getApiPrefixUrl`;
- `clientSafeConfig` / `getClientSafeConfig`;
- `clientRemoteType`;
- `createRequestHeaders` / `createSessionRequestHeaders`;
- `YandexMusicDesktopApp` / `YandexMusicWebNext`.

This means the previous assumption that the desktop UGC resource can be reproduced by simply reusing the normal `yandex-music==3.0.0` Android-oriented request client is not established.

## V8 goal

`tools/yandex_upload_config_binding_probe.py` recovers only structural relationships between those configuration concepts. It is designed to answer questions such as:

```text
customApiPrefixUrl <- getApiPrefixUrl(...)
prefixUrl <- config.customApiPrefixUrl
clientRemoteType <- YandexMusicDesktopApp
headers <- createRequestHeaders(...)
UgcUploadHttpClient(...)
```

The exact relationships above are examples of what the probe can report when present; they are not claimed until a real V8 report confirms them.

## Safety

V8 performs no network requests and emits no JavaScript source.

For sensitive configuration keys such as `customApiToken`, only the key name and the fact that its value is redacted are retained. Token values, cookies, authorization values, ordinary string values, raw source contexts and raw file contents are excluded.

## Decision gate

Do not retry live `prepare` until V8 establishes enough of the desktop HTTP-client configuration to decide whether MusicArk's current stage-one host/header profile is structurally compatible.

Production capabilities remain unchanged:

```text
can_upload_tracks = false
supports_user_uploads = false
```
