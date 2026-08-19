# Yandex Upload Protocol — V9 Webpack Module Wiring

## Why V9 exists

V8 confirmed several configuration relationships inside the official desktop HTTP stack, including:

- request prefix selection through `this.config.prefixUrl`;
- request/session header factories;
- `clientRemoteType` as configuration data;
- separate `customApiPrefixUrl`, `customApiToken`, and `clientSafeConfig` concepts in the desktop model bundle.

However, V8 scans object/call expressions without resolving webpack module boundaries. It therefore cannot prove which concrete configuration is supplied to `UgcUploadHttpClient` when that symbol is imported, aliased, or registered indirectly.

The first live `prepare` attempt remains inconclusive because the remote side disconnected before an HTTP response. No stage-two request or audio upload occurred.

## V9 goal

V9 resolves only the structural module wiring needed for the next decision gate:

```text
webpack module containing UgcUploadHttpClient
-> named export / local minified symbol
-> importing module and local alias
-> constructor/member use
-> constructor argument expression kinds
-> relevant prefix/header/client-type bindings
```

This is intended to establish whether the UGC upload client is wired to the same ordinary Music API configuration used by `yandex-music==3.0.0`, or to a separate desktop/web configuration path.

## Added probe

`tools/yandex_upload_module_wiring_probe.py`

The probe:

- reads only user-selected, already identified members from the official `app.asar`;
- detects webpack module boundaries;
- records numeric module IDs;
- records interesting named exports and their local symbols;
- records numeric-module import aliases;
- records imported `UgcUploadHttpClient` member/constructor uses;
- records constructor argument **kinds**, not arbitrary scalar values;
- records relevant V8 configuration bindings using the existing sanitizer;
- emits resolved module-to-module edges when an imported named export can be linked to its source module.

## Safety boundary

V9 performs no network I/O and emits no:

- JavaScript source contexts;
- OAuth/token values;
- cookie/session values;
- header values;
- ordinary string values;
- raw ASAR contents;
- audio contents.

Sensitive configuration keys may appear by name, but their values remain redacted by the existing V8 sanitizer.

## Decision gate

Do not retry live `prepare` yet.

Proceed only after V9 establishes enough module wiring to choose a stage-one host/client/header profile from evidence rather than guesswork.

Production capability flags remain disabled regardless of V9 output:

```text
can_upload_tracks = false
supports_user_uploads = false
```

A future successful stage-one request still does not prove upload support. Final experimental validation requires an explicit user-owned file, successful stage two, server processing, and target-playlist read-back observing a new track identity.
