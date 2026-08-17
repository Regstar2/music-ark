import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/content_label_bridge.dart';
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
  }) async => {'count': 0, 'limit': limit, 'offset': offset, 'items': <Map<String, dynamic>>[]};
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
        'provider': {'title': 'Page Song $index', 'artists': ['Artist $index'], 'album_title': 'Album', 'duration_seconds': 200},
        'local': null,
      },
    );
    final end = (offset + limit) > all.length ? all.length : offset + limit;
    final items = offset >= all.length ? <Map<String, dynamic>>[] : all.sublist(offset, end);
    return {'count': all.length, 'limit': limit, 'offset': offset, 'items': items};
  }
}

void main() {
  Future<void> desktop(WidgetTester tester, Widget widget) async {
    await tester.binding.setSurfaceSize(const Size(1600, 950));
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
    await tester.pumpWidget(MaterialApp(home: safeWidget));
    await tester.pumpAndSettle();
  }

  testWidgets('main navigation opens Matching section', (tester) async {
    final yandex = FakeMusicArkBridge(startSignedIn: true);
    final matching = FakeMatchingBridge();
    await tester.binding.setSurfaceSize(const Size(1600, 950));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(MusicArkDesktopApp(bridge: yandex, matchingBridge: matching));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('nav-matching')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('matching-page')), findsOneWidget);
    expect(find.byKey(const Key('matching-summary')), findsOneWidget);
  });

  testWidgets('empty Matching state is explicit and Russian', (tester) async {
    await desktop(tester, MatchingPage(bridge: EmptyMatchingBridge()));
    expect(find.byKey(const Key('matching-empty')), findsOneWidget);
    expect(find.text('Треков Яндекс Музыки: 0'), findsOneWidget);
    expect(find.text('Локальных треков: 0'), findsOneWidget);
  });

  testWidgets('summary and run matching refresh are visible', (tester) async {
    final bridge = FakeMatchingBridge();
    await desktop(tester, MatchingPage(bridge: bridge));
    expect(find.text('Совпало: 1'), findsOneWidget);
    expect(find.text('Требует проверки: 1'), findsOneWidget);
    expect(find.text('Не найдено: 1'), findsOneWidget);
    await tester.tap(find.byKey(const Key('matching-run')));
    await tester.pumpAndSettle();
    expect(bridge.runCalls, 1);
    expect(find.byKey(const Key('matching-run-result')), findsOneWidget);
  });

  testWidgets('filters and search use matching query contract', (tester) async {
    final bridge = FakeMatchingBridge();
    await desktop(tester, MatchingPage(bridge: bridge));
    await tester.tap(find.byKey(const Key('matching-filter-conflict')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('matching-row-202')), findsOneWidget);
    expect(find.byKey(const Key('matching-row-201')), findsNothing);
    await tester.tap(find.byKey(const Key('matching-filter-all')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('matching-search')), 'Missing Artist');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('matching-row-203')), findsOneWidget);
    expect(find.byKey(const Key('matching-row-201')), findsNothing);
  });

  testWidgets('pagination requests the next result page', (tester) async {
    final bridge = PagingMatchingBridge();
    await desktop(tester, MatchingPage(bridge: bridge));
    expect(find.byKey(const Key('matching-load-more')), findsOneWidget);
    expect(bridge.pageCalls, 1);
    await tester.tap(find.byKey(const Key('matching-load-more')));
    await tester.pumpAndSettle();
    expect(bridge.pageCalls, 2);
    expect(find.byKey(const Key('matching-load-more')), findsNothing);
  });

  testWidgets('matched detail is a three-column comparison table', (tester) async {
    final bridge = FakeMatchingBridge();
    await desktop(tester, MatchingPage(bridge: bridge));
    await tester.tap(find.byKey(const Key('matching-row-201')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('matching-track-comparison-table')), findsOneWidget);
    expect(find.text('Параметр'), findsOneWidget);
    expect(find.text('Яндекс Музыка'), findsOneWidget);
    expect(find.text('Локальный файл'), findsOneWidget);
    expect(find.text('Название'), findsOneWidget);
    expect(find.text('Исполнитель'), findsOneWidget);
    expect(find.text('Альбом'), findsOneWidget);
    expect(find.text('Длительность'), findsOneWidget);
    expect(find.text('Ярлык'), findsOneWidget);
    expect(find.text('Identity'), findsNothing);
    expect(find.text('Variant verification'), findsNothing);
    expect(find.textContaining('Audio similarity'), findsNothing);
    expect(find.text('Signals:'), findsNothing);
  });

  testWidgets('matching detail can set Yandex and local content labels', (tester) async {
    final bridge = FakeMatchingBridge();
    final labels = FakeContentLabelBridge();
    await desktop(tester, MatchingPage(bridge: bridge, contentLabelBridge: labels, variantAcceptanceBridge: FakeVariantAcceptanceBridge()));
    await tester.tap(find.byKey(const Key('matching-row-201')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('matching-provider-label')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('ОРИГИНАЛ').last);
    await tester.pumpAndSettle();
    expect(labels.providerLabels['201'], 'original');
    await tester.tap(find.byKey(const Key('matching-local-label')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('ЦЕНЗУРА').last);
    await tester.pumpAndSettle();
    expect(labels.localLabels[1], 'censored');
  });

  testWidgets('conflict detail exposes candidate comparison and manual accept', (tester) async {
    final bridge = FakeMatchingBridge();
    await desktop(tester, MatchingPage(bridge: bridge));
    await tester.tap(find.byKey(const Key('matching-row-202')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('matching-detail')), findsOneWidget);
    expect(find.text('Кандидаты'), findsOneWidget);
    expect(find.text(r'C:\Music\Song.flac'), findsOneWidget);
    await tester.tap(find.byKey(const Key('matching-accept-2')));
    await tester.pumpAndSettle();
    expect(bridge.acceptCalls, 1);
    expect(find.byKey(const Key('matching-detail')), findsNothing);
    expect(find.text('Совпало'), findsWidgets);
  });

  testWidgets('manual reject is routed through the bridge', (tester) async {
    final bridge = FakeMatchingBridge();
    await desktop(tester, MatchingPage(bridge: bridge));
    await tester.tap(find.byKey(const Key('matching-row-202')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('matching-reject-2')));
    await tester.pumpAndSettle();
    expect(bridge.rejectCalls, 1);
    expect(find.byKey(const Key('matching-detail')), findsNothing);
    expect(find.byKey(const Key('matching-row-202')), findsOneWidget);
  });
}
