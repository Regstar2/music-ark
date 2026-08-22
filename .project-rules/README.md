# MusicArk project rules

MusicArk uses the universal project-process rules introduced in `universal_project_rules_template_v11` together with the existing MusicArk-specific `AGENTS.md` architecture and safety rules.

These rules are additive. When a universal rule and a MusicArk-specific rule overlap, use the stricter constraint. Product/provider/domain invariants in `AGENTS.md` remain authoritative for MusicArk behavior.

Applied rule set:

- `DEVELOPMENT_WORKFLOW.md` — Issue → Project → branch → Draft PR → CI → merge → release flow.
- `ENGINEERING_PRINCIPLES.md` — bounded changes, evidence, safety and feature-freeze discipline.
- `AI_TEXT_GUARDRAILS.md` — factual documentation/release claims only.
- `GITHUB_AUTOMATION_STANDARD.md` — owner-gated self-hosted CI, Issues → Project #2, release automation.
- `RELEASE_STANDARD.md` — release-freeze, evidence and artifact rules for v1.0.0.
- `RELEASE_REVIEW_CHECKLIST.md` — final publication review.
- `AUTO_UPDATE_STANDARD.md` — Check → Prepare → Apply updater trust boundary.
- `FEEDBACK_STANDARD.md` — privacy-safe GitHub Issues feedback.
- `NETWORK_PROXY_STANDARD.md` — explicit proxy/WARP/network policy.
- `LOCALIZATION_STANDARD.md` — RU/EN release gate.
- `README_STANDARD.md` and `README_REVIEW_CHECKLIST.md` — public documentation requirements.
- `PROJECT_NAMING.md` — repository/product naming boundary.

Current owner defaults:

```text
Trusted GitHub login: Regstar2
Development Project: https://github.com/users/Regstar2/projects/2
Project secret: ADD_TO_PROJECT_PAT
Self-hosted labels: self-hosted, Windows, X64
```

Secrets, PAT values, Yandex credentials, proxy credentials and private library data must never be committed to this directory or any repository file.

The reusable generic templates remain maintained in the owner's canonical universal-rules repository. MusicArk stores the applied rules plus project-specific workflows/scripts rather than fail-closed initialization stubs.