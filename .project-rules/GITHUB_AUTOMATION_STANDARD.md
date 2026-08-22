# MusicArk GitHub automation standard

## Standard files

```text
.github/workflows/trusted-ci.yml
.github/workflows/project-sync.yml
.github/workflows/release.yml
scripts/ci.ps1
scripts/release.ps1
```

GitHub workflow files provide orchestration. Project-specific build/test/package logic belongs in `scripts/ci.ps1` and `scripts/release.ps1`.

## Trust boundary

The self-hosted Windows runner is a trusted owner machine, not a general public CI worker.

For PR code to reach it, all conditions must hold:

- `github.actor == 'Regstar2'`;
- `github.triggering_actor == 'Regstar2'`;
- PR author is `Regstar2`;
- PR head repository equals the base repository.

Trusted PR CI therefore uses `pull_request_target` only as a metadata gate, then checks out the exact approved same-repository PR SHA. External/fork PR code must never be checked out or executed on the self-hosted runner.

## Project Sync

Issues opened/reopened/transferred by `Regstar2` are added to:

`https://github.com/users/Regstar2/projects/2`

using repository secret `ADD_TO_PROJECT_PAT`. The PAT value must never appear in Git, logs, diagnostics or issue bodies.

## Release automation

Release jobs:

1. are owner-gated;
2. require an existing `vX.Y.Z` tag;
3. run CI again against the exact tagged source;
4. call `scripts/release.ps1 -Version <tag>`;
5. require non-empty `dist/`;
6. publish only files from `dist/`;
7. do not silently overwrite an existing GitHub Release.

## MusicArk-specific safety

CI and release automation must keep live Yandex mutation variables disabled unless a separate explicit manual/live test procedure is being executed. Project PAT is never passed to trusted CI or release jobs.