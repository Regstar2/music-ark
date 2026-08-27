from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected patch anchor not found in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# #56: recognize MusicArk's actual [yandex_ID] filename suffix as strict identity.
replace_once(
    "src/musicark/matching/scoring.py",
    '''    name = _path_basename(path)\n    pattern = re.compile(rf"^yandex[_-]{re.escape(external_id)}(?:\\.[^.]+)?$", re.IGNORECASE)\n    return bool(pattern.fullmatch(name))\n''',
    '''    name = _path_basename(path)\n    escaped = re.escape(external_id)\n    pattern = re.compile(\n        rf"^(?:yandex[_-]{escaped}|.+\\s*\\[yandex[_-]{escaped}\\])(?:\\.[^.]+)?$",\n        re.IGNORECASE,\n    )\n    return bool(pattern.fullmatch(name))\n''',
)

# #56: exact provider identity outranks metadata confidence; duplicate exact claims remain conflict.
replace_once(
    "src/musicark/matching/service.py",
    '''            scored = sorted(\n                (self._scorer.score(provider, local) for local in local_candidates),\n                key=lambda item: item.confidence,\n                reverse=True,\n            )\n''',
    '''            scored = sorted(\n                (self._scorer.score(provider, local) for local in local_candidates),\n                key=lambda item: (self._is_exact_identity(item), item.confidence),\n                reverse=True,\n            )\n''',
)
service = Path("src/musicark/matching/service.py")
text = service.read_text(encoding="utf-8")
anchor = '''    @staticmethod\n    def _decide(\n'''
helper = '''    @staticmethod\n    def _is_exact_identity(candidate: ScoredCandidate) -> bool:\n        return (\n            candidate.method is MatchMethod.EXACT_ID\n            and float(candidate.breakdown.get("exact_id") or 0.0) >= 1.0\n        )\n\n    @staticmethod\n    def _decide(\n'''
if anchor not in text:
    raise SystemExit("MatchingService _decide anchor not found")
text = text.replace(anchor, helper, 1)
old_decision = '''        best = candidates[0]\n        second = candidates[1] if len(candidates) > 1 else None\n        margin = best.confidence - second.confidence if second else 1.0\n        if best.confidence >= AUTO_MATCH_THRESHOLD and margin >= AMBIGUITY_MARGIN:\n            status = MatchStatus.MATCHED\n            reason = "auto_threshold_and_margin"\n        elif best.confidence >= CONFLICT_THRESHOLD:\n            status = MatchStatus.CONFLICT\n            reason = (\n                "ambiguous_top_candidates"\n                if second and margin < AMBIGUITY_MARGIN\n                else "manual_review_threshold"\n            )\n        else:\n            status = MatchStatus.UNMATCHED\n            reason = "below_conflict_threshold"\n'''
new_decision = '''        exact_candidates = [\n            candidate\n            for candidate in candidates\n            if MatchingService._is_exact_identity(candidate)\n        ]\n        best = exact_candidates[0] if exact_candidates else candidates[0]\n        if len(exact_candidates) == 1:\n            status = MatchStatus.MATCHED\n            reason = "exact_provider_identity"\n        elif len(exact_candidates) > 1:\n            status = MatchStatus.CONFLICT\n            reason = "ambiguous_exact_id_candidates"\n        else:\n            second = candidates[1] if len(candidates) > 1 else None\n            margin = best.confidence - second.confidence if second else 1.0\n            if best.confidence >= AUTO_MATCH_THRESHOLD and margin >= AMBIGUITY_MARGIN:\n                status = MatchStatus.MATCHED\n                reason = "auto_threshold_and_margin"\n            elif best.confidence >= CONFLICT_THRESHOLD:\n                status = MatchStatus.CONFLICT\n                reason = (\n                    "ambiguous_top_candidates"\n                    if second and margin < AMBIGUITY_MARGIN\n                    else "manual_review_threshold"\n                )\n            else:\n                status = MatchStatus.UNMATCHED\n                reason = "below_conflict_threshold"\n'''
if old_decision not in text:
    raise SystemExit("MatchingService decision block not found")
service.write_text(text.replace(old_decision, new_decision, 1), encoding="utf-8")

# RU/EN product copy for unavailable-track restore through an ordinary playlist.
loc = Path("ui/musicark_ui/lib/v0111_localizations_ext.dart")
text = loc.read_text(encoding="utf-8")
anchor = '''  String get v0111ReadyToRestore =>\n      _ru ? 'Готов к восстановлению' : 'Ready to restore';\n'''
addition = anchor + '''  String get v0111RestoreAction => _ru ? 'Восстановить' : 'Restore';\n  String get v0111RestoreUnavailableTitle => _ru\n      ? 'Восстановить недоступный трек'\n      : 'Restore unavailable track';\n  String get v0111RestoreUnavailableHint => _ru\n      ? 'Локальная копия будет загружена в Яндекс Музыку как пользовательский трек и добавлена в выбранный плейлист.'\n      : 'The local copy will be uploaded to Yandex Music as a user track and added to the selected playlist.';\n  String get v0111RestorePlaylistHint => _ru\n      ? 'Рекомендуется плейлист «ЗАГРУЖЕННЫЕ ТРЕКИ». Если его нет, создайте его в Яндекс Музыке, обновите библиотеку и выберите здесь. Можно выбрать любой другой свой плейлист.'\n      : 'The recommended target is “UPLOADED TRACKS”. If it does not exist, create it in Yandex Music, refresh the library, and select it here. You may also choose another playlist you own.';\n  String get v0111RestoreNoPlaylists => _ru\n      ? 'Нет доступных плейлистов. Создайте плейлист в Яндекс Музыке, обновите библиотеку MusicArk и повторите восстановление.'\n      : 'No playlists are available. Create a playlist in Yandex Music, refresh the MusicArk library, and retry restore.';\n'''
if anchor not in text:
    raise SystemExit("v0111 localization anchor not found")
loc.write_text(text.replace(anchor, addition, 1), encoding="utf-8")

# #54: restore unavailable local copies through a selected ordinary playlist.
page = Path("ui/musicark_ui/lib/sync_page.dart")
text = page.read_text(encoding="utf-8")
start = text.index("  Future<void> _restoreRecoveryTrack(")
end = text.index("  Widget _scopeContext()", start)
restore_method = r'''  Future<void> _restoreRecoveryTrack(Map<String, dynamic> item) async {
    final bridge = widget.managedPlaylistBridge;
    final localFileId = int.tryParse('${item['localFileId']}');
    final externalId = '${item['externalId'] ?? ''}';
    final state = '${item['recoveryState'] ?? ''}';
    final censoredRecovery = state.startsWith('censored_');
    final unavailableRecovery = state == 'unavailable_local_available';
    if (bridge == null ||
        localFileId == null ||
        (!censoredRecovery && !unavailableRecovery)) {
      return;
    }

    final available = _maps(_managed['availablePlaylists']);
    String? selectedPlaylistKind;
    if (censoredRecovery) {
      selectedPlaylistKind = _managedRoleKind('censored');
      if (selectedPlaylistKind == null) return;
    } else {
      final uploaded = _managedRoleKind('uploaded');
      if (uploaded != null &&
          available.any(
            (playlist) => '${playlist['playlistKind'] ?? ''}' == uploaded,
          )) {
        selectedPlaylistKind = uploaded;
      }
    }

    var rights = false;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) {
          final dialogL10n = dialogContext.l10n;
          return AlertDialog(
            key: Key('sync-recovery-restore-dialog-$externalId'),
            title: Text(
              unavailableRecovery
                  ? dialogL10n.v0111RestoreUnavailableTitle
                  : dialogL10n.v0111ReadyToRestore,
            ),
            content: SizedBox(
              width: 540,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (unavailableRecovery) ...[
                    Text(dialogL10n.v0111RestoreUnavailableHint),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      key: Key('sync-recovery-target-$externalId'),
                      initialValue: available.any(
                        (playlist) =>
                            '${playlist['playlistKind'] ?? ''}' ==
                            selectedPlaylistKind,
                      )
                          ? selectedPlaylistKind
                          : null,
                      isExpanded: true,
                      decoration: InputDecoration(
                        labelText: dialogL10n.v0111TargetPlaylist,
                        prefixIcon: const Icon(Icons.queue_music_outlined),
                        isDense: true,
                      ),
                      hint: Text(dialogL10n.v0111Select),
                      items: [
                        for (final playlist in available)
                          DropdownMenuItem(
                            value: '${playlist['playlistKind']}',
                            child: Text(
                              '${playlist['title'] ?? playlist['playlistKind']}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                      ],
                      onChanged: (value) => setDialogState(
                        () => selectedPlaylistKind = value,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      available.isEmpty
                          ? dialogL10n.v0111RestoreNoPlaylists
                          : dialogL10n.v0111RestorePlaylistHint,
                      style: Theme.of(dialogContext).textTheme.bodySmall,
                    ),
                    const SizedBox(height: 12),
                  ],
                  CheckboxListTile(
                    key: Key('sync-recovery-rights-$externalId'),
                    contentPadding: EdgeInsets.zero,
                    value: rights,
                    onChanged: (value) =>
                        setDialogState(() => rights = value == true),
                    title: Text(dialogL10n.v0111SyncRights),
                    controlAffinity: ListTileControlAffinity.leading,
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext, false),
                child: Text(dialogL10n.cancel),
              ),
              FilledButton(
                key: Key('sync-recovery-restore-confirm-$externalId'),
                onPressed: rights && selectedPlaylistKind != null
                    ? () => Navigator.pop(dialogContext, true)
                    : null,
                child: Text(dialogL10n.v0111RestoreAction),
              ),
            ],
          );
        },
      ),
    );
    if (confirmed != true || selectedPlaylistKind == null) return;
    await _run(() async {
      await bridge.uploadBatch(
        localFileIds: [localFileId],
        playlistKind: selectedPlaylistKind!,
        confirm: true,
        rightsConfirmed: true,
        batchId: 'recovery-${DateTime.now().microsecondsSinceEpoch}',
        allowStaleReupload: unavailableRecovery,
      );
      await _reloadRecoveryAndManaged();
    });
  }

'''
text = text[:start] + restore_method + text[end:]

start = text.index("  Widget _recoveryRow(Map<String, dynamic> item)")
end = text.index("  Widget _workspace(Map<String, dynamic> diff)", start)
recovery_row = r'''  Widget _recoveryRow(Map<String, dynamic> item) {
    final externalId = '${item['externalId'] ?? ''}';
    final artists = (item['artists'] as List? ?? const []).join(', ');
    final collections = _maps(item['collections'])
        .map((entry) => '${entry['title'] ?? entry['playlistKind'] ?? ''}')
        .where((value) => value.isNotEmpty)
        .join(', ');
    final localReady = item['localMp3Ready'] == true;
    final recoveryState = '${item['recoveryState'] ?? ''}';
    final needsReview = recoveryState.contains('needs_review');
    final censoredRecovery = recoveryState.startsWith('censored_');
    final unavailableRecovery = recoveryState == 'unavailable_local_available';
    final canRestore =
        widget.managedPlaylistBridge != null &&
        localReady &&
        !needsReview &&
        ((censoredRecovery && _managedRoleKind('censored') != null) ||
            unavailableRecovery);
    return Container(
      key: Key('sync-recovery-$externalId'),
      padding: const EdgeInsets.symmetric(vertical: 10),
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.cloud_off_outlined),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$artists${artists.isNotEmpty ? ' — ' : ''}${item['title'] ?? externalId}',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                if (collections.isNotEmpty)
                  Text('${context.l10n.v0111SourcePlaylists}: $collections'),
                Text(
                  item['providerAvailability'] == 'unavailable'
                      ? context.l10n.v0111YandexUnavailable
                      : context.l10n.v0111YandexUnknown,
                ),
                Text(
                  localReady
                      ? context.l10n.v0111LocalFound
                      : context.l10n.v0111LocalMissing,
                ),
              ],
            ),
          ),
          if (censoredRecovery || unavailableRecovery) ...[
            const SizedBox(width: 8),
            OutlinedButton.icon(
              key: Key('sync-recovery-restore-$externalId'),
              onPressed: canRestore ? () => _restoreRecoveryTrack(item) : null,
              icon: const Icon(Icons.cloud_upload_outlined),
              label: Text(
                localReady
                    ? context.l10n.v0111RestoreAction
                    : context.l10n.v0111NeedsLocalFile,
              ),
            ),
          ],
        ],
      ),
    );
  }

'''
text = text[:start] + recovery_row + text[end:]
page.write_text(text, encoding="utf-8")

# Widget acceptance: unavailable restore defaults to configured UPLOADED TRACKS
# and allows selecting another ordinary playlist.
test = Path("ui/musicark_ui/test/v0111_sync_page_test.dart")
text = test.read_text(encoding="utf-8")
start = text.index("  testWidgets(\n    'unavailable Recovery item remains visible but exposes no restore action'")
replacement = r'''  testWidgets(
    'unavailable Recovery restores local copy to configured uploaded playlist',
    (tester) async {
      final bridge = FakeSyncBridge();
      final managed = FakeYandexBatchUploadBridge(
        managedState: const {
          'canCreatePlaylists': false,
          'roles': [
            {
              'role': 'censored',
              'defaultTitle': 'ЦЕНЗУРА',
              'configured': false,
              'playlistKind': null,
              'title': null,
            },
            {
              'role': 'uploaded',
              'defaultTitle': 'ЗАГРУЖЕННЫЕ ТРЕКИ',
              'configured': true,
              'playlistKind': '7',
              'title': 'ЗАГРУЖЕННЫЕ ТРЕКИ',
            },
          ],
          'availablePlaylists': [
            {
              'playlistKind': '7',
              'title': 'ЗАГРУЖЕННЫЕ ТРЕКИ',
              'trackCount': 0,
            },
            {'playlistKind': '9', 'title': 'Архив', 'trackCount': 0},
          ],
        },
      );
      await pumpPage(tester, bridge, managed: managed);

      await tester.tap(find.textContaining('Восстановление ('));
      await tester.pumpAndSettle();
      final restore = find.byKey(
        const Key('sync-recovery-restore-unavailable-1'),
      );
      expect(restore, findsOneWidget);
      expect(find.textContaining('НЕДОСТУПНЫЕ'), findsNothing);

      await tester.tap(restore);
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('sync-recovery-restore-dialog-unavailable-1')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('sync-recovery-target-unavailable-1')),
        findsOneWidget,
      );
      final confirm = find.byKey(
        const Key('sync-recovery-restore-confirm-unavailable-1'),
      );
      expect(tester.widget<FilledButton>(confirm).onPressed, isNull);

      await tester.tap(
        find.byKey(const Key('sync-recovery-rights-unavailable-1')),
      );
      await tester.pumpAndSettle();
      expect(tester.widget<FilledButton>(confirm).onPressed, isNotNull);
      await tester.tap(confirm);
      await tester.pumpAndSettle();

      expect(managed.uploadedBatches, [
        [77],
      ]);
      expect(managed.uploadedTargets, ['7']);
    },
  );

  testWidgets(
    'unavailable Recovery can target another ordinary playlist',
    (tester) async {
      final bridge = FakeSyncBridge();
      final managed = FakeYandexBatchUploadBridge(
        managedState: const {
          'canCreatePlaylists': false,
          'roles': [
            {
              'role': 'censored',
              'defaultTitle': 'ЦЕНЗУРА',
              'configured': false,
              'playlistKind': null,
              'title': null,
            },
            {
              'role': 'uploaded',
              'defaultTitle': 'ЗАГРУЖЕННЫЕ ТРЕКИ',
              'configured': true,
              'playlistKind': '7',
              'title': 'ЗАГРУЖЕННЫЕ ТРЕКИ',
            },
          ],
          'availablePlaylists': [
            {
              'playlistKind': '7',
              'title': 'ЗАГРУЖЕННЫЕ ТРЕКИ',
              'trackCount': 0,
            },
            {'playlistKind': '9', 'title': 'Архив', 'trackCount': 0},
          ],
        },
      );
      await pumpPage(tester, bridge, managed: managed);
      await tester.tap(find.textContaining('Восстановление ('));
      await tester.pumpAndSettle();
      await tester.tap(
        find.byKey(const Key('sync-recovery-restore-unavailable-1')),
      );
      await tester.pumpAndSettle();

      await tester.tap(
        find.byKey(const Key('sync-recovery-target-unavailable-1')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Архив').last);
      await tester.pumpAndSettle();
      await tester.tap(
        find.byKey(const Key('sync-recovery-rights-unavailable-1')),
      );
      await tester.pumpAndSettle();
      await tester.tap(
        find.byKey(const Key('sync-recovery-restore-confirm-unavailable-1')),
      );
      await tester.pumpAndSettle();

      expect(managed.uploadedTargets, ['9']);
    },
  );
'''
test.write_text(text[:start] + replacement + "}\n", encoding="utf-8")

# Fix inherited #51 widget expectation: selected Wanted tasks use persistent runTask.
replace_once(
    "ui/musicark_ui/test/download_page_test.dart",
    '''    expect(bridge.runBatches, [\n      ['selected-203'],\n    ]);\n''',
    '''    expect(bridge.runTaskIds, ['selected-203']);\n    expect(bridge.runBatches, isEmpty);\n''',
)

# New regression tests for exact MusicArk/Yandex filename identity.
Path("tests/test_matching_exact_filename_v100.py").write_text(r'''from __future__ import annotations

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
''', encoding="utf-8")
