import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/account_control.dart';
import 'package:musicark_ui/account_session.dart';
import 'package:musicark_ui/l10n/app_localizations.dart';

void main() {
  Future<void> pumpControl(
    WidgetTester tester,
    AccountSessionController session, {
    Locale locale = const Locale('ru'),
    VoidCallback? onOpenYandex,
    Future<void> Function()? onLogout,
  }) async {
    await tester.pumpWidget(
      MaterialApp(
        locale: locale,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: SizedBox(
            width: 220,
            child: AccountControl(
              session: session,
              onOpenYandex: onOpenYandex ?? () {},
              onLogout: onLogout ?? () async {},
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('logged out account control opens existing Yandex flow', (tester) async {
    final session = AccountSessionController();
    session.applyPayload({
      'session': {'hasStoredToken': false, 'account': <String, dynamic>{}},
    });
    var opened = false;

    await pumpControl(tester, session, onOpenYandex: () => opened = true);

    expect(find.text('Войти'), findsOneWidget);
    await tester.tap(find.byKey(const Key('global-account-sign-in')));
    expect(opened, isTrue);
  });

  testWidgets('logged in account uses initials and English menu', (tester) async {
    final session = AccountSessionController();
    session.applyPayload({
      'session': {
        'hasStoredToken': true,
        'account': {'displayName': 'Ivan Petrov'},
      },
    });
    var loggedOut = false;

    await pumpControl(
      tester,
      session,
      locale: const Locale('en'),
      onLogout: () async => loggedOut = true,
    );

    expect(find.byKey(const Key('global-account-initials')), findsOneWidget);
    expect(find.text('IP'), findsOneWidget);
    await tester.tap(find.byKey(const Key('global-account-menu')));
    await tester.pumpAndSettle();
    expect(find.text('Open Yandex Music'), findsOneWidget);
    expect(find.text('Sign out'), findsOneWidget);
    await tester.tap(find.text('Sign out'));
    await tester.pumpAndSettle();
    expect(loggedOut, isTrue);
  });

  testWidgets('missing display name falls back to generic icon', (tester) async {
    final session = AccountSessionController();
    session.applyPayload({
      'session': {
        'hasStoredToken': true,
        'account': {'providerUserId': '42'},
      },
    });

    await pumpControl(tester, session);

    expect(find.byKey(const Key('global-account-generic-avatar')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('long display name does not overflow sidebar', (tester) async {
    final session = AccountSessionController();
    session.applyPayload({
      'session': {
        'hasStoredToken': true,
        'account': {
          'displayName': 'Очень длинное отображаемое имя пользователя Яндекс Музыки',
        },
      },
    });

    await pumpControl(tester, session);

    expect(tester.takeException(), isNull);
  });
}
