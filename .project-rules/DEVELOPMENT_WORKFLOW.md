# MusicArk development workflow

## Default flow

```text
Milestone / release goal
        ↓
Issues
        ↓
GitHub Project #2
        ↓
Backlog → Todo → In Progress → Done
        ↓
branch
        ↓
Draft PR
        ↓
Trusted CI
        ↓
owner review / manual acceptance when required
        ↓
merge
        ↓
release gate
```

## Rules

1. Meaningful work starts as a GitHub Issue with scope and acceptance criteria.
2. New Issues are collected in the shared Development Project and start in `Backlog`.
3. `Todo` means intentionally planned work; `In Progress` means implementation has started.
4. One branch should implement one bounded task or a tightly related set of Issues.
5. Open a Draft PR early enough for CI to validate the real branch.
6. PR bodies reference Issues; use `Closes #N` only when the PR actually completes the Issue.
7. Never claim PASS for a test that was not executed. Use `NOT VERIFIED` when evidence is unavailable.
8. External/fork PR code must not execute on the persistent self-hosted runner.
9. During v1.0.0 release freeze, only release blockers, regression fixes, documentation corrections and distribution hardening are allowed. New product features go to post-v1.0 backlog.
10. Merge is an owner decision. No workflow or agent auto-merges MusicArk release work.

## Definition of Done

A task is done only when applicable code, tests, documentation and verification evidence are complete. Any skipped test or manual check must include a concrete reason and residual risk.