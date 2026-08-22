# MusicArk release review checklist

Use together with `docs/release/release-checklist.md`.

- [ ] Release scope contains only accepted v1.0 blockers/fixes.
- [ ] Exact source commit/tag is recorded.
- [ ] Trusted CI passed on current source and again on the release tag.
- [ ] Manual Windows acceptance is recorded against final artifacts.
- [ ] `dist/` contains only intended publishable files.
- [ ] Installer/ZIP hashes match `SHA256SUMS.txt`.
- [ ] Update manifest matches the exact installer.
- [ ] README RU/EN, changelog and release notes match actual behavior.
- [ ] License/third-party requirements reviewed.
- [ ] Feedback/update URLs work after publication.
- [ ] Signing state is factual (`UNSIGNED` unless signature is actually verified).
- [ ] No secrets/private data are present in source, logs or artifacts.
- [ ] Existing release with the same tag is not silently overwritten.