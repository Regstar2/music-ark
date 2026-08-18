import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:musicark_ui/folder_picker.dart';
import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/sync_bridge.dart';
import 'package:musicark_ui/sync_page.dart';

Widget _app(
  FakeSyncBridge bridge, {
  LocalFolderPicker? picker,
  VoidCallback? onDownloads,
  VoidCallback? onMatching,
  Locale locale = const Locale('ru'),
}) {
  return MaterialApp(
    locale: locale,
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
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

Future<void> _settle(
  WidgetTester tester, {
  Size size = const Size(1400, 1200),
}) async {
  await tester.binding.setSurfaceSize(size);
  await tester.pump();
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows redesigned summary, coverage and plan filters', (tester) async {
    final bridge = FakeSyncBridge();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);
    addTearDown(() => tester.binding.setSurfaceSize(null));

    expect(bridge.createCalls, 1);
    expect(find.byKey(const Key('sync-summary')), findsOneWidget);
    expect(find.byKey(const Key('sync-coverage')), findsOneWidget);
    expect(find.byKey(const Key('sync-metric-yandex')), findsOneWidget);
    expect(find.byKey(const Key('sync-metric-local')), findsOneWidget);
    expect(find.byKey(const Key('sync-metric-download')), findsOneWidget);
    expect(find.byKey(const Key('sync-metric-queued')), findsOneWidget);
    expect(find.byKey(const Key('sync-metric-attention')), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const Key('sync-metric-attention')),
        matching: find.text('5'),
      ),
      findsOneWidget,
    );
    expect(find.text('Найдено: 30%'), findsOneWidget);
    expect(find.text('Завершено: 60%'), findsOneWidget);
    expect(find.byKey(const Key('sync-diff-details')), findsOneWidget);
    expect(find.byKey(const Key('sync-filter-download')), findsOneWidget);
    expect(find.text('Скачать 1'), findsOneWidget);
    expect(find.text('Решение 1'), findsOneWidget);
    expect(find.text('Сопоставление 2'), findsOneWidget);
    expect(find.text('Проверка версии 1'), findsOneWidget);
    expect(find.text('Локальная библиотека 1'), findsOneWidget);
    expect(find.byType(ExpansionTile), findsNothing);
  });

  testWidgets('changing scope rebuilds exactly selected collection', (tester) async {
    final bridge = FakeSyncBridge();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final selector = find.byKey(const ValueKey('sync-scope-selector-all|'));
    expect(selector, findsOneWidget);
    await tester.tap(selector);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Focus').last);
    await tester.pumpAndSettle();

    expect(bridge.createCalls, 2);
    expect(find.text('Коллекция: Focus'), findsOneWidget);
  });

  testWidgets('no target disables synchronization but keeps diff visible', (tester) async {
    final bridge = FakeSyncBridge(targetConfigured: false);
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);
    addTearDown(() => tester.binding.setSurfaceSize(null));

    expect(find.text('Выберите папку для загрузок'), findsOneWidget);
    expect(find.byKey(const Key('sync-summary')), findsOneWidget);
    final button = tester.widget<FilledButton>(find.byKey(const Key('sync-now')));
    expect(button.onPressed, isNull);
  });

  testWidgets('synchronize rebuilds diff and still requires confirmation', (tester) async {
    final bridge = FakeSyncBridge();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);
    addTearDown(() => tester.binding.setSurfaceSize(null));

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
    expect(find.textContaining('Выполнено 3 из 3 действий'), findsOneWidget);
  });

  testWidgets('plan filters are local presentation state', (tester) async {
    final bridge = FakeSyncBridge();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);
    addTearDown(() => tester.binding.setSurfaceSize(null));

    expect(bridge.createCalls, 1);
    expect(find.byKey(const Key('sync-download-1')), findsOneWidget);
    expect(find.byKey(const Key('sync-decision-2')), findsNothing);

    await tester.tap(find.byKey(const Key('sync-filter-decision')));
    await tester.pump();

    expect(bridge.createCalls, 1);
    expect(find.byKey(const Key('sync-download-1')), findsNothing);
    expect(find.byKey(const Key('sync-decision-2')), findsOneWidget);
  });

  testWidgets('decision action still updates bridge and rebuilds plan', (tester) async {
    final bridge = FakeSyncBridge();
    await tester.pumpWidget(_app(bridge));
    await _settle(tester);
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.tap(find.byKey(const Key('sync-filter-decision')));
    await tester.pump();
    final row = find.byKey(const Key('sync-decision-2'));
    final action = find.descendant(of: row, matching: find.text('Скачать'));
    await tester.tap(action);
    await tester.pumpAndSettle();

    expect(bridge.lastActionId, '2');
    expect(bridge.lastAction, 'wanted');
    expect(bridge.createCalls, 2);
  });

  testWidgets('matching and variant operations keep Matching routes', (tester) async {
    final bridge = FakeSyncBridge();
    var opens = 0;
    await tester.pumpWidget(_app(bridge, onMatching: () => opens++));
    await _settle(tester);
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.tap(find.byKey(const Key('sync-filter-matching')));
    await tester.pump();
    await tester.tap(
      find.descendant(
        of: find.byKey(const Key('sync-review-3')),
        matching: find.text('Открыть в сопоставлении'),
      ),
    );
    expect(opens, 1);

    await tester.tap(find.byKey(const Key('sync-filter-variant')));
    await tester.pump();
    await tester.tap(
      find.descendant(
        of: find.byKey(const Key('sync-variant-5')),
        matching: find.text('Проверить версии'),
      ),
    );
    expect(opens, 2);
  });

  testWidgets('download target selection refreshes diff', (tester) async {
    final bridge = FakeSyncBridge(targetConfigured: false);
    await tester.pumpWidget(
      _app(bridge, picker: FakeLocalFolderPicker(r'D:\Music')),
    );
    await _settle(tester);
    addTearDown(() => tester.binding.setSurfaceSize(null));

    expect(bridge.createCalls, 1);
    await tester.tap(find.byKey(const Key('sync-select-target')));
    await tester.pumpAndSettle();

    expect(bridge.targetConfigured, isTrue);
    expect(find.text(r'D:\Music'), findsOneWidget);
    expect(bridge.createCalls, 2);
  });

  testWidgets('downloads shortcut remains available from status card', (tester) async {
    final bridge = FakeSyncBridge();
    var opens = 0;
    await tester.pumpWidget(_app(bridge, onDownloads: () => opens++));
    await _settle(tester);
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.tap(find.byKey(const Key('sync-open-downloads')));
    expect(opens, 1);
  });

  testWidgets('narrow desktop layout keeps required actions without overflow', (tester) async {
    final bridge = FakeSyncBridge();
    await tester.pumpWidget(
      _app(
        bridge,
        onDownloads: () {},
        onMatching: () {},
      ),
    );
    await _settle(tester, size: const Size(620, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    expect(tester.takeException(), isNull);
    expect(find.byKey(const Key('sync-now')), findsOneWidget);
    expect(find.byKey(const Key('sync-open-downloads')), findsOneWidget);
    expect(find.byKey(const Key('sync-plan-table-header')), findsNothing);
    expect(find.byKey(const Key('sync-filter-download')), findsOneWidget);
  });

  testWidgets('new Sync workspace is localized in English', (tester) async {
    final bridge = FakeSyncBridge();
    await tester.pumpWidget(_app(bridge, locale: const Locale('en')));
    await _settle(tester);
    addTearDown(() => tester.binding.setSurfaceSize(null));

    expect(find.text('Sync'), findsWidgets);
    expect(
      find.text(
        'Builds and applies a controlled plan for wanted missing tracks. Sync does not delete local-only files and does not automatically replace a Different Version recording.',
      ),
      findsWidgets,
    );
    expect(find.text('Needs review'), findsWidgets);
    expect(find.text('Download 1'), findsOneWidget);
    expect(find.text('Синхронизация'), findsNothing);
  });
}
