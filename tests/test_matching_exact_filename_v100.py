from __future__ import annotations

import unittest

from musicark.matching.models import MatchMethod, MatchStatus
from musicark.matching.scoring import MatchScorer, _strict_yandex_id_match
from musicark.matching.service import MatchingService


class ExactMusicArkFilenameMatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = {
            "provider_id": "yandex_music",
            "external_id": "1201183911",
            "payload": {
                "title": "Stay with Me",
                "artists": ["shadowave"],
                "album_title": "Stay with Me",
                "duration_seconds": 110.028,
            },
        }
        self.scorer = MatchScorer()

    def local(self, local_id: int, path: str) -> dict:
        return {
            "id": local_id,
            "path": path,
            "title": "Stay with Me",
            "artists": ["shadowave"],
            "album": "Stay with Me",
            "duration_seconds": 110.028,
            "tag_title_present": True,
        }

    def decide(self, candidates):
        return MatchingService._decide(
            self.provider,
            provider_fingerprint="provider-fp",
            local_fingerprint="local-fp",
            candidates=list(candidates),
        )

    def test_musicark_bracketed_filename_is_strict_identity(self) -> None:
        path = r"C:\Music\shadowave - Stay with Me [yandex_1201183911].mp3"
        self.assertTrue(_strict_yandex_id_match("yandex_music", "1201183911", path))
        self.assertFalse(_strict_yandex_id_match("yandex_music", "981700711", path))
        self.assertTrue(
            _strict_yandex_id_match(
                "yandex_music", "1201183911", r"C:\Music\yandex_1201183911.mp3"
            )
        )

    def test_exact_filename_identity_outranks_100_percent_metadata_duplicate(self) -> None:
        exact = self.scorer.score(
            self.provider,
            self.local(
                1,
                r"C:\Music\shadowave - Stay with Me [yandex_1201183911].mp3",
            ),
        )
        metadata = self.scorer.score(
            self.provider,
            self.local(2, r"C:\Music\shadowave - Stay with Me duplicate.mp3"),
        )
        self.assertEqual(exact.method, MatchMethod.EXACT_ID)
        self.assertEqual(metadata.confidence, 1.0)
        decision = self.decide([metadata, exact])
        self.assertEqual(decision.status, MatchStatus.MATCHED)
        self.assertEqual(decision.local_file_id, 1)
        self.assertEqual(decision.reason, "exact_provider_identity")

    def test_two_metadata_only_100_percent_candidates_remain_conflict(self) -> None:
        first = self.scorer.score(
            self.provider,
            self.local(2, r"C:\Music\Stay with Me copy 1.mp3"),
        )
        second = self.scorer.score(
            self.provider,
            self.local(3, r"C:\Music\Stay with Me copy 2.mp3"),
        )
        self.assertEqual(first.confidence, 1.0)
        self.assertEqual(second.confidence, 1.0)
        decision = self.decide([first, second])
        self.assertEqual(decision.status, MatchStatus.CONFLICT)
        self.assertEqual(decision.reason, "ambiguous_top_candidates")

    def test_two_files_claiming_same_exact_id_remain_conflict(self) -> None:
        first = self.scorer.score(
            self.provider,
            self.local(4, r"C:\Music\A [yandex_1201183911].mp3"),
        )
        second = self.scorer.score(
            self.provider,
            self.local(5, r"C:\Music\B [yandex_1201183911].mp3"),
        )
        decision = self.decide([first, second])
        self.assertEqual(decision.status, MatchStatus.CONFLICT)
        self.assertEqual(decision.reason, "ambiguous_exact_id_candidates")


if __name__ == "__main__":
    unittest.main()
