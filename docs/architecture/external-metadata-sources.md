# External metadata sources

This document records the v0.12.0 source boundaries. Terms, quotas and commercial-use rules are version-sensitive and must be rechecked against each provider's official documentation before a public or monetized release.

| Source | Purpose | Authentication | Runtime policy | Important limitations |
| --- | --- | --- | --- | --- |
| Yandex Music | Existing trusted identity metadata | Existing MusicArk credential boundary | Existing direct Yandex path | External resolver does not change Yandex upload routing |
| AcoustID | Audio fingerprint → recording identity hint | Application client key | Up to documented public-service limit; centralized limiter | Free web service is intended for non-commercial use; audio file itself is not uploaded |
| MusicBrainz | Recording/release metadata, ISRC, release alternatives | No API key | Meaningful User-Agent; centralized 1 request/sec limiter | Core DB data and web-service terms are separate; public web service has commercial-use constraints |
| Cover Art Archive | Artwork for MusicBrainz Release/Release Group | None | On demand, bounded artwork handling | Public availability does not make the image copyright-free |
| Discogs | Optional release-level metadata fallback | User-supplied token when required | Optional/fail-isolated | Images/restricted data are not used as the primary artwork source; terms must be rechecked before distribution |
| TheAudioDB | Optional low-priority metadata fallback | User-supplied API key | Disabled/not configured without key | Free-tier rate and app-store/commercial restrictions must be rechecked before release |
| Last.fm | Optional low-priority supplemental metadata | User-supplied API key | Disabled/not configured without key | Commercial use requires separate review/agreement |

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

## Rate limiting and cache

Provider rate limits belong to one infrastructure boundary rather than ad-hoc sleeps in UI/provider methods. Positive responses use a bounded cache and negative responses use a shorter TTL. Cache duration must respect provider terms; v0.12.0 intentionally does not make external responses permanent source-of-truth data.

## Artwork

Cover Art Archive is the preferred non-Yandex release-artwork source because it is keyed by MusicBrainz release identity. MusicArk should request UI-sized thumbnails first and only fetch larger images when a user explicitly applies artwork. Binary artwork must stay behind the backend cache boundary and must not cross the Flutter JSON bridge.

## Privacy

Text metadata lookups can disclose artist/title/album or provider IDs to the selected API. AcoustID receives fingerprint + duration. The Local Library audio file is not uploaded to metadata services by this subsystem.

## Network restrictions

Every external source uses `ExternalNetworkTransport`, which supports Direct, Custom Proxy, WARP local proxy and Auto routing. Auto fallback is triggered only by transport-level connectivity failures. HTTP authorization, not-found, rate-limit and server responses remain provider responses and do not silently change routes.

The Windows-specific Cloudflare integration is an adapter below this provider-neutral layer. Mobile implementations can replace that adapter without changing MusicBrainz/AcoustID source code.

## Cloudflare component ownership

A pre-existing WARP installation remains user-owned. MusicArk records ownership only after its own verified installation succeeds. The future MusicArk uninstaller must preserve pre-existing WARP and must offer a keep option for MusicArk-installed WARP.
