# Технологический стек

## v0.6.0

- Flutter / Dart `^3.11.5` — Windows desktop UI;
- Python `>=3.10` — provider/local/matching/variant/coverage application runtime;
- SQLite — cache, Local Library index, identity, variants and coverage triage;
- `yandex-music==3.0.0`, `keyring==25.7.0`, `mutagen>=1.47.0`, `requests>=2.32.0`;
- ffmpeg — optional capability только для v0.5.1 decoded-audio variant verification.

Coverage не добавляет внешних analytics/matching библиотек. Summary/list/filter/search/sort/pagination выполняются SQL `JOIN/LEFT JOIN/EXISTS`, CTE и indexes. Derived coverage не materialize-ится в Python/Flutter целиком.

Persistence boundaries: `matching_results/track_links` — identity truth; `track_variant_results` — secondary recording truth; `provider_track_actions` — только user triage. Reference cache не является Local Library.

v0.6 не добавляет download product flow, source selection, torrent/YouTube acquisition, destructive filesystem operations или Yandex mutation.
