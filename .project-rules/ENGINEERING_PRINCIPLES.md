# MusicArk engineering principles

These rules supplement `AGENTS.md`.

- Prefer the smallest change that fixes a confirmed requirement or release blocker.
- Preserve provider-neutral core boundaries; Yandex-specific behavior stays behind provider/application adapters.
- Planning and mutation remain separate. Dangerous operations require explicit confirmation.
- Existing local audio is never silently deleted, replaced or retagged.
- Provider/network/update failures fail closed and must not broaden permissions or mutation scope.
- Tests and build output are evidence; prose is not evidence.
- New dependencies require a concrete current need and release impact review.
- During v1.0 feature freeze, speculative refactors and new features are deferred.
- Secrets, account data, private library data and local machine paths are not committed or included in diagnostics.
- If behavior is not verified, say `NOT VERIFIED` instead of inferring success.