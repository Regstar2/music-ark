import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/coverage_bridge.dart';
import 'package:musicark_ui/coverage_page.dart';
import 'package:musicark_ui/download_bridge.dart';
import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/matching_bridge.dart';
import 'package:musicark_ui/musicark_bridge.dart';

void main() {
  Future<void> page(
    WidgetTester tester, {
    FakeCoverageBridge? coverage,
    FakeMatchingBridge? matching,
    FakeDownloadBridge? downloads,
    VoidCallback? onOpenMatching,
  }) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CoveragePage(
            bridge: coverage ?? FakeCoverageBridge(),
            matchingBridge: matching ?? FakeMatchingBridge(),
            downloadBridge: downloads,
            onOpenMatching: onOpenMatching,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('main navigation opens Coverage page', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final coverage = FakeCoverageBridge();
    await tester.pumpWidget(
      MusicArkDesktopApp(
        bridge: FakeMusicArkBridge(startSignedIn: true),
        matchingBridge: FakeMatchingBridge(),
        coverageBridge: coverage,
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('nav-coverage')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('coverage-page')), findsOneWidget);
    expect(find.text('Недостающие треки'), findsOneWidget);
    expect(coverage.summaryCalls, greaterThan(0));
  });

  testWidgets('summary renders and Missing is the default filter', (tester) async {
    await page(tester);

    expect(find.byKey(const Key('coverage-summary')), findsOneWidget);
    expect(find.textContaining('Yandex: 4'), findsOneWidget);
    expect(find.byKey(const ValueKey('coverage-row-203')), findsOneWidget);
    expect(find.byKey(const ValueKey('coverage-row-202')), findsNothing);

    final chip = tester.widget<ChoiceChip>(
      find.byKey(const Key('coverage-filter-missing')),
    );
    expect(chip.selected, isTrue);
  });

  testWidgets('primary filters keep Review, Not Analyzed, and Covered distinct', (
    tester,
  ) async {
    await page(tester);

    await tester.tap(find.byKey(const Key('coverage-filter-review')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('coverage-row-202')), findsOneWidget);
    expect(find.text('Требует проверки'), findsWidgets);

    await tester.tap(find.byKey(const Key('coverage-filter-not-analyzed')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('coverage-row-204')), findsOneWidget);
    expect(find.text('Не анализировалось'), findsWidgets);

    await tester.tap(find.byKey(const Key('coverage-filter-covered')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('coverage-row-201')), findsOneWidget);
    expect(find.text('Другая версия локально'), findsOneWidget);
    expect(find.text('Missing'), findsNothing);
  });

  testWidgets('collection selector scopes the page and exposes playlist order sort', (
    tester,
  ) async {
    await page(tester);

    await tester.tap(find.byKey(const Key('coverage-collection')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Workout').last);
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('coverage-row-203')), findsOneWidget);
    expect(find.textContaining('Yandex: 2'), findsOneWidget);

    final sort = tester.widget<DropdownButtonFormField<String>>(
      find.byKey(const Key('coverage-sort')),
    );
    expect(sort.initialValue, 'position');
  });

  testWidgets('search covers provider metadata and collection names', (tester) async {
    await page(tester);

    await tester.enterText(
      find.byKey(const Key('coverage-search')),
      'Missing Artist',
    );
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('coverage-row-203')), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('coverage-search')),
      'does-not-exist',
    );
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('coverage-list')), findsNothing);
    expect(find.text('Нет треков для выбранных фильтров.'), findsOneWidget);
  });

  testWidgets('wanted/ignored triage persists through bridge reloads', (tester) async {
    final coverage = FakeCoverageBridge();
    await page(tester, coverage: coverage);

    await tester.tap(find.byKey(const ValueKey('coverage-wanted-203')));
    await tester.pumpAndSettle();
    expect(coverage.setActionCalls, 1);
    expect(coverage.items.first['userAction'], 'wanted');

    await tester.tap(find.byKey(const ValueKey('coverage-ignored-203')));
    await tester.pumpAndSettle();
    expect(coverage.setActionCalls, 2);
    expect(coverage.items.first['userAction'], 'ignored');

    await tester.tap(find.byKey(const ValueKey('coverage-reset-203')));
    await tester.pumpAndSettle();
    expect(coverage.items.first['userAction'], 'unreviewed');
  });

  testWidgets('missing track can be downloaded in one click without prior Wanted action', (
    tester,
  ) async {
    final coverage = FakeCoverageBridge();
    final downloads = FakeDownloadBridge();
    await page(tester, coverage: coverage, downloads: downloads);

    expect(coverage.items.first['userAction'], 'unreviewed');
    expect(find.byKey(const ValueKey('coverage-download-203')), findsOneWidget);
    expect(find.text('Скачать'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('coverage-download-203')));
    await tester.pumpAndSettle();

    expect(coverage.items.first['userAction'], 'wanted');
    expect(downloads.enqueueCalls, 1);
    expect(downloads.lastEnqueuedId, '203');
    expect(downloads.runCalled, isTrue);
  });

  testWidgets('bulk selection applies wanted action without download control', (
    tester,
  ) async {
    final coverage = FakeCoverageBridge();
    await page(tester, coverage: coverage);

    await tester.tap(find.byKey(const ValueKey('coverage-select-203')));
    await tester.pump();
    expect(find.byKey(const Key('coverage-bulk-bar')), findsOneWidget);

    await tester.tap(find.byKey(const Key('coverage-bulk-wanted')));
    await tester.pumpAndSettle();
    expect(coverage.bulkActionCalls, 1);
    expect(coverage.items.first['userAction'], 'wanted');
    expect(find.textContaining('Скачать'), findsNothing);
  });

  testWidgets('details keep identity and variant sections independent', (
    tester,
  ) async {
    await page(tester);

    await tester.tap(find.byKey(const ValueKey('coverage-row-203')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('coverage-detail')), findsOneWidget);
    expect(find.text('Matching'), findsOneWidget);
    expect(find.text('Variant'), findsOneWidget);
    expect(find.text('Status: unmatched'), findsOneWidget);
    expect(find.text('N/A — no accepted local identity'), findsOneWidget);
  });

  testWidgets('Needs Review can route to existing Matching page', (tester) async {
    var opened = 0;
    await page(tester, onOpenMatching: () => opened++);

    await tester.tap(find.byKey(const Key('coverage-filter-review')));
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const ValueKey('coverage-open-matching-202')),
    );
    await tester.pump();
    expect(opened, 1);
  });

  testWidgets('all-not-analyzed empty state runs existing matching workflow', (
    tester,
  ) async {
    final coverage = FakeCoverageBridge();
    coverage.items.removeWhere(
      (item) => item['coverageStatus'] != 'not_analyzed',
    );
    final matching = FakeMatchingBridge();
    await page(tester, coverage: coverage, matching: matching);

    expect(
      find.text('Сначала выполните сопоставление библиотеки.'),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('coverage-run-matching')));
    await tester.pumpAndSettle();
    expect(matching.runCalls, 1);
  });

  testWidgets('coverage list paginates instead of materializing the full library', (
    tester,
  ) async {
    final coverage = FakeCoverageBridge();
    for (var index = 0; index < 105; index++) {
      coverage.items.add({
        'providerId': 'yandex_music',
        'externalId': 'bulk-$index',
        'provider': {
          'title': 'Bulk $index',
          'artists': ['Bulk Artist'],
          'album_title': 'Bulk Album',
          'duration_seconds': 180,
        },
        'collections': [
          {'id': 'liked', 'title': 'Мне нравится', 'position': index + 10},
        ],
        'coverageStatus': 'missing',
        'matchingStatus': 'unmatched',
        'confidence': 0.0,
        'reason': 'no_candidates',
        'variantStatus': null,
        'userAction': 'unreviewed',
        'local': null,
      });
    }
    await page(tester, coverage: coverage);

    final next = tester.widget<IconButton>(
      find.byKey(const Key('coverage-page-next')),
    );
    expect(next.onPressed, isNotNull);
    expect(find.textContaining('из 106'), findsOneWidget);

    await tester.tap(find.byKey(const Key('coverage-page-next')));
    await tester.pumpAndSettle();
    expect(find.textContaining('101–106 из 106'), findsOneWidget);
  });
}
