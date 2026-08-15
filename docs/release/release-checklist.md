# Release Checklist — v0.6.0 Missing Tracks / Library Coverage

## Automated

- [ ] full Python unittest suite green;
- [ ] `flutter pub get`, `flutter analyze`, `flutter test` green;
- [ ] schema initializes idempotently at `1.6.0`;
- [ ] realistic `1.5.0 → 1.6.0` migration preserves cache/local/matching/manual/conflict/variant rows;
- [ ] central coverage truth table green;
- [ ] all five variant statuses remain secondary to Covered identity;
- [ ] strict reference-cache regression remains Missing without accepted local identity;
- [ ] global collection dedup/scopes/playlist order green;
- [ ] removed provider identities are absent from active coverage;
- [ ] wanted/ignored/reset persistence and matching-change behavior green;
- [ ] bridge structured bulk payload tests green;
- [ ] Flutter navigation/default Missing/filter/search/sort/pagination/triage/bulk/empty-state tests green.

## Semantic quality gate

- [ ] `CONFLICT != MISSING`;
- [ ] `NOT_ANALYZED != MISSING`;
- [ ] stale automatic state is not presented as proven Missing;
- [ ] stale manual accepted link becomes Needs Review;
- [ ] `DIFFERENT_VERSION/ALTERED/UNCERTAIN/NOT_CHECKED != MISSING` when identity is accepted;
- [ ] reference cache does not establish Covered.

## Performance / safety

- [ ] list/summary/filter/search/sort/pagination are SQL-backed and no N+1 loop was introduced;
- [ ] no `missing_tracks` copy table;
- [ ] only user triage is persisted;
- [ ] no missing-track download/source selection;
- [ ] no filesystem or Yandex mutation;
- [ ] no token, DB, personal music, or audio fixture in diff.

## Manual Windows

- [ ] real library summary reviewed against Matching;
- [ ] scopes Liked/playlist verified;
- [ ] bulk triage survives restart;
- [ ] rerun Matching moves newly matched row out of Missing;
- [ ] offline Coverage works;
- [ ] strict v0.5.1 reference file still does not count as Local Library coverage.
