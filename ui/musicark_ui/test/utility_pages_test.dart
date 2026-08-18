import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/account_session.dart';
import 'package:musicark_ui/app_settings.dart';
import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/musicark_bridge.dart';
import 'package:musicark_ui/settings_page.dart';

class _MemorySettingsStorage implements AppSettingsStorage {
  Map<String, dynamic> value = {};

  @override
  Future<Map<String, dynamic>> read() async => Map<String, dynamic>.from(value);

  @override
  Future<void> write(Map<String, dynamic> value) async {
    this.value = Map<String, dynamic>.from(value);
  }
}

void main() {
  Future<void> pumpDesktop(
    WidgetTester tester, {
    Size size = const Size(1500, 900),
    bool signedIn = false,
  }) async {
    tester.platformDispatcher.localeTestValue = const Locale('ru');
    addTearDown(tester.platformDispatcher.clearLocaleTestValue);
    await tester.binding.setSurfaceSize(size);
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MusicArkDesktopApp(
        bridge: FakeMusicArkBridge(startSignedIn: signedIn),
        settingsStorage: _MemorySettingsStorage(),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('Settings exposes compact utility controls and signed-out provider card', (
    tester,
  ) async {
    await pumpDesktop(tester);
    await tester.tap(find.byKey(const Key('nav-settings')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('settings-page')), findsOneWidget);
    expect(find.byKey(const Key('theme-selector')), findsOneWidget);
    expect(find.byKey(const Key('locale-selector')), findsOneWidget);
    expect(find.byKey(const Key('settings-auto-save-status')), findsOneWidget);
    expect(find.byKey(const Key('settings-account-card')), findsOneWidget);
    expect(find.byKey(const Key('settings-account-sign-in')), findsOneWidget);
    expect(find.byKey(const Key('settings-help')), findsOneWidget);
    expect(find.byKey(const Key('settings-about')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Settings provider card renders signed-in session', (tester) async {
    await pumpDesktop(tester, signedIn: true);
    await tester.tap(find.byKey(const Key('nav-settings')));
    await tester.pumpAndSettle();

    expect(find.text('Tester'), findsWidgets);
    expect(find.text('Активная сессия'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Settings account layout tolerates a long display name', (tester) async {
    await tester.binding.setSurfaceSize(const Size(620, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final settings = AppSettingsController(storage: _MemorySettingsStorage());
    final session = AccountSessionController();
    addTearDown(settings.dispose);
    addTearDown(session.dispose);
    await settings.load();
    const longName =
        'Very Long Provider Display Name That Must Not Break The Settings Account Card';
    session.applyPayload({
      'session': {
        'hasStoredToken': true,
        'account': {'displayName': longName},
      },
    });

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
        home: SettingsPage(
          settings: settings,
          session: session,
          onOpenYandex: () {},
          onOpenHelp: () {},
          onOpenAbout: () {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text(longName), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Help groups expanded guidance and returns to Settings', (tester) async {
    await pumpDesktop(tester);
    await tester.tap(find.byKey(const Key('nav-settings')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('settings-help')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('help-page')), findsOneWidget);
    expect(find.text('Библиотека'), findsOneWidget);
    expect(find.text('Анализ коллекции'), findsOneWidget);
    expect(find.text('Восстановление и действия'), findsOneWidget);
    expect(find.text('Приложение'), findsOneWidget);
    expect(find.byKey(const Key('help-topic-variant')), findsOneWidget);
    expect(find.byKey(const Key('help-topic-safety')), findsOneWidget);

    final variant = find.byKey(const Key('help-topic-variant'));
    await tester.ensureVisible(variant);
    await tester.tap(variant);
    await tester.pumpAndSettle();
    expect(
      find.textContaining('не превращает исходный результат анализа в SAME'),
      findsOneWidget,
    );

    final back = find.byKey(const Key('help-back-settings'));
    await tester.ensureVisible(back);
    await tester.tap(back);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('settings-page')), findsOneWidget);
  });

  testWidgets('About exposes version, diagnostics, licenses and project actions', (
    tester,
  ) async {
    await pumpDesktop(tester);
    await tester.tap(find.byKey(const Key('nav-settings')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('settings-about')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('about-page')), findsOneWidget);
    expect(find.byKey(const Key('about-product-card')), findsOneWidget);
    expect(find.text('0.9.7'), findsWidgets);
    expect(find.text('1.8.4'), findsOneWidget);
    expect(find.byKey(const Key('copy-diagnostics')), findsOneWidget);
    expect(find.byKey(const Key('open-source-licenses')), findsOneWidget);
    expect(find.byKey(const Key('copy-repository')), findsOneWidget);

    final back = find.byKey(const Key('about-back-settings'));
    await tester.ensureVisible(back);
    await tester.tap(back);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('settings-page')), findsOneWidget);
  });

  testWidgets('Utility pages reflow at a narrow desktop window without exceptions', (
    tester,
  ) async {
    await pumpDesktop(tester, size: const Size(900, 700));
    await tester.tap(find.byKey(const Key('nav-settings')));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);

    await tester.tap(find.byKey(const Key('settings-help')));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);

    await tester.tap(find.byKey(const Key('nav-settings')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('settings-about')));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
