import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/content_label_bridge.dart';
import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/yandex_content_labels.dart';

void main() {
  testWidgets('Yandex cached tracks can be marked ORIGINAL or CENSORED', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    final labels = FakeContentLabelBridge()..providerLabels['101'] = 'original';
    await tester.binding.setSurfaceSize(const Size(1200, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        locale: const Locale('ru'),
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: YandexContentLabelsButton(
            bridge: bridge,
            labelBridge: labels,
          ),
        ),
      ),
    );

    await tester.tap(find.byKey(const Key('yandex-content-labels-open')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('yandex-content-labels-dialog')), findsOneWidget);
    expect(find.byKey(const Key('yandex-content-label-101')), findsOneWidget);
    expect(find.text('ОРИГИНАЛ'), findsOneWidget);

    await tester.tap(find.byKey(const Key('yandex-content-label-menu-101')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('ЦЕНЗУРА').last);
    await tester.pumpAndSettle();
    expect(labels.providerLabels['101'], 'censored');
  });
}
