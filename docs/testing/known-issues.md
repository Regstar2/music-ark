# Known issues — v1.0 stabilization

Этот файл фиксирует release-blocking дефекты, найденные во время Windows acceptance, и состояние их исправлений. Текущий consolidated review выполняется в ветке `fix/v1.0-acceptance-round2`. Статус `candidate fixed` означает, что изменение реализовано, но финальная ручная Windows-приёмка не заменена автоматическими тестами.

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

## #45 — Matching batch persistence lock

- Version: v1.0 acceptance round 2.
- Reproduction: запустить Matching на большой библиотеке; процесс останавливается с `Failed to persist matching batch.`.
- Expected: bounded matching batches сохраняются на протяжении всего run без SQLite writer contention.
- Actual before fix: optimized run держал SQLite connection для preloaded/candidate reads, но каждые 250 решений `persist_batch()` открывал отдельное write connection.
- Cause: второй writer path внутри long-lived optimized run.
- Fix: bounded batch persistence выполняется на том же SQLite connection, который обслуживает optimized run.
- Check: regression запрещает вызов repository `persist_batch()` из optimized hot loop; Windows 5k+ run — `NOT VERIFIED`.
- Status: `candidate fixed`.

## #46 — Missing select-all / bulk Wanted feedback

- Version: v1.0 acceptance round 2.
- Reproduction: ~5k+ Missing -> `Выбрать все` -> массово `Нужен`.
- Expected: пользователь сразу видит, что операция началась, и processed/total растёт до завершения; UI продолжает обрабатывать события.
- Actual before fix: операции были bounded, но во время нескольких bridge calls интерфейс почти не давал обратной связи и выглядел зависшим.
- Cause: bulk state переиспользовал общий loading flag либо вообще не имел пользовательского progress state.
- Fix: отдельные select-all и bulk-action busy/progress states, 2000-row reads, 1000-ID writes, yield между chunks, incremental visible-row update.
- Check: widget regression блокирует bridge call и проверяет видимый progress; Windows 5k+ pass — `NOT VERIFIED`.
- Status: `candidate fixed`.

## #47 — stale Wanted/queue state in Downloads

- Version: v1.0 acceptance round 2.
- Reproduction: отметить тысячи Missing как Wanted и сразу открыть Downloads; после enqueue не покидать страницу.
- Expected: Wanted counter и persisted task queue обновляются без открытия специальной вкладки или page re-entry.
- Actual before fix: initial Downloads load читал только task state; Wanted загружался позже при открытии таба, а post-enqueue task list обновлялся только после долгого worker call.
- Cause: persistent page freshness была scoped только к активному sub-tab и mutation completion.
- Fix: initial/reactivation/manual refresh обновляет task + Wanted state; enqueue refresh выполняется до запуска worker.
- Check: widget regressions проверяют initial Wanted count и reactivation; Windows pass — `NOT VERIFIED`.
- Status: `candidate fixed`.

## #48 — Download All queue execution visibility

- Version: v1.0 acceptance round 2.
- Reproduction: Downloads -> Wanted -> `Скачать все` на нескольких тысячах Wanted tracks.
- Expected: enqueue виден сразу, queue появляется до первого download, затем отображаются worker processed/total и per-track progress; downloads start automatically.
- Actual before fix: UI awaited one monolithic `run_tasks` process for the whole batch; controls gray-out, queue refresh and task progress appeared only after return/page re-entry. Task discovery was also limited to 5000 IDs per read.
- Cause: queue creation and long execution were combined into one awaited UI operation; polling was absent; 5000-task read boundary truncated large queue visibility.
- Fix: enqueue -> immediate full refresh -> asynchronous bounded one-task worker; lightweight 800ms running/summary poll; queue drain refetches later batches; summary counts persisted user tasks directly and is not truncated at 5000.
- Check: Python regression covers 5247 persisted queue count; widget regression blocks first worker task and verifies visible operation progress after enqueue; Windows bulk download pass — `NOT VERIFIED`.
- Status: `candidate fixed`.

## #50 — Portable ZIP creation / temporary Windows file lock

- Version: v1.0 acceptance round 2.
- Reproduction: Windows packaging reaches archive creation; a staged PyInstaller/keyring file is temporarily held by another process; `Compress-Archive` emits `IOException`, then packaging still prints success while no ZIP/SHA256 exists.
- Expected: transient sharing violations are retried; persistent archive errors terminate packaging; success is printed only after a non-empty ZIP and checksum file exist.
- Actual before fix: PowerShell Archive module emitted a non-terminating error that bypassed the script's intended fail-fast behavior.
- Cause: archive creation had no explicit verified postcondition and relied on `Compress-Archive` error semantics.
- Fix: use `System.IO.Compression.ZipFile.CreateFromDirectory` with four bounded retry attempts/backoff; delete partial archives between attempts; require non-empty ZIP and `SHA256SUMS.txt` before success output.
- Check: fresh Windows portable packaging pass — `VERIFIED 2026-08-26` on old pre-#51 HEAD `0b2c12d`; repeat on #51 candidate still required.
- Status: `candidate fixed`.

## #51 — 5k Yandex download worker / session churn

- Version: v1.0 acceptance round 2.
- Reproduction: ~5k Missing/Wanted -> Downloads -> `Скачать все`; observe mixed `provider_request`, apparent `authentication`, unavailable and UGC UUID failures.
- Expected: one sequential worker/session handles the queue; transient provider/network failures retry with bounded backoff; a true auth/systemic outage pauses instead of marking the remaining thousands failed; permanent per-track failures do not stop unrelated tracks.
- Actual before fix: Flutter called `runTask` once per row and every call used `Process.run`, rebuilding Python, `DownloadService` and `Client(token).init()` thousands of times. Broad exception mapping could mislabel provider/network initialization failures as authentication, and the UI continued after each persisted failed task.
- Fix: `DownloadBridge.runTask` now uses one persistent JSON-lines `musicark.download.worker_bridge`; one `DownloadService` registers one `ResilientYandexMusicDownloadProvider` and reuses its initialized Yandex client. Transient network/timeout/429/5xx classes use bounded exponential backoff; auth is distinct; three consecutive systemic failures trip a circuit breaker. The pausing response terminates the worker so explicit Continue starts a fresh session. `track_unavailable`, `no_download_info` and `ugc_unsupported` remain per-track failures. >5000 persisted rows are drained in bounded batches and frozen runtime whitelists worker/batch bridges.
- Tests: client reuse, retry/backoff, permanent rejection, UGC UUID classification, immediate auth circuit, three-failure systemic circuit, permanent-error reset, JSON protocol safety, 5247-row bounded queue continuation, Flutter bridge source contract and frozen-runtime entry points.
- Check: automated suite and fresh Windows ~5k real-account acceptance on the new commit — `NOT VERIFIED`.
- Status: `candidate fixed`.
