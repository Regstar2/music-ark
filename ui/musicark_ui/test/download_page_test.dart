import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/download_bridge.dart';
import 'package:musicark_ui/download_page.dart';
import 'package:musicark_ui/folder_picker.dart';
import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/musicark_bridge.dart';

void main() {
  Future<void> pumpDownloads(
    WidgetTester tester,
    FakeDownloadBridge bridge, {
    LocalFolderPicker? picker,
  }) async {
    await tester.binding.setSurfaceSize(const Size(1400, 900));
    await tester.pumpWidget(
      MaterialApp(
        home: DownloadPage(
          bridge: bridge,
          folderPicker: picker ?? FakeLocalFolderPicker(r'C:\Music'),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('Downloads page shows persisted queue states and real progress', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    expect(find.text('Загрузки'), findsOneWidget);
    expect(find.text('В очереди: 1'), findsOneWidget);
    expect(find.text('Загружается: 1'), findsOneWidget);
    expect(find.text('Ошибки: 1'), findsOneWidget);
    expect(find.textContaining('Queued Song'), findsOneWidget);
    expect(find.textContaining('Running Song'), findsOneWidget);
    expect(find.textContaining('82%'), findsOneWidget);
    expect(find.byKey(const Key('download-progress-running-1')), findsOneWidget);
    expect(find.byKey(const Key('download-retry-failed-1')), findsOneWidget);
    expect(find.byKey(const Key('download-cancel-queued-1')), findsOneWidget);

    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('unknown total renders indeterminate progress', (tester) async {
    final bridge = FakeDownloadBridge();
    bridge.items[1]['totalBytes'] = null;
    bridge.items[1]['progress'] = null;
    bridge.items[1]['downloadedBytes'] = 4096;
    await pumpDownloads(tester, bridge);

    final indicator = tester.widget<LinearProgressIndicator>(
      find.byKey(const Key('download-progress-running-1')),
    );
    expect(indicator.value, isNull);
    expect(find.textContaining('4.0 KB загружено'), findsOneWidget);

    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('target selection uses folder picker abstraction', (tester) async {
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
    expect(find.textContaining(r'D:\Music\MusicArk'), findsOneWidget);

    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('retry and queued cancel update persisted view', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    await tester.tap(find.byKey(const Key('download-retry-failed-1')));
    await tester.pumpAndSettle();
    expect(bridge.items.firstWhere((e) => e['id'] == 'failed-1')['status'], 'queued');

    await tester.tap(find.byKey(const Key('download-cancel-queued-1')));
    await tester.pumpAndSettle();
    expect(bridge.items.firstWhere((e) => e['id'] == 'queued-1')['status'], 'cancelled');

    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('bulk wanted action is available', (tester) async {
    final bridge = FakeDownloadBridge();
    await pumpDownloads(tester, bridge);

    await tester.tap(find.byKey(const Key('downloads-enqueue-wanted')));
    await tester.pumpAndSettle();
    expect(bridge.enqueueWantedCalls, 1);

    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('top-level navigation opens Downloads', (tester) async {
    final downloadBridge = FakeDownloadBridge();
    await tester.binding.setSurfaceSize(const Size(1500, 900));
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

    await tester.binding.setSurfaceSize(null);
  });
}
