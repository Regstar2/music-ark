# Known issues — v1.0 stabilization

Этот файл фиксирует release-blocking дефекты, найденные во время Windows acceptance, и состояние их исправлений. Статус `candidate fixed` означает, что изменение реализовано, но финальная ручная Windows-приёмка ещё не заменена автоматическими тестами.

## #39 — Responsiveness / Matching / large Coverage

- Version: v1.0 release candidate.
- Reproduction: библиотека ~5k+ треков; Matching, переключение вкладок, `Missing -> Select all`, массовые решения, возврат в Downloads/Wanted.
- Expected: UI остаётся отзывчивым; matching progress сохраняется; >5000 выбранных треков обрабатываются без одного oversized payload; Wanted обновляется при возврате.
- Actual before fix: Matching state терялся, UI мог получать `Not responding`, bulk payload >5000 отклонялся, Downloads/Wanted мог показывать устаревшее состояние.
- Cause: data pages пересоздавались при навигации; matching process не стримил progress и многократно открывал DB resources; Coverage materialized слишком мелкими страницами и отправлял один большой bulk request; persistent Downloads page не refresh'илась при re-entry.
- Fix: stable persistent pages, streamed matching progress, per-run DB/candidate reuse, Coverage reads до 2000, UI bulk chunks <=1000, refresh Downloads on activation.
- Check: automated regressions добавлены; previous Windows acceptance failed на старом follow-up build; свежий Windows large-library pass — `NOT VERIFIED`.
- Status: `candidate fixed`.

## #40 — Network settings / WARP coupling

- Version: v1.0 release candidate.
- Reproduction: открыть Settings и использовать application-managed WARP path; legacy `auto`/`warp` settings.
- Expected: release contract соответствует `System / Direct / Custom`, Custom не имеет silent Direct fallback, proxy password не сохраняется в JSON.
- Actual before fix: UI и backend содержали WARP install/status/control path и дополнительную release-risk поверхность.
- Cause: историческая v0.12 network implementation была сохранена в release candidate после изменения продуктового network standard.
- Fix: System/Direct/Custom only, legacy auto/warp -> System, WARP backend/UI implementation removed, source-key Settings card removed, installer/docs aligned.
- Check: backend/Flutter regression tests и manual checklist добавлены; финальный Trusted CI и Windows network pass — `NOT VERIFIED`.
- Status: `candidate fixed`.

## #41 — Yandex playback preparation latency

- Version: v1.0 release candidate.
- Reproduction: Play на Yandex track с cold playback cache, затем повтор того же трека.
- Expected: cached replay не делает network round-trip; UI показывает preparation state и не блокируется; latency имеет диагностические timing fields.
- Actual before fix: каждый Play проходил process/service preparation; disk cache проверялся только внутри download provider после token/service setup; payload всегда сообщал `cached=true`, даже для cold download.
- Cause: cache short-circuit находился слишком глубоко, а session-level prepared path не переиспользовался.
- Fix: disk cache проверяется до token/provider startup; cold/cache result различается; `cacheCheck/providerPrepare/total/bridgeRoundTrip` timing evidence; session-level prepared path reuse; spinner regression for pending preparation.
- Check: automated regressions добавлены; cold/cached Windows timing pass — `NOT VERIFIED`.
- Status: `candidate fixed`.
