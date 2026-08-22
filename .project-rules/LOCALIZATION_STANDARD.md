# MusicArk localization standard

User-facing MusicArk desktop UI is released with Russian and English support.

Release requirements:

- RU and EN expose the same implemented capabilities and warnings;
- new user-facing strings use the existing localization mechanism rather than inline one-language literals;
- security/confirmation/update/feedback text is reviewed in both languages;
- README.md and README_EN.md remain factually synchronized;
- narrow/normal layouts are smoke-tested in both languages where text length can change layout behavior;
- missing translations are release blockers when they affect the primary Windows workflow.

Translations must preserve technical meaning rather than mechanically mirror sentence structure.