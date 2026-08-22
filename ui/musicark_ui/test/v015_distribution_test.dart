import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:musicark_ui/distribution_settings_card.dart';
import 'package:musicark_ui/feedback_bridge.dart';
import 'package:musicark_ui/update_bridge.dart';

Widget _host({
  required UpdateBridgeClient updates,
  required FeedbackBridgeClient feedback,
  Locale locale = const Locale('en'),
}) {
  return MaterialApp(
    locale: locale,
    supportedLocales: const [Locale('en'), Locale('ru')],
    localizationsDelegates: const [
      GlobalMaterialLocalizations.delegate,
      GlobalWidgetsLocalizations.delegate,
      GlobalCupertinoLocalizations.delegate,
    ],
    home: Scaffold(
      body: SingleChildScrollView(
        child: DistributionSettingsCard(
          updateBridge: updates,
          feedbackBridge: feedback,
          autoCheck: false,
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('check prepare and explicit install confirmation are separate', (tester) async {
    final updates = FakeUpdateBridge(currentVersion: '0.15.0', latestVersion: '0.16.0');
    final feedback = FakeFeedbackBridge();
    await tester.pumpWidget(_host(updates: updates, feedback: feedback));

    await tester.tap(find.byKey(const Key('check-updates')));
    await tester.pumpAndSettle();
    expect(updates.checkCalls, 1);
    expect(find.text('Update available'), findsOneWidget);
    expect(find.byKey(const Key('prepare-update')), findsOneWidget);

    await tester.tap(find.byKey(const Key('prepare-update')));
    await tester.pumpAndSettle();
    expect(updates.prepareCalls, 1);
    expect(find.byKey(const Key('install-update')), findsOneWidget);
    expect(updates.applyCalls, 0);

    await tester.tap(find.byKey(const Key('install-update')));
    await tester.pumpAndSettle();
    expect(find.text('Install MusicArk update?'), findsOneWidget);
    expect(updates.applyCalls, 0);

    await tester.tap(find.byKey(const Key('confirm-install-update')));
    await tester.pumpAndSettle();
    expect(updates.applyCalls, 1);
    expect(find.text('Installer launched.'), findsOneWidget);
  });

  testWidgets('feedback actions stay explicit', (tester) async {
    final updates = FakeUpdateBridge();
    final feedback = FakeFeedbackBridge();
    await tester.pumpWidget(_host(updates: updates, feedback: feedback));

    await tester.tap(find.byKey(const Key('report-bug')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('request-feature')));
    await tester.pump();

    expect(feedback.bugOpenCalls, 1);
    expect(feedback.featureOpenCalls, 1);
  });

  testWidgets('Russian copy is available without a second localization system', (tester) async {
    await tester.pumpWidget(
      _host(
        updates: FakeUpdateBridge(currentVersion: '0.15.0', latestVersion: '0.15.0'),
        feedback: FakeFeedbackBridge(),
        locale: const Locale('ru'),
      ),
    );
    expect(find.text('Обновления и обратная связь'), findsOneWidget);
    expect(find.text('Сообщить об ошибке'), findsOneWidget);
  });
}
