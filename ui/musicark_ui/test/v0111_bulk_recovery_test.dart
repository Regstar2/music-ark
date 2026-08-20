import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/scope_context_bar.dart';
import 'package:musicark_ui/yandex_batch_upload_bridge.dart';
import 'package:musicark_ui/yandex_batch_upload_dialog.dart';
import 'package:musicark_ui/yandex_upload_bridge.dart';

void main() {
  Future<void> pumpShell(
    WidgetTester tester,
    Widget child, {
    Locale locale = const Locale('ru'),
    Size size = const Size(900, 760),
  }) async {
    await tester.binding.setSurfaceSize(size);
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        locale: locale,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(body: child),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets(
    'scope context keeps collection and long local folder visible on narrow layout',
    (tester) async {
      const path =
          r'D:\Music\A very very very long library root that must not break a narrow layout';
      await pumpShell(
        tester,
        const Padding(
          padding: EdgeInsets.all(8),
          child: ScopeContextBar(
            collection: 'Revolution',
            localFolders: path,
            localFoldersTooltip: path,
          ),
        ),
        size: const Size(420, 260),
      );

      expect(find.byKey(const Key('scope-context-bar')), findsOneWidget);
      expect(find.text('Коллекция'), findsOneWidget);
      expect(find.text('Revolution'), findsOneWidget);
      expect(find.text('Локальная папка'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'bulk dialog defaults to managed uploaded role and requires rights',
    (tester) async {
      final targetBridge = FakeYandexUploadBridge(
        playlists: const [
          YandexUploadTarget(
            playlistKind: '7',
            title: 'ЗАГРУЖЕННЫЕ ТРЕКИ',
            trackCount: 2,
          ),
          YandexUploadTarget(playlistKind: '8', title: 'Other', trackCount: 0),
        ],
      );
      final batchBridge = FakeYandexBatchUploadBridge();
      final tracks = <Map<String, dynamic>>[
        {'id': 11, 'fileName': 'a.mp3', 'extension': '.mp3', 'fileSize': 1024},
        {
          'id': 12,
          'fileName': 'b.flac',
          'extension': '.flac',
          'fileSize': 2048,
        },
      ];

      await pumpShell(
        tester,
        Builder(
          builder: (context) => Center(
            child: FilledButton(
              key: const Key('open-batch'),
              onPressed: () => showYandexBatchUploadDialog(
                context: context,
                tracks: tracks,
                targetBridge: targetBridge,
                batchBridge: batchBridge,
                localContext: r'D:\Music',
              ),
              child: const Text('open'),
            ),
          ),
        ),
      );
      await tester.tap(find.byKey(const Key('open-batch')));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('yandex-batch-upload-dialog')),
        findsOneWidget,
      );
      expect(find.text('Загрузить 2 треков в Яндекс Музыку'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('yandex-batch-submit')))
            .onPressed,
        isNull,
      );

      final field = tester.widget<DropdownButtonFormField<String>>(
        find.byKey(const Key('yandex-batch-playlist')),
      );
      expect(field.initialValue, '7');

      await tester.tap(find.byKey(const Key('yandex-batch-rights')));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('yandex-batch-submit')))
            .onPressed,
        isNotNull,
      );

      await tester.tap(find.byKey(const Key('yandex-batch-submit')));
      await tester.pumpAndSettle();
      expect(batchBridge.uploadedBatches, [
        [11, 12],
      ]);
      expect(batchBridge.uploadedTargets, ['7']);
      expect(find.byKey(const Key('yandex-batch-result')), findsOneWidget);
    },
  );

  testWidgets(
    'delivery unknown is manual-check only and never offered as blind retry',
    (tester) async {
      final targetBridge = FakeYandexUploadBridge(
        playlists: const [
          YandexUploadTarget(
            playlistKind: '7',
            title: 'ЗАГРУЖЕННЫЕ ТРЕКИ',
            trackCount: 0,
          ),
        ],
      );
      final batchBridge = FakeYandexBatchUploadBridge(
        resultFactory: (ids, playlistKind) => {
          'batchId': 'test',
          'status': 'finished',
          'total': ids.length,
          'completed': ids.length,
          'counts': {
            'total': ids.length,
            'verified': 0,
            'processing': 0,
            'deliveryUnknown': 1,
            'failed': 0,
            'unsupported': 0,
            'ambiguous': 0,
            'skipped': 0,
            'cancelled': 0,
          },
          'items': [
            {
              'localFileId': ids.first,
              'status': 'delivery_unknown',
              'result': {'state': 'delivery_unknown'},
            },
          ],
          'retryableLocalFileIds': <int>[],
          'manualCheckLocalFileIds': [ids.first],
          'concurrency': 1,
        },
      );

      await pumpShell(
        tester,
        Builder(
          builder: (context) => Center(
            child: FilledButton(
              key: const Key('open-batch'),
              onPressed: () => showYandexBatchUploadDialog(
                context: context,
                tracks: const [
                  {
                    'id': 21,
                    'fileName': 'a.mp3',
                    'extension': '.mp3',
                    'fileSize': 1,
                  },
                ],
                targetBridge: targetBridge,
                batchBridge: batchBridge,
                localContext: 'Все папки',
              ),
              child: const Text('open'),
            ),
          ),
        ),
      );
      await tester.tap(find.byKey(const Key('open-batch')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('yandex-batch-rights')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('yandex-batch-submit')));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('yandex-batch-manual-check')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('yandex-batch-retry-failures')),
        findsNothing,
      );
      expect(find.textContaining('Проверить плейлист'), findsOneWidget);
    },
  );
}
