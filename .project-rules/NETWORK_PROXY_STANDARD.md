# MusicArk network/proxy standard

MusicArk uses one explicit external-network policy for provider-independent metadata/update/download paths where technically applicable.

Required behavior:

- preserve explicit Direct / HTTP(S) / SOCKS5 / WARP / Auto behavior already implemented by MusicArk;
- never silently fall back from an explicitly configured custom proxy to Direct;
- proxy credentials are secrets and must not be logged, committed, included in diagnostics or issue bodies;
- TLS verification is not disabled to make a provider/update path work;
- WARP installation/control remains explicit and ownership-aware;
- MusicArk uninstall must not silently remove WARP or other external software;
- update traffic must not inherit provider credentials;
- network/provider failure must remain distinguishable from metadata/matching/upload semantics.

Release regression coverage for v0.12 network behavior is mandatory.