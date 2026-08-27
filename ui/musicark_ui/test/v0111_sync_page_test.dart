import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/sync_bridge.dart';
import 'package:musicark_ui/sync_page.dart';
import 'package:musicark_ui/yandex_batch_upload_bridge.dart';

class _UploadOnlySyncBridge extends FakeSyncBridge {
  _UploadOnlySyncBridge() : super(targetConfigured: false);

  @override
  Map<String, dynamic> samplePlan({String status = 'planned'}) {
    final plan = super.samplePlan(status: status);
    final summary = Map<String, dynamic>.from(plan['summary'] as Map);
    summary['readyToDownload'] = 0;
    summary['readyToUpload'] = 1;
    summary['operationCount'] = 1;
    summary['blockerCount'] = 0;
    summary['missingUndecided'] = 0;
    summary['identityReview'] = 0;
    summary['notAnalyzed'] = 0;
    summary['variantIssues'] = 0;
    summary['uploadBlocked'] = 0;
    summary['uploadByRole'] = {'censored': 1};
    plan['summary'] = summary;
    plan['targetRootId'] = null;
    plan['targetFolder'] = null;
    plan['operations'] = [
      {
        'id': 90,
        'type': 'upload_local_to_yandex',
        'externalId': 'censored-1',
        'reason': 'provider_censored_original_local_mp3',
        'status': 'pending',
        'dangerous': true,
        'metadata': {
          'title': 'Original Track',
          'artists': ['Artist'],
          'localFileId': 77,
          'targetRole': 'censored',
          'targetPlaylistKind': '8',
          'providerAvailability': 'available',
          'recoveryState': 'censored_original_available',
        },
        'result': {},
      },
    ];
    return plan;
  }
}

void main() {
  Future<void> pumpPage(
    WidgetTester tester,
    SyncBridgeClient bridge, {
    YandexBatchUploadBridgeClient? managed,
  }) async {
    await tester.binding.setSurfaceSize(const Size(1200, 1050));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        locale: const Locale('ru'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: SyncPage(bridge: bridge, managedPlaylistBridge: managed),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets(
    'censorship upload-only Sync does not require a download folder and requires rights',
    (tester) async {
      final bridge = _UploadOnlySyncBridge();
      final managed = FakeYandexBatchUploadBridge(
        managedState: const {
          'canCreatePlaylists': false,
          'roles': [
            {
              'role': 'censored',
              'defaultTitle': 'ЦЕНЗУРА',
              'configured': true,
              'playlistKind': '8',
              'title': 'ЦЕНЗУРА',
            },
            {
              'role': 'uploaded',
              'defaultTitle': 'ЗАГРУЖЕННЫЕ ТРЕКИ',
              'configured': false,
              'playlistKind': null,
              'title': null,
            },
          ],
          'availablePlaylists': [
            {'playlistKind': '8', 'title': 'ЦЕНЗУРА', 'trackCount': 0},
          ],
        },
      );

      await pumpPage(tester, bridge, managed: managed);

      expect(find.byKey(const Key('scope-context-bar')), findsOneWidget);
      expect(
        find.textContaining('не требуется для этого плана'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('sync-workspace-tabs')), findsOneWidget);

      final syncNow = find.byKey(const Key('sync-now'));
      await tester.ensureVisible(syncNow);
      await tester.pumpAndSettle();
      expect(tester.widget<FilledButton>(syncNow).onPressed, isNotNull);

      await tester.tap(syncNow);
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('sync-confirmation')), findsOneWidget);
      expect(
        find.text('Будет поставлено в загрузку с Яндекс Музыки: 0'),
        findsOneWidget,
      );
      expect(find.text('Будет загружено в Яндекс Музыку: 1'), findsOneWidget);
      expect(find.textContaining('НЕДОСТУПНЫЕ'), findsNothing);
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('sync-confirm')))
            .onPressed,
        isNull,
      );

      await tester.tap(find.byKey(const Key('sync-upload-rights')));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('sync-confirm')))
            .onPressed,
        isNotNull,
      );
      await tester.tap(find.byKey(const Key('sync-confirm')));
      await tester.pumpAndSettle();

      expect(bridge.applyCalls, 1);
      expect(bridge.lastRightsConfirmed, isTrue);
    },
  );

  testWidgets(
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
}
