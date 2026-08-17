import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/desktop_file_actions.dart';
import 'package:musicark_ui/download_bridge.dart';
import 'package:musicark_ui/download_page.dart';
import 'package:musicark_ui/folder_picker.dart';
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
    LocalFolderPicker? picker,
    LocalFileActions? fileActions,
    bool active = true,
    bool settle = true,
  }) async {
    await tester.binding.setSurfaceSize(const Size(1400, 1300));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: DownloadPage(
          bridge: bridge,
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

  testWidgets('Downloads page shows persisted queue states and real progress', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    expect(find.text('Загрузки'), findsNWidgets(2));
    expect(find.text('В очереди: 1'), findsOneWidget);
    expect(find.text('Загружается: 1'), findsOneWidget);
    expect(find.text('Ошибки: 1'), findsOneWidget);

    await reveal(tester, const Key('download-cancel-queued-1'));
    expect(find.textContaining('Queued Song'), findsOneWidget);
    expect(find.byKey(const Key('download-cancel-queued-1')), findsOneWidget);
    expect(find.byKey(const Key('downloads-cancel-queued')), findsOneWidget);

    await reveal(tester, const Key('download-progress-running-1'));
    expect(find.textContaining('Running Song'), findsOneWidget);
    expect(find.textContaining('82%'), findsOneWidget);
    expect(find.byKey(const Key('download-progress-running-1')), findsOneWidget);

    await reveal(tester, const Key('download-retry-failed-1'));
    expect(find.byKey(const Key('download-retry-failed-1')), findsOneWidget);
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
    expect(find.textContaining('4.0 KB загружено'), findsOneWidget);
  });

  testWidgets('target selection persists exact folder picked by the user', (tester) async {
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

  testWidgets('retry runs only the selected task and does not wake old queue', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    await reveal(tester, const Key('download-retry-failed-1'));
    await tester.tap(find.byKey(const Key('download-retry-failed-1')));
    await tester.pumpAndSettle();

    expect(bridge.runCalled, isFalse);
    expect(bridge.runTaskIds, ['failed-1']);
    expect(
      bridge.items.firstWhere((e) => e['id'] == 'failed-1')['status'],
      'completed',
    );
    expect(
      bridge.items.firstWhere((e) => e['id'] == 'queued-1')['status'],
      'queued',
    );

    await reveal(
      tester,
      const Key('download-cancel-queued-1'),
      delta: -350,
    );
    await tester.tap(find.byKey(const Key('download-cancel-queued-1')));
    await tester.pumpAndSettle();
    expect(bridge.items.firstWhere((e) => e['id'] == 'queued-1')['status'], 'cancelled');
  });

  testWidgets('bulk wanted runs only tasks created by that action', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    await tester.tap(find.byKey(const Key('downloads-enqueue-wanted')));
    await tester.pumpAndSettle();

    expect(bridge.enqueueWantedCalls, 1);
    expect(bridge.runCalled, isFalse);
    expect(bridge.runTaskIds, ['wanted-1']);
    expect(
      bridge.items.firstWhere((e) => e['id'] == 'queued-1')['status'],
      'queued',
      reason: 'pre-existing queue must not be auto-run by a new bulk action',
    );
  });

  testWidgets('explicit cancel queue cancels waiting tasks without deleting files', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    await tester.tap(find.byKey(const Key('downloads-cancel-queued')));
    await tester.pumpAndSettle();
    expect(find.text('Отменить очередь?'), findsOneWidget);

    await tester.tap(find.byKey(const Key('downloads-cancel-queued-confirm')));
    await tester.pumpAndSettle();

    expect(bridge.items.firstWhere((e) => e['id'] == 'queued-1')['status'], 'cancelled');
    expect(find.text('В очереди: 0'), findsOneWidget);
  });

  testWidgets('leaving Downloads stops queue after the current track', (tester) async {
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
      bridge.items.firstWhere((e) => e['id'] == 'queued-2')['status'],
      'queued',
      reason: 'off-screen Downloads page must not keep draining the queue',
    );
  });

  testWidgets('completed file path is hidden by default and play/reveal are available', (tester) async {
    final bridge = FakeDownloadBridge();
    const path = r'C:\Music\Finished [yandex_777].mp3';
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
      'error': null,
      'canRetry': false,
      'canCancel': false,
    });
    final actions = FakeFileActions();
    await pumpDownloads(tester, bridge, fileActions: actions);
    await reveal(tester, const Key('download-play-completed-777'));

    expect(find.text(path), findsNothing);
    expect(find.byKey(const Key('download-play-completed-777')), findsOneWidget);
    expect(find.byKey(const Key('download-reveal-completed-777')), findsOneWidget);

    await tester.tap(find.byKey(const Key('download-toggle-path-completed-777')));
    await tester.pump();
    expect(find.text(path), findsOneWidget);

    await tester.tap(find.byKey(const Key('download-play-completed-777')));
    await tester.tap(find.byKey(const Key('download-reveal-completed-777')));
    await tester.pump();
    expect(actions.played, [path]);
    expect(actions.revealed, [path]);
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
