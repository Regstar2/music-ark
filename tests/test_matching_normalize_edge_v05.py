"""Normalization edge cases that should not lose legitimate artist names."""

from __future__ import annotations

import unittest

from musicark.matching.normalize import normalize_artists


class MatchingNormalizeEdgeV05Tests(unittest.TestCase):
    def test_single_letter_x_artist_is_not_treated_as_separator(self) -> None:
        self.assertEqual(normalize_artists(("X",)), ("x",))

    def test_spaced_x_still_separates_collaboration_spelling(self) -> None:
        self.assertEqual(normalize_artists(("Artist A x Artist B",)), ("artist a", "artist b"))

    def test_feat_and_ft_spelling_still_split(self) -> None:
        self.assertEqual(normalize_artists(("Artist A feat. Artist B",)), ("artist a", "artist b"))
        self.assertEqual(normalize_artists(("Artist A ft. Artist B",)), ("artist a", "artist b"))


if __name__ == "__main__":
    unittest.main()
