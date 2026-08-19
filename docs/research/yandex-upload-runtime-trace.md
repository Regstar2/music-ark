# Yandex Upload Runtime Ground-Truth Workflow

## Purpose

The second v0.10.0 reverse-engineering round recovered the Yandex desktop upload request far enough to establish that stage-one authorization uses the normal account OAuth path, but static analysis cannot prove the final production hostname used for `loader/upload-url`.

The remaining proof step is therefore runtime ground truth: observe one normal, visible, user-owned upload in the already-authenticated official desktop client while MusicArk records only sanitized request structure and independently verifies the resulting playlist identity.

No raw HAR, raw CDP messages, browser profile, token, cookie, Authorization value, signed upload URL, or response body is persisted.

## Static investigation conclusion

The official researched `app.asar` SHA-256 is:

```text
8e7f4cec0776c39f194dee0a94086548d13f1465d46aa05d3e00a21624cbe80a
```

Confirmed stage-one structure:

```text
module 12690
  loader/upload-url
  getUploadUrl

12690 -> request module 31322
```

The request stack structurally resolves authorization to:

```text
common.oauth
this.config.params.common.oauth
scheme: OAuth
customApiTokenReferenced: false
```

The final prefix investigation reached:

```text
new 12690.S(...)
  prefixUrl = getTldHost(arg0, arg1, TLD_MARK)

TLD_MARK = {tld}
arg0 nearest use-site value = module 73202 property hooks
```

V40 corrected an important minified-local reuse error: the value used at the exact stage-one call site is `73202.hooks`, not the stale original module-32732 binding of that local.

V41-V43 then located module `73202` in the official upload chunk:

```text
app/_next/static/chunks/2248.c548ad7dd602472d.js
```

but `hooks` is not represented as a statically recoverable standard webpack named export, direct export, or CommonJS/object export in the packaged build. No allowlisted Yandex URL template can be proven from that property without runtime evaluation.

**Static prefix archaeology stops here.** Further regex/module-form probes would no longer provide a materially different proof path.

## Unified ground-truth PoC

Use:

```text
tools/yandex_upload_ground_truth_poc.py
```

It combines, in one process:

1. localhost-only Chromium DevTools Protocol observation;
2. optional sanitized renderer instrumentation;
3. a visible upload performed by the official Yandex Music desktop client;
4. MusicArk playlist snapshot and bounded read-back;
5. ground-truth analysis of stage one, stage two, and processing traffic;
6. one final `official-desktop-assisted` result.

The official desktop application performs the upload mutation. MusicArk does not extract its credentials and does not send the audio request on the assisted path.

### One-command local experiment

Use a dedicated user-owned test playlist and exactly one owned local file.

```powershell
Set-Location C:\Base\projects\MusicArk

git pull --ff-only origin agent/v0.10.0-yandex-upload-feasibility

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:MUSICARK_EXPERIMENTAL_YANDEX_UPLOAD = "1"

$YandexDir = Join-Path $env:LOCALAPPDATA "Programs\YandexMusic"
$YandexExe = Get-ChildItem -LiteralPath $YandexDir -Filter *.exe -File |
    Where-Object { $_.Name -notmatch 'Update|Uninstall|Squirrel' } |
    Sort-Object Length -Descending |
    Select-Object -First 1

if (-not $YandexExe) {
    throw "Could not locate the official Yandex Music executable."
}

.\.venv\Scripts\python.exe .\tools\yandex_upload_ground_truth_poc.py `
    --launch-exe $YandexExe.FullName `
    --port 9222 `
    --trace-duration 120 `
    --file "C:\PATH\TO\ONE_OWNED_TEST.mp3" `
    --playlist-kind 1055 `
    --confirm-owned-file `
    --confirm-desktop-upload `
    --readback-attempts 60 `
    --readback-delay 2
```

When the tool prompts:

1. switch to the visible, already-authenticated official Yandex Music client;
2. open the exact target playlist;
3. invoke its normal track-upload UI;
4. select exactly the same owned file passed to the PoC;
5. wait for the official application to finish its upload/processing indication;
6. return to the terminal and press Enter.

Do not modify that playlist through another client during the observation window.

## Produced reports

All outputs are sanitized JSON under `.musicark/research/`:

```text
yandex-upload-runtime-ground-truth.json
yandex-upload-ground-truth-decision.json
yandex-upload-ground-truth-poc.json
```

The runtime trace retains only structural information such as:

- scheme / host / path;
- HTTP method;
- query parameter names, not values;
- header names, not values;
- authorization-present boolean / source classification;
- HTTP status;
- structural response shape;
- stage-two multipart observation;
- processing/UGC request paths.

## Success definition

The assisted workflow succeeds only when playlist read-back observes exactly one unambiguous new track identity:

```json
{
  "transportMode": "official-desktop-assisted",
  "status": "verified",
  "readBack": {
    "verified": true,
    "ambiguous": false,
    "verifiedTrackId": "<new id>"
  }
}
```

If the same runtime trace also observes `/loader/upload-url`, the ground-truth decision records its real host/profile without exposing credentials. That host can then be supplied explicitly to the direct PoC's `--stage1-base-url`; there is no default host or fallback.

## Direct HTTP follow-up

The branch contains `YandexOAuthStage1Requester` and the direct PoC accepts an explicit ground-truth prefix:

```text
--stage1-base-url <verified HTTPS Yandex prefix>
```

It uses the already-saved MusicArk account OAuth credential. The token is never accepted as a CLI argument.

A direct `prepare` must not be attempted with a guessed host. If runtime ground truth provides a single host/profile, one controlled prepare may be run. Stage two remains separately guarded by `MUSICARK_YANDEX_UPLOAD_LIVE=1` and explicit upload confirmation.

## Safety boundary

Never persist or share:

- OAuth token values;
- `customApiToken` values;
- Cookie/session values;
- Authorization values;
- signed upload URLs;
- raw HAR or raw CDP logs;
- browser profiles;
- copied `app.asar`;
- extracted official JavaScript source.

CI runs only offline tests and sanitized static probes. It never performs a live Yandex mutation.

## Production state

Unchanged until a real one-file PoC is verified:

```text
can_upload_tracks = false
supports_user_uploads = false
```
