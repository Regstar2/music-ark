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
    summary['uploadByRole'] = {'censored': 0, 'unavailable': 1};
    plan['summary'] = summary;
    plan['targetRootId'] = null;
    plan['targetFolder'] = null;
    plan['operations'] = [
      {
        'id': 90,
        'type': 'upload_local_to_yandex',
        'externalId': 'unavailable-1',
        'reason': 'provider_unavailable_local_mp3',
        'status': 'pending',
        'dangerous': true,
        'metadata': {
          'title': 'Unavailable Track',
          'artists': ['Artist'],
          'localFileId': 77,
          'targetRole': 'unavailable',
          'targetPlaylistKind': '9',
          'providerAvailability': 'unavailable',
          'recoveryState': 'unavailable_local_available',
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

  tearDown(() => TestWidgetsFlutterBinding.ensureInitialized().setSurfaceSize(null));

  testWidgets('upload-only Sync does not require a download folder and requires rights', (
    tester,
  ) async {
    final bridge = _UploadOnlySyncBridge();
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
            'configured': false,
            'playlistKind': null,
            'title': null,
          },
          {
            'role': 'unavailable',
            'defaultTitle': 'НЕДОСТУПНЫЕ',
            'configured': true,
            'playlistKind': '9',
            'title': 'НЕДОСТУПНЫЕ',
          },
        ],
        'availablePlaylists': [
          {'playlistKind': '9', 'title': 'НЕДОСТУПНЫЕ', 'trackCount': 0},
        ],
      },
    );

    await pumpPage(tester, bridge, managed: managed);

    expect(find.byKey(const Key('scope-context-bar')), findsOneWidget);
    expect(find.textContaining('не требуется для этого плана'), findsOneWidget);
    expect(find.byKey(const Key('sync-recovery-section')), findsOneWidget);
    expect(find.byKey(const Key('sync-managed-playlists')), findsOneWidget);
    expect(find.byKey(const Key('sync-recovery-unavailable-1')), findsOneWidget);

    final syncNow = find.byKey(const Key('sync-now'));
    await tester.ensureVisible(syncNow);
    await tester.pumpAndSettle();
    expect(tester.widget<FilledButton>(syncNow).onPressed, isNotNull);

    await tester.tap(syncNow);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sync-confirmation')), findsOneWidget);
    expect(find.text('Будет поставлено в загрузку с Яндекс Музыки: 0'), findsOneWidget);
    expect(find.text('Будет загружено в Яндекс Музыку: 1'), findsOneWidget);
    expect(
      tester.widget<FilledButton>(find.byKey(const Key('sync-confirm'))).onPressed,
      isNull,
    );

    await tester.tap(find.byKey(const Key('sync-upload-rights')));
    await tester.pumpAndSettle();
    expect(
      tester.widget<FilledButton>(find.byKey(const Key('sync-confirm'))).onPressed,
      isNotNull,
    );
    await tester.tap(find.byKey(const Key('sync-confirm')));
    await tester.pumpAndSettle();

    expect(bridge.applyCalls, 1);
    expect(bridge.lastRightsConfirmed, isTrue);
  });

  testWidgets('recovery filters are present and recoverable item exposes restore action', (
    tester,
  ) async {
    final bridge = FakeSyncBridge();
    final managed = FakeYandexBatchUploadBridge(
      managedState: const {
        'canCreatePlaylists': false,
        'roles': [
          {
            'role': 'unavailable',
            'defaultTitle': 'НЕДОСТУПНЫЕ',
            'configured': true,
            'playlistKind': '9',
            'title': 'НЕДОСТУПНЫЕ',
          },
        ],
        'availablePlaylists': [
          {'playlistKind': '9', 'title': 'НЕДОСТУПНЫЕ', 'trackCount': 0},
        ],
      },
    );
    await pumpPage(tester, bridge, managed: managed);

    await tester.ensureVisible(find.byKey(const Key('sync-recovery-section')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sync-recovery-filter-all')), findsOneWidget);
    expect(find.byKey(const Key('sync-recovery-filter-recoverable')), findsOneWidget);
    expect(find.byKey(const Key('sync-recovery-filter-missing_local')), findsOneWidget);
    expect(find.byKey(const Key('sync-recovery-filter-needs_review')), findsOneWidget);
    expect(find.byKey(const Key('sync-recovery-restore-unavailable-1')), findsOneWidget);
  });
}
