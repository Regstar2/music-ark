# Yandex upload research V11 — symbol-role gate

## Purpose

V10 reduced the relevant cross-chunk relationship to one upload-config module and one provider module:

```text
39670 -> import 70204 as r
39670 -> uses r.Xc and r.RG
```

Module `70204` contains the `UgcUploadHttpClient`, `BaseResourceHttpClient`, and `ResourceHttpClient` anchors, but V10 could not associate the `UgcUploadHttpClient` anchor with one concrete minified export key. The two stable export keys actually used by module `39670` are `Xc` and `RG`.

V11 therefore narrows the static analysis to these two symbols only.

## Probe

`tools/yandex_upload_symbol_role_probe.py`

The probe reports, for export keys `Xc` and `RG`:

- their local minified symbol in each selected provider chunk;
- structural definition form such as class/function/import-member/call assignment;
- whether the smallest syntactic symbol region contains upload protocol anchors such as:
  - `UgcUploadHttpClient`;
  - `BaseResourceHttpClient`;
  - `ResourceHttpClient`;
  - `loader/upload-url`;
  - `getUploadUrl`;
  - `uploadFile`;
  - `createHttpOptions`;
  - `prefixUrl`;
- structural use classification for `r.Xc` and `r.RG` inside module `39670`.

## Safety

V11 is offline-only.

The report does not contain:

- JavaScript source context;
- arbitrary string values;
- OAuth/custom API token values;
- cookie/session values;
- Authorization/header values;
- raw ASAR contents;
- audio bytes.

No network request is made.

## Decision gate

Desired outcome:

```text
70204 export Xc or RG
-> symbol definition shape
-> upload-specific anchors in same syntactic region

39670
-> uses matching export
-> structural role in upload config
```

If one export is structurally identified as the UGC upload HTTP client, the next step is to trace only that export's constructor/configuration path to `prefixUrl`, request-header construction and `clientRemoteType`.

Do not repeat the live stage-one `prepare` request until that configuration path is established from static evidence. Production upload capabilities remain disabled.
