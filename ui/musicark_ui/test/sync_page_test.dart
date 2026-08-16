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

Future<void> _settle(WidgetTester tester) async {
  await tester.pump();
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('renders scope selector, target and creates preview plan', (tester) async {
    final bridge = FakeSyncBridge();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);

    expect(find.byKey(const Key('sync-scope-selector')), findsOneWidget);
    expect(find.byKey(const Key('sync-target-state')), findsOneWidget);
    expect(find.byKey(const Key('sync-create-plan')), findsOneWidget);

    await tester.tap(find.byKey(const Key('sync-create-plan')));
    await tester.pumpAndSettle();
    expect(bridge.createCalls, 1);
    expect(find.byKey(const Key('sync-summary')), findsOneWidget);
    expect(find.textContaining('Current coverage: 30.0%'), findsOneWidget);
    expect(find.byKey(const Key('sync-plan-details')), findsOneWidget);
  });

  testWidgets('shows no-target state and disables Apply', (tester) async {
    final bridge = FakeSyncBridge(targetConfigured: false);
    bridge.currentPlan = bridge.samplePlan();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);

    expect(find.textContaining('Не выбран'), findsOneWidget);
    final apply = tester.widget<FilledButton>(find.byKey(const Key('sync-apply')));
    expect(apply.onPressed, isNull);
  });

  testWidgets('stale plan shows banner and disables Apply', (tester) async {
    final bridge = FakeSyncBridge();
    bridge.currentPlan = bridge.samplePlan(status: 'stale');
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);

    expect(find.byKey(const Key('sync-stale-banner')), findsOneWidget);
    final apply = tester.widget<FilledButton>(find.byKey(const Key('sync-apply')));
    expect(apply.onPressed, isNull);
  });

  testWidgets('Apply requires confirmation and reports queue-only result', (tester) async {
    final bridge = FakeSyncBridge();
    bridge.currentPlan = bridge.samplePlan();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);

    await tester.tap(find.byKey(const Key('sync-apply')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sync-apply-confirmation')), findsOneWidget);
    expect(bridge.applyCalls, 0);

    await tester.tap(find.byKey(const Key('sync-confirm-apply')));
    await tester.pumpAndSettle();
    expect(bridge.applyCalls, 1);
    expect(find.byKey(const Key('sync-apply-result')), findsOneWidget);
    expect(find.textContaining('В очередь добавлено: 3'), findsOneWidget);
  });

  testWidgets('decision buttons update Coverage action and make plan stale', (tester) async {
    final bridge = FakeSyncBridge();
    bridge.currentPlan = bridge.samplePlan();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);

    await tester.scrollUntilVisible(
      find.text('Требует решения (1)'),
      200,
      scrollable: find.byKey(const Key('sync-page')),
    );
    await tester.tap(find.text('Требует решения (1)'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Нужен'));
    await tester.pumpAndSettle();

    expect(bridge.lastActionId, '2');
    expect(bridge.lastAction, 'wanted');
    expect(find.byKey(const Key('sync-stale-banner')), findsOneWidget);
  });

  testWidgets('identity and variant review link to Matching', (tester) async {
    final bridge = FakeSyncBridge();
    bridge.currentPlan = bridge.samplePlan();
    var matchingOpens = 0;
    await tester.pumpWidget(_app(bridge, onMatching: () => matchingOpens++));
    await _settle(tester);

    await tester.scrollUntilVisible(
      find.text('Проверить сопоставление (1)'),
      200,
      scrollable: find.byKey(const Key('sync-page')),
    );
    await tester.tap(find.text('Проверить сопоставление (1)'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Открыть сопоставление'));
    expect(matchingOpens, 1);

    await tester.tap(find.text('Проблемы версии (1)'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Открыть проверку версии'));
    expect(matchingOpens, 2);
  });

  testWidgets('history plan is persisted surface and planned plan can be cancelled', (tester) async {
    final bridge = FakeSyncBridge();
    bridge.currentPlan = bridge.samplePlan();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);

    expect(find.byKey(const Key('sync-history')), findsOneWidget);
    await tester.scrollUntilVisible(
      find.byKey(const Key('sync-cancel-plan')),
      200,
      scrollable: find.byKey(const Key('sync-page')),
    );
    await tester.tap(find.byKey(const Key('sync-cancel-plan')));
    await tester.pumpAndSettle();
    expect(bridge.cancelCalls, 1);
    expect(find.textContaining('cancelled'), findsOneWidget);
  });

  testWidgets('download target can be selected', (tester) async {
    final bridge = FakeSyncBridge(targetConfigured: false);
    await tester.pumpWidget(
      _app(bridge, picker: FakeLocalFolderPicker(r'D:\Music')),
    );
    await _settle(tester);

    await tester.tap(find.byKey(const Key('sync-select-target')));
    await tester.pumpAndSettle();
    expect(bridge.targetConfigured, isTrue);
    expect(find.text(r'D:\Music'), findsOneWidget);
  });
}
