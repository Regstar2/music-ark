# Yandex Upload V10 — Cross-Chunk Export Alias Resolution

## Goal

V9 established a concrete structural relationship that was not visible in V7/V8:

- webpack module `39670` contains `customApiPrefixUrl`, `customApiToken`, and `prefixUrl`-related upload configuration;
- module `39670` imports module `70204` through a minified local alias;
- module `70204`, present in the selected app layout chunks, contains `UgcUploadHttpClient`, `BaseResourceHttpClient`, and `ResourceHttpClient` anchors.

However, V9 emitted no `resolved_edges`. Its export parser intentionally retained only human-readable interesting export names, while the actual webpack export key can be minified.

V10 closes only that gap. It does not broaden the network experiment.

## Tool

`tools/yandex_upload_export_alias_probe.py`

The probe:

1. identifies modules containing the `UgcUploadHttpClient` anchor;
2. extracts safe identifier-only webpack export mappings for those provider modules, including minified export keys;
3. identifies only modules importing those provider module IDs;
4. inspects only the proven import aliases for member/constructor/call use;
5. maps class spans containing the UGC anchor back to safe local symbols;
6. resolves an edge only when the importer's minified member matches an export whose local symbol is associated with the UGC anchor.

## Safety

V10 is offline-only and source-free in its output.

It does not emit:

- JavaScript source contexts;
- ordinary string values;
- OAuth/custom API token values;
- cookie/session values;
- Authorization or header values;
- raw ASAR contents;
- audio contents.

Sensitive identifier names are filtered where they could expose secret-bearing bindings. Existing structural config reporting continues to redact sensitive values.

## Decision gate

A useful V10 result must show all of the following:

```text
provider module 70204
-> anchor UgcUploadHttpClient
-> minified export key resolved to anchor-associated local symbol

importer module 39670
-> imports 70204 through local alias
-> alias.<same export key> used as constructor/call

resolved_edges
-> 39670 -> 70204
```

Only after that edge exists should the stage-one transport be changed. The concrete `prefixUrl`, header profile, and client type must still be derived from structural evidence rather than guessed.

## Production status

No production capability changes are allowed at this stage:

- `can_upload_tracks = false`;
- `supports_user_uploads = false`;
- no Upload UI;
- no Sync/Matching integration;
- no CI live upload;
- no repeated live `prepare` until the V10 gate is evaluated.
