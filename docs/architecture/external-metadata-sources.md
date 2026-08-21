# External metadata sources

This document records the v0.12.0 source boundaries. Terms, quotas and commercial-use rules are version-sensitive and must be rechecked against each provider's official documentation before a public or monetized release.

| Source | Purpose | Authentication | Runtime policy | Important limitations |
| --- | --- | --- | --- | --- |
| Yandex Music | Existing trusted identity metadata | Existing MusicArk credential boundary | Existing direct Yandex path | External resolver does not change Yandex upload routing |
| AcoustID | Audio fingerprint → MusicBrainz-backed recording/release metadata | Bundled MusicArk application client key | Zero-config read-only lookup; centralized <=3 req/s limiter | Free web service is non-commercial; audio file itself is not uploaded |
| MusicBrainz | Best-effort text/recording fallback, ISRC, release alternatives | No API key | Meaningful User-Agent; centralized 1 request/sec limiter | Direct `musicbrainz.org` is not required after a successful AcoustID fingerprint match |
| Cover Art Archive | Artwork for MusicBrainz Release/Release Group | None | On demand, bounded artwork handling | Public availability does not make the image copyright-free |
| ListenBrainz / MusicBrainz Mapper | Optional MetaBrainz fallback to recover MusicBrainz IDs/release context | None for the read-only endpoints used here | Fallback only; not an additional mandatory dependency | Availability may differ by network; do not make it a single point of failure |
| Discogs | Optional release-level metadata fallback | Separate token/app auth | Advanced optional/fail-isolated | Images/restricted data are not used as the primary artwork source; authentication and terms must be rechecked before distribution |
| TheAudioDB | Optional low-priority metadata fallback | Documented public free-tier key in development/free builds; override supported | Optional/fail-isolated | Free-tier/app-store/commercial restrictions must be rechecked before release |
| Last.fm | Deferred optional supplemental metadata | Application API key | Disabled unless an app/developer key is available; not required for v0.12 completion | API-account availability and commercial-use requirements must be revalidated before enabling in release builds |

## Provider credentials

Ordinary MusicArk users must not be required to create developer accounts for the default metadata workflow.

AcoustID distinguishes two different key types:

```text
application client key -> identifies MusicArk for read-only lookup
user API key           -> identifies a user for fingerprint submissions
```

MusicArk bundles only its application client key and uses it in the public `client` lookup parameter. AcoustID user submission keys are not implemented or stored. The bundled application key is an application identifier shipped with the client, not a user-account secret.

Developers can override the bundled AcoustID key with:

```text
MUSICARK_ACOUSTID_CLIENT_KEY
```

Other provider secrets/tokens and proxy passwords remain separate from application identifiers and must never be committed to diagnostics or normal preference JSON. Local user/developer overrides are stored through the OS keyring where supported.

TheAudioDB's documented public free-tier key is treated as a non-secret development/free fallback only. Its licensing/distribution conditions must be rechecked before a public/app-store/commercial release.

## Provider-neutral contract

External services emit `ExternalMetadataCandidate` instead of provider DTOs. A candidate carries normalized fields, external identities, per-field provenance, typed evidence and confidence category. Recording and Release identities are deliberately separate.

```text
External source DTO
-> source adapter
-> ExternalMetadataCandidate
-> Compare
-> explicit selected-field Apply
-> existing MetadataEditorService
```

No source adapter is allowed to mutate local audio.

## Default identification path

The preferred zero-config path is:

```text
local audio
-> Chromaprint/fpcalc
-> AcoustID
   -> Recording MBID
   -> title / artist
   -> release / release-group
   -> ISRC when available
-> Cover Art Archive
```

This deliberately avoids making `musicbrainz.org` a mandatory runtime hop in networks where that host is filtered or behaves inconsistently through a proxy. Direct MusicBrainz remains available as a best-effort text fallback.

## Rate limiting and cache

Provider rate limits belong to one infrastructure boundary rather than ad-hoc sleeps in UI/provider methods. Positive responses use a bounded cache and negative responses use a shorter TTL. Cache duration must respect provider terms; v0.12.0 intentionally does not make external responses permanent source-of-truth data.

## Artwork

Cover Art Archive is the preferred non-Yandex release-artwork source because it is keyed by MusicBrainz release identity. MusicArk should request UI-sized thumbnails first and only fetch larger images when a user explicitly applies artwork. Binary artwork must stay behind the backend cache boundary and must not cross the Flutter JSON bridge.

## Privacy

Text metadata lookups can disclose artist/title/album or provider IDs to the selected API. AcoustID receives fingerprint + duration. The Local Library audio file is not uploaded to metadata services by this subsystem.

## Network restrictions

Every external source uses `ExternalNetworkTransport`, which supports Direct, Custom Proxy, WARP local proxy and Auto routing. Auto fallback is triggered only by transport-level connectivity failures. HTTP authorization, not-found, rate-limit and server responses remain provider responses and do not silently change routes.

The default fingerprint flow does not require direct MusicBrainz connectivity. CAA and other external sources can independently use Direct/WARP/custom proxy routing as needed. TLS certificate verification remains enabled for every route.

The Windows-specific Cloudflare integration is an adapter below this provider-neutral layer. Mobile implementations can replace that adapter without changing provider code.

## Cloudflare component ownership

A pre-existing WARP installation remains user-owned. MusicArk records ownership only after its own verified installation succeeds. The future MusicArk uninstaller must preserve pre-existing WARP and must offer a keep option for MusicArk-installed WARP.
