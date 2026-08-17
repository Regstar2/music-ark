# Metadata editor architecture

The metadata editor is an explicit-write subsystem under `src/musicark/metadata/`.

## Boundaries

- `formats/base.py` defines the format adapter contract.
- `formats/mp3.py` owns ID3 interpretation/writes only; it never replaces originals itself.
- `service.py` owns the filesystem transaction, single-file reindex/SHA refresh, audit and orchestration.
- `artwork.py` owns disk-backed local/Yandex artwork caches.
- `yandex.py` performs authenticated search/full Track lookup in the backend and exposes sanitized metadata only.
- `matching_refresh.py` scopes rematching to identities plausibly affected by the edited local file, then advances the Local Library fingerprint only for unrelated rows that were already fresh.
- `identity.py` is the only v0.8.2 path that creates a user-confirmed exact provider/local relation.
- `bridge.py` is a JSON process boundary for Flutter. Binary artwork and credentials do not cross it.

## Read-only invariant

Local Scan, Matching, Coverage and Sync do not call metadata write APIs. Existing user files are mutated only by `local_metadata_update` or `local_metadata_apply_yandex` after an explicit UI action carrying `confirm=true`.

## Identity recovery

`Apply + Bind` writes MusicArk/Yandex provenance TXXX frames. Local Metadata Reader v0.8.1 already recognizes the trusted complete provenance set. Re-scanning a moved file can therefore recover provider/local identity independently of its filename and file hash.
