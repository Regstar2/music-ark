import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/content_label_bridge.dart';
import 'package:musicark_ui/matching_bridge.dart';
import 'package:musicark_ui/matching_page.dart';
import 'package:musicark_ui/variant_acceptance_bridge.dart';

Map<String, dynamic> variantFixture(
  String status, {
  double? similarity,
  List<Map<String, dynamic>> segments = const [],
  List<String> reasons = const [],
}) => {
      'providerId': 'yandex_music',
      'externalId': '201',
      'localFileId': 1,
      'status': status,
      'variantStatus': status,
      'metadataScore': 0.95,
      'audioSimilarity': similarity,
      'variantReasons': reasons,
      'alteredSegments': segments,
      'referencePath': r'C:\MusicArk\.musicark\downloads\yandex\yandex_201.mp3',
      'metadata': <String, dynamic>{},
    };

class SlowVariantBridge extends FakeMatchingBridge {
  final Completer<Map<String, dynamic>> completer = Completer<Map<String, dynamic>>();
  @override
  Future<Map<String, dynamic>> variantRunAllAvailable() => completer.future;
}

class ErrorVariantBridge extends FakeMatchingBridge {
  @override
  Future<Map<String, dynamic>> variantRun(String externalId, {bool force = false}) async {
    throw const MatchingBridgeException('unexpected_error', 'синтетическая ошибка проверки версии');
  }
}

void main() {
  Future<void> desktop(WidgetTester tester, MatchingBridgeClient bridge, {VariantAcceptanceBridgeClient? acceptance}) async {
    await tester.binding.setSurfaceSize(const Size(1600, 950));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: MatchingPage(
          bridge: bridge,
          contentLabelBridge: FakeContentLabelBridge(),
          variantAcceptanceBridge: acceptance ?? FakeVariantAcceptanceBridge(),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('same-version badge is shown independently from match status', (tester) async {
    final bridge = FakeMatchingBridge();
    bridge.variants['201'] = variantFixture('same', similarity: 0.99);
    await desktop(tester, bridge);
    expect(find.descendant(of: find.byKey(const Key('variant-badge-201')), matching: find.text('Та же версия')), findsOneWidget);
    expect(find.text('Совпало'), findsWidgets);
  });

  testWidgets('altered badge and altered regions are visible in Russian', (tester) async {
    final bridge = FakeMatchingBridge();
    bridge.variants['201'] = variantFixture(
      'altered',
      similarity: 0.94,
      reasons: const ['localized_audio_differences', 'possible_clean_or_censored_variant'],
      segments: const [{'startSeconds': 72.0, 'endSeconds': 74.0, 'meanSimilarity': 0.31, 'minimumSimilarity': 0.20}],
    );
    await desktop(tester, bridge);
    expect(find.descendant(of: find.byKey(const Key('variant-badge-201')), matching: find.text('Изменённая запись')), findsOneWidget);
    await tester.tap(find.byKey(const Key('matching-row-201')));
    await tester.pumpAndSettle();
    expect(find.text('Результат: Изменённая запись'), findsOneWidget);
    expect(find.text('Сходство аудио: 94%'), findsOneWidget);
    expect(find.text('Признаки:'), findsOneWidget);
    expect(find.text('• Обнаружены локальные отличия в аудио.'), findsOneWidget);
    expect(find.text('• Возможна версия с цензурой или без цензуры.'), findsOneWidget);
    expect(find.byKey(const Key('variant-altered-region-0')), findsOneWidget);
    expect(find.text('1:12–1:14 (31%)'), findsOneWidget);
    expect(find.textContaining('Reference:'), findsNothing);
  });

  testWidgets('different version can be explicitly accepted and reset', (tester) async {
    final bridge = FakeMatchingBridge();
    bridge.variants['201'] = variantFixture('different_version', similarity: 0.61, reasons: const ['strong_version_marker_mismatch']);
    final acceptance = FakeVariantAcceptanceBridge();
    await desktop(tester, bridge, acceptance: acceptance);
    await tester.tap(find.byKey(const Key('matching-row-201')));
    await tester.pumpAndSettle();
    expect(find.text('Результат: Другая версия'), findsOneWidget);
    expect(find.byKey(const Key('variant-accept-current')), findsOneWidget);
    await tester.tap(find.byKey(const Key('variant-accept-current')));
    await tester.pumpAndSettle();
    expect(acceptance.acceptCalls, 1);
    expect(find.byKey(const Key('variant-reset-acceptance')), findsOneWidget);
    expect(find.textContaining('больше не требует проверки'), findsOneWidget);
    await tester.tap(find.byKey(const Key('variant-reset-acceptance')));
    await tester.pumpAndSettle();
    expect(acceptance.resetCalls, 1);
    expect(find.byKey(const Key('variant-accept-current')), findsOneWidget);
  });

  testWidgets('not checked badge and verify button are shown in Russian', (tester) async {
    final bridge = FakeMatchingBridge();
    bridge.variants.clear();
    await desktop(tester, bridge);
    expect(find.descendant(of: find.byKey(const Key('variant-badge-201')), matching: find.text('Не проверено')), findsOneWidget);
    await tester.tap(find.byKey(const Key('matching-row-201')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('variant-verify')), findsOneWidget);
    expect(find.text('Результат: Не проверено'), findsOneWidget);
  });

  testWidgets('audio verification unavailable state is visible', (tester) async {
    final bridge = FakeMatchingBridge(ffmpegAvailable: false);
    await desktop(tester, bridge);
    expect(find.byKey(const Key('variant-unavailable')), findsOneWidget);
    expect(find.text('Аудиосравнение недоступно: ffmpeg не найден'), findsOneWidget);
  });

  testWidgets('batch variant verification exposes progress state', (tester) async {
    final bridge = SlowVariantBridge();
    await desktop(tester, bridge);
    await tester.tap(find.byKey(const Key('variant-run-all')));
    await tester.pump();
    expect(find.byKey(const Key('variant-progress')), findsOneWidget);
    expect(find.text('Проверка версий…'), findsOneWidget);
    bridge.completer.complete({'eligibleMatched': 1, 'available': 1, 'processed': 1, 'cached': 0, 'errors': 0, 'same': 1, 'altered': 0, 'differentVersion': 0, 'uncertain': 0, 'notChecked': 0});
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('variant-run-result')), findsOneWidget);
  });

  testWidgets('variant verification error stays local to detail dialog', (tester) async {
    final bridge = ErrorVariantBridge();
    bridge.variants.clear();
    await desktop(tester, bridge);
    await tester.tap(find.byKey(const Key('matching-row-201')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('variant-verify')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('variant-detail-error')), findsOneWidget);
    expect(find.text('синтетическая ошибка проверки версии'), findsOneWidget);
    expect(find.byKey(const Key('matching-detail')), findsOneWidget);
  });

  testWidgets('row refreshes after single-track analysis', (tester) async {
    final bridge = FakeMatchingBridge();
    bridge.variants.clear();
    await desktop(tester, bridge);
    await tester.tap(find.byKey(const Key('matching-row-201')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('variant-verify')));
    await tester.pumpAndSettle();
    expect(bridge.variantRunCalls, 1);
    expect(find.text('Результат: Та же версия'), findsOneWidget);
    await tester.tap(find.text('Закрыть'));
    await tester.pumpAndSettle();
    expect(find.descendant(of: find.byKey(const Key('variant-badge-201')), matching: find.text('Та же версия')), findsOneWidget);
  });
}
