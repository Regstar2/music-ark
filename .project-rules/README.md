# MusicArk project rules

MusicArk uses the universal project-process rules introduced in `universal_project_rules_template_v11` together with the existing MusicArk-specific `AGENTS.md` architecture and safety rules.

These rules are additive. When a universal rule and a MusicArk-specific rule overlap, use the stricter constraint. Product/provider/domain invariants in `AGENTS.md` remain authoritative for MusicArk behavior.

Required process documents:

- `DEVELOPMENT_WORKFLOW.md` — Issue → Project → branch → Draft PR → CI → merge → release flow.
- `GITHUB_AUTOMATION_STANDARD.md` — owner-gated self-hosted CI, Issues → Project #2, release automation.
- `RELEASE_STANDARD.md` — release-freeze, evidence and artifact rules for v1.0.0.

Current owner defaults:

```text
Trusted GitHub login: Regstar2
Development Project: https://github.com/users/Regstar2/projects/2
Project secret: ADD_TO_PROJECT_PAT
Self-hosted labels: self-hosted, Windows, X64
```

Secrets, PAT values, Yandex credentials, proxy credentials and private library data must never be committed to this directory or any repository file.