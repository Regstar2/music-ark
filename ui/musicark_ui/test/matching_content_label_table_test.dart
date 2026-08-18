import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/content_label_bridge.dart';
import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/matching_bridge.dart';
import 'package:musicark_ui/matching_page.dart';
import 'package:musicark_ui/variant_acceptance_bridge.dart';

void main() {
  testWidgets('matching rows show provider and local content labels', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 950));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final labels = FakeContentLabelBridge()
      ..providerLabels['201'] = 'original'
      ..localLabels[1] = 'censored';

    await tester.pumpWidget(
      MaterialApp(
        locale: const Locale('ru'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        theme: ThemeData(colorSchemeSeed: Colors.blue, useMaterial3: true),
        home: MatchingPage(
          bridge: FakeMatchingBridge(),
          contentLabelBridge: labels,
          variantAcceptanceBridge: FakeVariantAcceptanceBridge(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('matching-provider-content-label-201')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('matching-local-content-label-201')),
      findsOneWidget,
    );
    expect(find.text('ОРИГИНАЛ'), findsOneWidget);
    expect(find.text('ЦЕНЗУРА'), findsOneWidget);
  });

  testWidgets('matching table refreshes labels after closing details', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 950));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final labels = FakeContentLabelBridge();
    await tester.pumpWidget(
      MaterialApp(
        locale: const Locale('ru'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        theme: ThemeData(colorSchemeSeed: Colors.blue, useMaterial3: true),
        home: MatchingPage(
          bridge: FakeMatchingBridge(),
          contentLabelBridge: labels,
          variantAcceptanceBridge: FakeVariantAcceptanceBridge(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('matching-provider-content-label-201')),
      findsNothing,
    );

    await tester.tap(find.byKey(const Key('matching-row-201')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('matching-provider-label')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('ОРИГИНАЛ').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Закрыть'));
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('matching-provider-content-label-201')),
      findsOneWidget,
    );
    expect(find.text('ОРИГИНАЛ'), findsOneWidget);
  });
}
