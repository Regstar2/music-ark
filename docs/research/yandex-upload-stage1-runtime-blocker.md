# Yandex Single-Track Upload — Stage-One Runtime Blocker

## Decision

Yandex Music own-track upload is **feasible at the service/protocol level**, but direct MusicArk single-track upload through the existing credential boundary is **BLOCKED** at the official desktop stage-one runtime profile.

This is not a statement that Yandex cannot upload local tracks. The official product does. The blocker is reproducing the official authenticated `loader/upload-url` request legitimately from MusicArk without extracting private desktop configuration.

## Confirmed protocol

Official researched desktop `app.asar` SHA-256:

`8e7f4cec0776c39f194dee0a94086548d13f1465d46aa05d3e00a21624cbe80a`

Recovered with high confidence:

- stage one: `POST loader/upload-url`;
- stage-one fields: `uid`, `playlist-id`, optional `visibility`, `path`;
- stage two: POST to the dynamic URL returned by stage one;
- stage-two body: multipart `FormData` field `file`;
- stage two excludes the ordinary Music API header set;
- processing lifecycle includes preparing/uploading/processing, retry/abort, `checkProcessingTracks`, and `moveTracksFromUploadCenterToPlaylist`.

## Existing live evidence

One guarded stage-one `prepare` was previously sent through the ordinary pinned `yandex-music==3.0.0` request profile.

Observed result:

```text
RemoteDisconnected('Remote end closed connection without response')
```

No HTTP status was returned. No dynamic upload URL was obtained. Stage two was not sent and no audio bytes were uploaded.

The pinned Python client uses an Android-oriented Music API profile. The failed request therefore does not prove a bad playlist ID or path; it proves only that the ordinary MusicArk request profile is not a verified reproduction of the desktop UGC request.

## Runtime-profile evidence

The final source-free probes intentionally emit no JavaScript source, token/header values, query values, raw ASAR bytes, or credentials.

### Upload resource module

The official upload/API chunk places `loader/upload-url` and `getUploadUrl` in webpack module:

```text
12690
```

Module `12690` directly depends on request-construction module:

```text
12690 -> 31322
```

Module `31322` contains the allowlisted request anchors/properties:

```text
createHttpOptions
createRequestHeaders
prefixUrl
authorization
headers
```

Therefore the official stage-one resource is not merely a relative URL sent through an arbitrary generic client; it is wired to a request layer that requires a configured prefix and authorization/header construction.

### Production serialized runtime configuration

Across the official packaged runtime snapshots, the sanitized value-kind probe observes:

```text
customApiPrefixUrl:
  non-empty opaque string in 79 members

customApiToken:
  non-empty redacted sensitive value in 81 members

prefixUrl:
  empty string in 2 members
  identifier/reference forms in 10 members
```

The `customApiPrefixUrl` value remains opaque after safe JSON-unescape. It is not recoverable as an allowlisted public Yandex HTTP(S) host/path or safe relative prefix without exposing arbitrary runtime string contents.

The `customApiToken` value is deliberately never emitted or inspected.

## Why direct HTTP implementation stops here

MusicArk can reproduce the **shape** of stage one, but cannot currently supply a verified legitimate production `prefixUrl + authorization` profile.

The available evidence leaves two possibilities:

1. the desktop custom prefix/token are required by the production upload request; or
2. a separate public profile exists, but its mapping to `loader/upload-url` has not been established from any public/legitimate source.

Neither case permits replacing the failed Android-oriented request with guessed hosts, User-Agents, headers, or credentials.

Extracting/copying the packaged `customApiToken`, arbitrary opaque runtime prefix values, cookies, or browser session material is explicitly outside the MusicArk security boundary.

Accordingly, the exact blocker is:

> **No verified public stage-one prefix/authorization contract is available through MusicArk's existing OAuth credential boundary, while the official desktop production runtime uses opaque custom API configuration.**

## Implementation consequence

`YandexUploadTransport` now has a fail-closed stage-one boundary:

- there is no default fallback to `client.base_url`;
- `prepare_upload()` requires an explicitly injected verified stage-one requester;
- the CLI PoC injects no private requester and therefore blocks before credential resolution, playlist reads, or upload mutation;
- the recovered stage-one query mapping remains unit-testable through an injected fake requester;
- stage-two multipart/header isolation remains unit-testable independently.

This prevents repeating the previous unverified request profile accidentally.

## Read-back correctness

The PoC also now requires an unambiguous uploaded identity:

- a stage-two track ID verifies only when that ID is newly observed after upload;
- exactly one new read-back ID may verify via set difference;
- multiple unknown new IDs are marked ambiguous and **do not** produce `verified`.

HTTP 2xx alone never means success.

## Production capability state

Unchanged:

```text
can_upload_tracks = false
supports_user_uploads = false
```

No Upload UI, bulk queue, reverse Sync, Matching/Coverage integration, or background uploader is enabled.

## Reopening the implementation

Direct single-track upload can be reopened if at least one legitimate source provides the missing stage-one contract, for example:

- Yandex publishes/supports a user-file upload API suitable for normal account credentials;
- an approved client library exposes it;
- a future official desktop/web build exposes a public non-secret prefix/client profile that can be tied structurally to `loader/upload-url` without extracting private credentials.

Until then, no live `prepare` or upload retry should be performed from MusicArk.
