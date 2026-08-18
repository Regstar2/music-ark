import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/coverage_bridge.dart';
import 'package:musicark_ui/desktop_file_actions.dart';
import 'package:musicark_ui/download_bridge.dart';
import 'package:musicark_ui/download_page.dart';
import 'package:musicark_ui/folder_picker.dart';
import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/musicark_bridge.dart';

class FakeFileActions implements LocalFileActions {
  final List<String> played = [];
  final List<String> revealed = [];

  @override
  Future<void> play(String path) async => played.add(path);

  @override
  Future<void> reveal(String path) async => revealed.add(path);
}

class BlockingDownloadBridge extends FakeDownloadBridge {
  final Completer<void> firstStarted = Completer<void>();
  final Completer<void> releaseFirst = Completer<void>();
  bool _blocked = false;

  @override
  Future<Map<String, dynamic>> runTask(String taskId) async {
    if (!_blocked) {
      _blocked = true;
      firstStarted.complete();
      await releaseFirst.future;
    }
    return super.runTask(taskId);
  }
}

void main() {
  Finder downloadsScrollable() => find.descendant(
        of: find.byKey(const Key('downloads-page')),
        matching: find.byType(Scrollable),
      );

  Future<void> reveal(
    WidgetTester tester,
    Key key, {
    double delta = 350,
  }) async {
    await tester.scrollUntilVisible(
      find.byKey(key),
      delta,
      scrollable: downloadsScrollable(),
    );
    await tester.pump();
  }

  Future<void> pumpDownloads(
    WidgetTester tester,
    FakeDownloadBridge bridge, {
    CoverageBridgeClient? coverageBridge,
    LocalFolderPicker? picker,
    LocalFileActions? fileActions,
    bool active = true,
    bool settle = true,
    Locale locale = const Locale('ru'),
  }) async {
    await tester.binding.setSurfaceSize(const Size(1500, 1300));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        locale: locale,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: DownloadPage(
          bridge: bridge,
          coverageBridge: coverageBridge,
          active: active,
          folderPicker: picker ?? FakeLocalFolderPicker(r'C:\Music'),
          fileActions: fileActions ?? FakeFileActions(),
        ),
      ),
    );
    if (settle) {
      await tester.pumpAndSettle();
    } else {
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
    }
  }

  testWidgets('Downloads workspace shows summary, filters and real progress', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    expect(
      find.text('Управление очередью загрузок и треками, которым нужна локальная копия'),
      findsOneWidget,
    );
    expect(find.text('В очереди'), findsWidgets);
    expect(find.text('Загружается'), findsWidgets);
    expect(find.text('Ошибки'), findsWidgets);
    expect(find.byKey(const Key('downloads-search')), findsOneWidget);
    expect(find.byKey(const Key('downloads-filter-all')), findsOneWidget);
    expect(find.byKey(const Key('downloads-filter-failed')), findsOneWidget);

    await reveal(tester, const Key('download-progress-running-1'));
    expect(find.textContaining('Running Song'), findsOneWidget);
    expect(find.textContaining('82%'), findsOneWidget);
  });

  testWidgets('unknown total renders indeterminate progress', (tester) async {
    final bridge = FakeDownloadBridge();
    bridge.items[1]['totalBytes'] = null;
    bridge.items[1]['progress'] = null;
    bridge.items[1]['downloadedBytes'] = 4096;
    await pumpDownloads(tester, bridge, settle: false);
    await reveal(tester, const Key('download-progress-running-1'));

    final indicator = tester.widget<LinearProgressIndicator>(
      find.byKey(const Key('download-progress-running-1')),
    );
    expect(indicator.value, isNull);
    expect(find.textContaining('4.0 KB'), findsOneWidget);
  });

  testWidgets('search filters the loaded task list', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    await tester.enterText(find.byKey(const Key('downloads-search')), 'Failed Song');
    await tester.pump();

    expect(find.textContaining('Failed Song'), findsOneWidget);
    expect(find.textContaining('Queued Song'), findsNothing);
    expect(find.textContaining('Running Song'), findsNothing);
  });

  testWidgets('failed task shows friendly error and raw technical details separately', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);
    await reveal(tester, const Key('download-details-failed-1'));

    expect(
      find.textContaining('Яндекс Музыка не смогла предоставить этот трек'),
      findsOneWidget,
    );
    expect(find.textContaining('Network error while downloading track.'), findsNothing);

    await tester.tap(find.byKey(const Key('download-details-failed-1')));
    await tester.pumpAndSettle();

    expect(find.text('Технические сведения'), findsOneWidget);
    expect(find.textContaining('errorCode: network_error'), findsOneWidget);
    expect(find.textContaining('Network error while downloading track.'), findsOneWidget);
  });

  testWidgets('failed task removal requires confirmation and removes only the task record', (tester) async {
    final bridge = FakeDownloadBridge();
    final fileActions = FakeFileActions();
    await pumpDownloads(tester, bridge, fileActions: fileActions);
    await reveal(tester, const Key('download-remove-failed-1'));

    await tester.tap(find.byKey(const Key('download-remove-failed-1')));
    await tester.pumpAndSettle();
    expect(find.text('Удалить задачу загрузки?'), findsOneWidget);
    expect(
      find.textContaining('Музыкальные файлы и локальная библиотека не будут изменены'),
      findsOneWidget,
    );

    await tester.tap(find.text('Отмена'));
    await tester.pumpAndSettle();
    expect(bridge.items.any((item) => item['id'] == 'failed-1'), isTrue);

    await tester.tap(find.byKey(const Key('download-remove-failed-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('download-remove-confirm-failed-1')));
    await tester.pumpAndSettle();

    expect(bridge.removeBatches, [
      ['failed-1'],
    ]);
    expect(bridge.items.any((item) => item['id'] == 'failed-1'), isFalse);
    expect(fileActions.played, isEmpty);
    expect(fileActions.revealed, isEmpty);
  });

  testWidgets('single retry runs only selected task and leaves old queue untouched', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);
    await reveal(tester, const Key('download-retry-failed-1'));

    await tester.tap(find.byKey(const Key('download-retry-failed-1')));
    await tester.pumpAndSettle();

    expect(bridge.runCalled, isFalse);
    expect(bridge.runTaskIds, ['failed-1']);
    expect(
      bridge.items.firstWhere((item) => item['id'] == 'queued-1')['status'],
      'queued',
    );
  });

  testWidgets('bulk retry runs only selected failed tasks', (tester) async {
    final bridge = FakeDownloadBridge();
    bridge.items.add({
      'id': 'failed-2',
      'provider': 'yandex_music',
      'externalId': '104',
      'title': 'Second Failed Song',
      'artists': ['Artist'],
      'status': 'failed',
      'progress': null,
      'downloadedBytes': 0,
      'totalBytes': null,
      'targetPath': r'C:\Music\Second Failed.mp3',
      'errorCode': 'provider_request',
      'error': 'Provider failed.',
      'canRetry': true,
      'canCancel': false,
    });
    await pumpDownloads(tester, bridge);

    await reveal(tester, const Key('download-select-failed-1'));
    await tester.tap(find.byKey(const Key('download-select-failed-1')));
    await reveal(tester, const Key('download-select-failed-2'));
    await tester.tap(find.byKey(const Key('download-select-failed-2')));
    await tester.pump();
    await reveal(tester, const Key('downloads-bulk-retry'), delta: -350);
    await tester.tap(find.byKey(const Key('downloads-bulk-retry')));
    await tester.pumpAndSettle();

    expect(bridge.retryBatches, [
      ['failed-1', 'failed-2'],
    ]);
    expect(bridge.runBatches, [
      ['failed-1', 'failed-2'],
    ]);
    expect(bridge.runCalled, isFalse);
    expect(
      bridge.items.firstWhere((item) => item['id'] == 'queued-1')['status'],
      'queued',
    );
  });

  testWidgets('bulk cancel confirms and affects only selected active tasks', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    await reveal(tester, const Key('download-select-queued-1'));
    await tester.tap(find.byKey(const Key('download-select-queued-1')));
    await tester.pump();
    await reveal(tester, const Key('downloads-bulk-cancel'), delta: -350);
    await tester.tap(find.byKey(const Key('downloads-bulk-cancel')));
    await tester.pumpAndSettle();
    expect(find.text('Отменить выбранные загрузки?'), findsOneWidget);

    await tester.tap(find.byKey(const Key('downloads-bulk-cancel-confirm')));
    await tester.pumpAndSettle();

    expect(bridge.cancelBatches, [
      ['queued-1'],
    ]);
    expect(
      bridge.items.firstWhere((item) => item['id'] == 'running-1')['status'],
      'running',
    );
  });

  testWidgets('bulk remove deletes only selected failed tasks', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    await reveal(tester, const Key('download-select-failed-1'));
    await tester.tap(find.byKey(const Key('download-select-failed-1')));
    await tester.pump();
    await reveal(tester, const Key('downloads-bulk-remove'), delta: -350);
    await tester.tap(find.byKey(const Key('downloads-bulk-remove')));
    await tester.pumpAndSettle();
    expect(find.textContaining('Удалить 1 ошибочных задач?'), findsOneWidget);

    await tester.tap(find.byKey(const Key('downloads-bulk-remove-confirm')));
    await tester.pumpAndSettle();

    expect(bridge.removeBatches, [
      ['failed-1'],
    ]);
    expect(bridge.items.any((item) => item['id'] == 'failed-1'), isFalse);
    expect(bridge.items.any((item) => item['id'] == 'queued-1'), isTrue);
  });

  testWidgets('select all selects current visible search results only', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    await tester.enterText(find.byKey(const Key('downloads-search')), 'Failed Song');
    await tester.pump();
    await tester.tap(find.byKey(const Key('downloads-select-all')));
    await tester.pump();

    expect(find.byKey(const Key('downloads-bulk-retry')), findsOneWidget);
    expect(find.byKey(const Key('downloads-bulk-cancel')), findsNothing);
  });

  testWidgets('Wanted downloads selected tasks without waking unrelated queue', (tester) async {
    final bridge = FakeDownloadBridge();
    final coverage = FakeCoverageBridge();
    coverage.items.first['userAction'] = 'wanted';
    await pumpDownloads(tester, bridge, coverageBridge: coverage);

    await tester.tap(find.textContaining('Нужные').last);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('downloads-wanted-select-203')), findsOneWidget);

    await tester.tap(find.byKey(const Key('downloads-wanted-select-203')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('downloads-wanted-download-selected')));
    await tester.pumpAndSettle();

    expect(bridge.enqueueSelectedBatches, [
      ['203'],
    ]);
    expect(bridge.runBatches, [
      ['selected-203'],
    ]);
    expect(
      bridge.items.firstWhere((item) => item['id'] == 'queued-1')['status'],
      'queued',
    );
  });

  testWidgets('selection clears when switching Downloads and Wanted tabs', (tester) async {
    final bridge = FakeDownloadBridge();
    final coverage = FakeCoverageBridge();
    coverage.items.first['userAction'] = 'wanted';
    await pumpDownloads(tester, bridge, coverageBridge: coverage);

    await reveal(tester, const Key('download-select-failed-1'));
    await tester.tap(find.byKey(const Key('download-select-failed-1')));
    await tester.pump();
    await reveal(tester, const Key('downloads-bulk-bar'), delta: -350);
    expect(find.byKey(const Key('downloads-bulk-bar')), findsOneWidget);

    await tester.tap(find.textContaining('Нужные').last);
    await tester.pumpAndSettle();
    await tester.tap(find.textContaining('Загрузки').last);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('downloads-bulk-bar')), findsNothing);
  });

  testWidgets('target selection persists exact folder picked by user', (tester) async {
    final bridge = FakeDownloadBridge(configured: false);
    await pumpDownloads(
      tester,
      bridge,
      picker: FakeLocalFolderPicker(r'D:\Music'),
    );

    expect(find.text('Выберите папку для загрузок'), findsOneWidget);
    await tester.tap(find.byKey(const Key('downloads-select-target')));
    await tester.pumpAndSettle();
    expect(bridge.selectedPath, r'D:\Music');
    expect(find.text(r'D:\Music'), findsOneWidget);
  });

  testWidgets('explicit cancel queue cancels waiting tasks without deleting files', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    await tester.tap(find.byKey(const Key('downloads-cancel-queued')));
    await tester.pumpAndSettle();
    expect(find.text('Отменить очередь?'), findsOneWidget);

    await tester.tap(find.byKey(const Key('downloads-cancel-queued-confirm')));
    await tester.pumpAndSettle();

    expect(bridge.cancelBatches, [
      ['queued-1'],
    ]);
    expect(
      bridge.items.firstWhere((item) => item['id'] == 'queued-1')['status'],
      'cancelled',
    );
  });

  testWidgets('leaving Downloads stops explicit queue after current task', (tester) async {
    final bridge = BlockingDownloadBridge();
    bridge.items.add({
      'id': 'queued-2',
      'provider': 'yandex_music',
      'externalId': '104',
      'title': 'Second Queued Song',
      'artists': ['Artist'],
      'status': 'queued',
      'progress': null,
      'downloadedBytes': 0,
      'totalBytes': null,
      'targetPath': r'C:\Music\Second.mp3',
      'error': null,
      'canRetry': false,
      'canCancel': true,
    });

    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MusicArkDesktopApp(
        bridge: FakeMusicArkBridge(startSignedIn: true),
        downloadBridge: bridge,
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('nav-downloads')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('downloads-run')));
    await tester.pump();
    await bridge.firstStarted.future;

    await tester.tap(find.text('Яндекс Музыка').first);
    await tester.pump();
    bridge.releaseFirst.complete();
    await tester.pumpAndSettle();

    expect(bridge.runTaskIds, ['queued-1']);
    expect(
      bridge.items.firstWhere((item) => item['id'] == 'queued-2')['status'],
      'queued',
    );
  });

  testWidgets('completed row shows local completion time and keeps file actions', (tester) async {
    final bridge = FakeDownloadBridge();
    const path = r'C:\Music\Finished [yandex_777].mp3';
    const finishedAt = '2026-08-18T07:42:00+00:00';
    bridge.items.add({
      'id': 'completed-777',
      'provider': 'yandex_music',
      'externalId': '777',
      'title': 'Finished',
      'artists': ['Artist'],
      'status': 'completed',
      'progress': 1.0,
      'downloadedBytes': 100,
      'totalBytes': 100,
      'targetPath': path,
      'finishedAt': finishedAt,
      'error': null,
      'canRetry': false,
      'canCancel': false,
    });
    final actions = FakeFileActions();
    await pumpDownloads(tester, bridge, fileActions: actions);
    await tester.tap(find.byKey(const Key('downloads-filter-completed')));
    await tester.pumpAndSettle();
    await reveal(tester, const Key('download-play-completed-777'));

    final timestampFinder = find.byKey(const Key('download-finished-at-completed-777'));
    expect(timestampFinder, findsOneWidget);
    final timestampContext = tester.element(timestampFinder);
    final material = MaterialLocalizations.of(timestampContext);
    final localFinishedAt = DateTime.parse(finishedAt).toLocal();
    final expectedTimestamp =
        '${material.formatCompactDate(localFinishedAt)} · ${material.formatTimeOfDay(TimeOfDay.fromDateTime(localFinishedAt))}';
    expect(find.text(expectedTimestamp), findsOneWidget);

    expect(find.text(path), findsNothing);
    await tester.tap(find.byKey(const Key('download-toggle-path-completed-777')));
    await tester.pump();
    expect(find.text(path), findsOneWidget);

    await tester.tap(find.byKey(const Key('download-play-completed-777')));
    await tester.tap(find.byKey(const Key('download-reveal-completed-777')));
    await tester.pump();
    expect(actions.played, [path]);
    expect(actions.revealed, [path]);
  });

  testWidgets('Downloads labels localize to English', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge, locale: const Locale('en'));

    expect(
      find.text('Manage the download queue and tracks that still need a local copy'),
      findsOneWidget,
    );
    expect(find.text('Queued'), findsWidgets);
    expect(find.text('Errors'), findsWidgets);
  });

  testWidgets('top-level navigation opens Downloads', (tester) async {
    final downloadBridge = FakeDownloadBridge();
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MusicArkDesktopApp(
        bridge: FakeMusicArkBridge(startSignedIn: true),
        downloadBridge: downloadBridge,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('nav-downloads')), findsOneWidget);
    await tester.tap(find.byKey(const Key('nav-downloads')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('downloads-page')), findsOneWidget);
  });
}
