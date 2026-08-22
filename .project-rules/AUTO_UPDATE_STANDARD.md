# MusicArk auto-update standard

The v0.15 updater is a release-critical security boundary.

Required contract:

```text
check   = read-only discovery
prepare = download + exact size/SHA-256 verification, no launch
apply   = explicit confirmation + re-verification + installer launch
```

Release requirements:

- strict MAJOR.MINOR.PATCH version parsing;
- approved HTTPS GitHub/GitHubusercontent update hosts;
- bounded redirects with target revalidation;
- plain `.exe` installer name;
- exact size and SHA-256 verification;
- failed or mismatched downloads are never promoted;
- update failure never blocks application startup or Settings;
- no Yandex/provider/proxy credential is sent to the update channel;
- stable manifest is generated from the exact final installer;
- automatic update checks are release behavior only where already implemented and must remain testable/disableable.

Any change to updater trust, download or launch behavior is a release blocker and requires automated regression coverage.