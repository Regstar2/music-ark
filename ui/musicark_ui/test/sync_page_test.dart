import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:musicark_ui/folder_picker.dart';
import 'package:musicark_ui/sync_bridge.dart';
import 'package:musicark_ui/sync_page.dart';

Widget _app(
  FakeSyncBridge bridge, {
  LocalFolderPicker? picker,
  VoidCallback? onDownloads,
  VoidCallback? onMatching,
}) {
  return MaterialApp(
    home: SyncPage(
      bridge: bridge,
      folderPicker: picker ?? FakeLocalFolderPicker(r'C:\Music'),
      onOpenDownloads: onDownloads,
      onOpenMatching: onMatching,
    ),
  );
}

Finder _syncScrollable() => find.descendant(
      of: find.byKey(const Key('sync-page')),
      matching: find.byType(Scrollable),
    );

Future<void> _settle(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(1400, 1000));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pump();
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows synchronization diff immediately without plan/history UI', (
    tester,
  ) async {
    final bridge = FakeSyncBridge();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);

    expect(bridge.createCalls, 1);
    expect(find.byKey(const Key('sync-summary')), findsOneWidget);
    expect(find.textContaining('Разница: Вся библиотека'), findsOneWidget);
    expect(find.text('В Яндекс Музыке'), findsOneWidget);
    expect(find.text('Уже локально'), findsOneWidget);
    expect(find.text('К скачиванию'), findsOneWidget);
    expect(find.byKey(const Key('sync-diff-details')), findsOneWidget);

    expect(find.text('Создать план'), findsNothing);
    expect(find.text('Текущий план'), findsNothing);
    expect(find.text('История планов'), findsNothing);
    expect(find.textContaining('stale'), findsNothing);
  });

  testWidgets('changing scope rebuilds diff for exactly the selected collection', (
    tester,
  ) async {
    final bridge = FakeSyncBridge();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);

    final selector = find.byKey(
      const ValueKey('sync-scope-selector-all|'),
    );
    expect(selector, findsOneWidget);

    await tester.tap(selector);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Focus').last);
    await tester.pumpAndSettle();

    expect(bridge.createCalls, 2);
    expect(find.textContaining('Разница: Focus'), findsOneWidget);
  });

  testWidgets('no target disables synchronization but still shows diff', (
    tester,
  ) async {
    final bridge = FakeSyncBridge(targetConfigured: false);
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);

    expect(find.text('Папка не выбрана.'), findsOneWidget);
    expect(find.byKey(const Key('sync-summary')), findsOneWidget);
    final button =
        tester.widget<FilledButton>(find.byKey(const Key('sync-now')));
    expect(button.onPressed, isNull);
  });

  testWidgets('synchronize rebuilds current diff and requires confirmation', (
    tester,
  ) async {
    final bridge = FakeSyncBridge();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);

    expect(bridge.createCalls, 1);
    await tester.tap(find.byKey(const Key('sync-now')));
    await tester.pumpAndSettle();

    expect(bridge.createCalls, 2);
    expect(find.byKey(const Key('sync-confirmation')), findsOneWidget);
    expect(bridge.applyCalls, 0);

    await tester.tap(find.byKey(const Key('sync-confirm')));
    await tester.pumpAndSettle();

    expect(bridge.applyCalls, 1);
    expect(bridge.createCalls, 3);
    expect(find.textContaining('Добавлено в очередь: 3'), findsOneWidget);
  });

  testWidgets('decision actions immediately rebuild the visible diff', (
    tester,
  ) async {
    final bridge = FakeSyncBridge();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);

    await tester.scrollUntilVisible(
      find.text('Нужно решить (1)'),
      200,
      scrollable: _syncScrollable(),
    );
    await tester.tap(find.text('Нужно решить (1)'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Скачать'));
    await tester.pumpAndSettle();

    expect(bridge.lastActionId, '2');
    expect(bridge.lastAction, 'wanted');
    expect(bridge.createCalls, 2);
    expect(find.textContaining('stale'), findsNothing);
  });

  testWidgets('matching problems route to Matching without exposing planner terms', (
    tester,
  ) async {
    final bridge = FakeSyncBridge();
    var matchingOpens = 0;
    await tester.pumpWidget(
      _app(bridge, onMatching: () => matchingOpens++),
    );
    await _settle(tester);

    await tester.scrollUntilVisible(
      find.text('Нужно сопоставить (2)'),
      200,
      scrollable: _syncScrollable(),
    );
    await tester.tap(find.text('Нужно сопоставить (2)'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Открыть сопоставление').first);
    expect(matchingOpens, 1);
  });

  testWidgets('download target selection refreshes diff', (tester) async {
    final bridge = FakeSyncBridge(targetConfigured: false);
    await tester.pumpWidget(
      _app(bridge, picker: FakeLocalFolderPicker(r'D:\Music')),
    );
    await _settle(tester);

    expect(bridge.createCalls, 1);
    await tester.tap(find.byKey(const Key('sync-select-target')));
    await tester.pumpAndSettle();

    expect(bridge.targetConfigured, isTrue);
    expect(find.text(r'D:\Music'), findsOneWidget);
    expect(bridge.createCalls, 2);
  });

  testWidgets('downloads shortcut remains available from diff view', (
    tester,
  ) async {
    final bridge = FakeSyncBridge();
    var opens = 0;
    await tester.pumpWidget(
      _app(bridge, onDownloads: () => opens++),
    );
    await _settle(tester);

    await tester.tap(find.byKey(const Key('sync-open-downloads')));
    expect(opens, 1);
  });
}
