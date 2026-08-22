# MusicArk feedback standard

MusicArk exposes Bug report and Feature request actions through GitHub Issues.

Requirements:

- public release must use an Issues tracker reachable by intended users;
- bug/feature Issue Forms remain available and privacy-oriented;
- built-in diagnostics may include MusicArk version, OS and architecture only unless a field is explicitly reviewed safe;
- diagnostics must exclude Yandex tokens/cookies, signed URLs, account identifiers, proxy secrets, local music paths and library contents;
- browser-open failure provides a copied-link fallback;
- no client-side GitHub PAT is embedded in MusicArk;
- users are instructed to review diagnostics before submission.

While the repository is private, external feedback accessibility is `NOT VERIFIED` until the final public target is configured and tested.