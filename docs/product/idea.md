# Идея проекта

MusicArk объединяет streaming-library и локальную коллекцию поэтапно: сначала надёжная identity, затем проверка версии записи, затем честная оценка coverage, и только после этого download/sync.

```text
Yandex cache + Local Library
        ↓
Identity Matching
        ↓
Variant Verification (secondary)
        ↓
Library Coverage
        ↓
Missing + wanted
        ↓
future Download
```

v0.6 отвечает «что доказанно отсутствует локально?» и сознательно не называет conflict/stale/not-analyzed состояниями missing. Пользователь может отметить технически missing трек как wanted/ignored, не меняя ни matching, ни Yandex.

Ключевой принцип продукта: система не должна создавать ложное ощущение полноты библиотеки. Поэтому рядом с Local coverage показывается доля Matching analyzed, а variant issues считаются отдельно.
