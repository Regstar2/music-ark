import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/content_label_bridge.dart';
import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/matching_bridge.dart';
import 'package:musicark_ui/matching_page.dart';
import 'package:musicark_ui/musicark_bridge.dart';
import 'package:musicark_ui/variant_acceptance_bridge.dart';

class EmptyMatchingBridge extends FakeMatchingBridge {
  @override
  Future<Map<String, dynamic>> matchingSummary() async => {
        'providerId': 'yandex_music',
        'yandexTracks': 0,
        'localTracks': 0,
        'processed': 0,
        'matched': 0,
        'conflicts': 0,
        'unmatched': 0,
      };

  @override
  Future<Map<String, dynamic>> matchingResults({
    int limit = 100,
    int offset = 0,
    String status = '',
    String search = '',
    String sort = 'confidence',
  }) async => {
        'count': 0,
        'limit': limit,
        'offset': offset,
        'items': <Map<String, dynamic>>[],
      };
}

class RecordingMatchingBridge extends FakeMatchingBridge {
  String lastStatus = '';
  String lastSearch = '';
  String lastSort = 'confidence';

  @override
  Future<Map<String, dynamic>> matchingResults({
    int limit = 100,
    int offset = 0,
    String status = '',
    String search = '',
    String sort = 'confidence',
  }) async {
    lastStatus = status;
    lastSearch = search;
    lastSort = sort;
    return super.matchingResults(
      limit: limit,
      offset: offset,
      status: status,
      search: search,
      sort: sort,
    );
  }
}

class PagingMatchingBridge extends FakeMatchingBridge {
  int pageCalls = 0;

  @override
  Future<Map<String, dynamic>> matchingResults({
    int limit = 100,
    int offset = 0,
    String status = '',
    String search = '',
    String sort = 'confidence',
  }) async {
    pageCalls++;
    final all = List.generate(
      55,
      (index) => <String, dynamic>{
        'providerId': 'yandex_music',
        'externalId': 'page-$index',
        'status': 'unmatched',
        'localFileId': null,
        'confidence': 0.0,
        'method': 'automatic',
        'score': <String, dynamic>{},
        'reason': 'no_candidates',
        'manual': false,
        'provider': {
          'title': 'Page Song $index',
          'artists': ['Artist $index'],
          'album_title': 'Album',
          'duration_seconds': 200,
        },
        'local': null,
      },
    );
    final end = (offset + limit) > all.length ? all.length : offset + limit;
    final items = offset >= all.length
        ? <Map<String, dynamic>>[]
        : all.sublist(offset, end);
    return {
      'count': all.length,
      'limit': limit,
      'offset': offset,
      'items': items,
    };
  }
}

void main() {
  Future<void> desktop(
    WidgetTester tester,
    Widget widget, {
    Locale locale = const Locale('ru'),
    ThemeMode themeMode = ThemeMode.light,
    Size size = const Size(1600, 950),
  }) async {
    await tester.binding.setSurfaceSize(size);
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final safeWidget = widget is MatchingPage
        ? MatchingPage(
            bridge: widget.bridge,
            contentLabelBridge: widget.contentLabelBridge is FakeContentLabelBridge
                ? widget.contentLabelBridge
                : FakeContentLabelBridge(),
            variantAcceptanceBridge:
                widget.variantAcceptanceBridge is FakeVariantAcceptanceBridge
                    ? widget.variantAcceptanceBridge
                    : FakeVariantAcceptanceBridge(),
          )
        : widget;
    await tester.pumpWidget(
      MaterialApp(
        locale: locale,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        theme: ThemeData(colorSchemeSeed: Colors.blue, useMaterial3: true),
        darkTheme: ThemeData(
          colorSchemeSeed: Colors.blue,
          brightness: Brightness.dark,
          useMaterial3: true,
        ),
        themeMode: themeMode,
        home: safeWidget,
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('main navigation opens Matching section', (tester) async {
    final yandex = FakeMusicArkBridge(startSignedIn: true);
    final matching = FakeMatchingBridge();
    await tester.binding.setSurfaceSize(const Size(1600, 950));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MusicArkDesktopApp(bridge: yandex, matchingBridge: matching),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('nav-matching')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('matching-page')), findsOneWidget);
    expect(find.byKey(const Key('matching-summary')), findsOneWidget);
  });

  testWidgets('summary metrics and counted filters are visible', (tester) async {
    await desktop(tester, MatchingPage(bridge: FakeMatchingBridge()));
    expect(find.byKey(const Key('matching-summary-yandex')), findsOneWidget);
    expect(find.byKey(const Key('matching-summary-local')), findsOneWidget);
    expect(find.byKey(const Key('matching-summary-matched')), findsOneWidget);
    expect(find.byKey(const Key('matching-summary-conflict')), findsOneWidget);
    expect(find.byKey(const Key('matching-summary-unmatched')), findsOneWidget);
    expect(find.text('Все 3'), findsOneWidget);
    expect(find.text('Совпало 1'), findsOneWidget);
    expect(find.text('Требует проверки 1'), findsOneWidget);
    expect(find.text('Не найдено 1'), findsOneWidget);
  });

  testWidgets('refresh only reloads current read state', (tester) async {
    final bridge = FakeMatchingBridge();
    await desktop(tester, MatchingPage(bridge: bridge));
    final resultCallsBeforeRefresh = bridge.resultCalls;
    await tester.tap(find.byKey(const Key('matching-refresh')));
    await tester.pumpAndSettle();
    expect(bridge.runCalls, 0);
    expect(bridge.variantRunAllCalls, 0);
    expect(bridge.resultCalls, resultCallsBeforeRefresh + 1);
  });

  testWidgets('matching and variant runs keep independent result banners', (
    tester,
  ) async {
    final bridge = FakeMatchingBridge();
    await desktop(tester, MatchingPage(bridge: bridge));
    await tester.tap(find.byKey(const Key('matching-run')));
    await tester.pumpAndSettle();
    expect(bridge.runCalls, 1);
    expect(find.byKey(const Key('matching-run-result')), findsOneWidget);
    await tester.tap(find.byKey(const Key('variant-run-all')));
    await tester.pumpAndSettle();
    expect(bridge.variantRunAllCalls, 1);
    expect(find.byKey(const Key('variant-run-result')), findsOneWidget);
  });

  testWidgets('filters search clear and sort use the bridge query contract', (
    tester,
  ) async {
    final bridge = RecordingMatchingBridge();
    await desktop(tester, MatchingPage(bridge: bridge));

    await tester.tap(find.byKey(const Key('matching-filter-conflict')));
    await tester.pumpAndSettle();
    expect(bridge.lastStatus, 'conflict');
    expect(find.byKey(const Key('matching-row-202')), findsOneWidget);

    await tester.tap(find.byKey(const Key('matching-filter-all')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('matching-search')),
      'Missing Artist',
    );
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();
    expect(bridge.lastSearch, 'Missing Artist');
    expect(find.byKey(const Key('matching-row-203')), findsOneWidget);

    await tester.tap(find.byKey(const Key('matching-search-clear')));
    await tester.pumpAndSettle();
    expect(bridge.lastSearch, '');

    await tester.tap(find.byKey(const Key('matching-sort')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Название').last);
    await tester.pumpAndSettle();
    expect(bridge.lastSort, 'title');
  });

  testWidgets('results use a Yandex-local comparison table', (tester) async {
    await desktop(tester, MatchingPage(bridge: FakeMatchingBridge()));
    expect(find.text('ЯНДЕКС МУЗЫКА'), findsOneWidget);
    expect(find.text('ЛОКАЛЬНЫЙ ФАЙЛ'), findsOneWidget);
    expect(find.text('УВЕРЕННОСТЬ'), findsOneWidget);
    expect(find.text('СТАТУС'), findsOneWidget);
    expect(find.byType(CircleAvatar), findsNothing);
    expect(find.text('Linkin Park — Numb'), findsWidgets);
    expect(find.text(r'C:\Music\Linkin Park\Numb.flac'), findsOneWidget);
    expect(find.text('97%'), findsOneWidget);
    expect(find.byKey(const Key('variant-badge-201')), findsOneWidget);
  });

  testWidgets('unmatched row exposes missing-local state without success meter', (
    tester,
  ) async {
    await desktop(tester, MatchingPage(bridge: FakeMatchingBridge()));
    expect(find.text('Локальный файл не найден'), findsOneWidget);
    expect(find.byKey(const Key('matching-confidence-unmatched')), findsOneWidget);
    expect(find.text('Не найдено'), findsWidgets);
  });

  testWidgets('pagination appends the next result page and updates counter', (
    tester,
  ) async {
    final bridge = PagingMatchingBridge();
    await desktop(tester, MatchingPage(bridge: bridge));
    expect(find.byKey(const Key('matching-load-more')), findsOneWidget);
    expect(find.text('Показано 50 из 55'), findsOneWidget);
    expect(bridge.pageCalls, 1);
    await tester.tap(find.byKey(const Key('matching-load-more')));
    await tester.pumpAndSettle();
    expect(bridge.pageCalls, 2);
    expect(find.text('Показано 55 из 55'), findsOneWidget);
    expect(find.byKey(const Key('matching-load-more')), findsNothing);
  });

  testWidgets('matched detail keeps comparison and content label controls', (
    tester,
  ) async {
    final bridge = FakeMatchingBridge();
    final labels = FakeContentLabelBridge();
    await desktop(
      tester,
      MatchingPage(
        bridge: bridge,
        contentLabelBridge: labels,
        variantAcceptanceBridge: FakeVariantAcceptanceBridge(),
      ),
    );
    await tester.tap(find.byKey(const Key('matching-row-201')));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('matching-track-comparison-table')),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('matching-provider-label')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('ОРИГИНАЛ').last);
    await tester.pumpAndSettle();
    expect(labels.providerLabels['201'], 'original');
  });

  testWidgets('conflict detail preserves manual accept workflow', (tester) async {
    final bridge = FakeMatchingBridge();
    await desktop(tester, MatchingPage(bridge: bridge));
    await tester.tap(find.byKey(const Key('matching-row-202')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('matching-accept-2')));
    await tester.pumpAndSettle();
    expect(bridge.acceptCalls, 1);
    expect(find.byKey(const Key('matching-detail')), findsNothing);
  });

  testWidgets('conflict detail preserves manual accept and reject workflows', (
    tester,
  ) async {
    final bridge = FakeMatchingBridge();
    await desktop(tester, MatchingPage(bridge: bridge));
    await tester.tap(find.byKey(const Key('matching-row-202')));
    await tester.pumpAndSettle();
    expect(find.text('Кандидаты'), findsOneWidget);
    expect(find.byKey(const Key('matching-accept-2')), findsOneWidget);
    expect(find.byKey(const Key('matching-reject-2')), findsOneWidget);
    await tester.tap(find.byKey(const Key('matching-reject-2')));
    await tester.pumpAndSettle();
    expect(bridge.rejectCalls, 1);
    expect(find.byKey(const Key('matching-detail')), findsNothing);
  });

  testWidgets('empty state is explicit', (tester) async {
    await desktop(tester, MatchingPage(bridge: EmptyMatchingBridge()));
    expect(find.byKey(const Key('matching-empty')), findsOneWidget);
    expect(find.text('Результатов сопоставления пока нет'), findsOneWidget);
  });

  testWidgets('narrow desktop layout stays renderable', (tester) async {
    await desktop(
      tester,
      MatchingPage(bridge: FakeMatchingBridge()),
      size: const Size(1000, 768),
    );
    expect(tester.takeException(), isNull);
    expect(find.byKey(const Key('matching-results')), findsOneWidget);
    expect(find.byType(SingleChildScrollView), findsWidgets);
  });

  testWidgets('matching workspace supports dark theme', (tester) async {
    await desktop(
      tester,
      MatchingPage(bridge: FakeMatchingBridge()),
      themeMode: ThemeMode.dark,
    );
    expect(tester.takeException(), isNull);
    expect(find.text('Сопоставление'), findsOneWidget);
    expect(find.byKey(const Key('matching-results')), findsOneWidget);
  });

  testWidgets('new matching workspace strings are localized to English', (
    tester,
  ) async {
    await desktop(
      tester,
      MatchingPage(bridge: FakeMatchingBridge()),
      locale: const Locale('en'),
    );
    expect(find.text('Matching'), findsOneWidget);
    expect(
      find.text('Compare the Yandex Music collection with the local library'),
      findsOneWidget,
    );
    expect(find.text('All 3'), findsOneWidget);
    expect(find.text('YANDEX MUSIC'), findsOneWidget);
    expect(find.text('LOCAL FILE'), findsOneWidget);
    expect(find.text('Needs review'), findsWidgets);
  });
}
