import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/app_settings.dart';
import 'package:musicark_ui/audio_player.dart';
import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/musicark_bridge.dart';

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
  Future<_MemorySettingsStorage> pumpDesktop(
    WidgetTester tester, {
    Locale locale = const Locale('ru'),
  }) async {
    tester.platformDispatcher.localeTestValue = locale;
    addTearDown(tester.platformDispatcher.clearLocaleTestValue);
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final storage = _MemorySettingsStorage();
    await tester.pumpWidget(
      MusicArkDesktopApp(
        bridge: FakeMusicArkBridge(startSignedIn: false),
        settingsStorage: storage,
      ),
    );
    await tester.pumpAndSettle();
    return storage;
  }

  testWidgets('unsupported system locale deterministically falls back to Russian', (tester) async {
    await pumpDesktop(tester, locale: const Locale('de'));

    expect(find.text('Яндекс Музыка'), findsWidgets);
    expect(find.text('Настройки'), findsOneWidget);
  });

  testWidgets('theme and locale switch without restart and persist', (tester) async {
    final storage = await pumpDesktop(tester);
    await tester.tap(find.byKey(const Key('nav-settings')));
    await tester.pumpAndSettle();

    await tester.tap(find.text('English'));
    await tester.pumpAndSettle();
    expect(find.text('Settings'), findsWidgets);
    expect(find.text('Yandex Music'), findsWidgets);

    await tester.tap(find.text('Dark'));
    await tester.pumpAndSettle();
    final settingsElement = tester.element(find.byKey(const Key('settings-page')));
    expect(Theme.of(settingsElement).brightness, Brightness.dark);
    expect(storage.value['localeMode'], 'en');
    expect(storage.value['themeMode'], 'dark');
  });

  testWidgets('Help and About stay inside shell with Now Playing bar', (tester) async {
    await pumpDesktop(tester);
    await tester.tap(find.byKey(const Key('nav-settings')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('settings-help')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('help-page')), findsOneWidget);
    expect(find.byType(MusicArkNowPlayingBar), findsOneWidget);
    expect(find.text('Синхронизация'), findsWidgets);

    await tester.tap(find.byKey(const Key('nav-settings')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('settings-about')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('about-page')), findsOneWidget);
    expect(find.text('0.9.1'), findsWidgets);
    expect(find.byType(MusicArkNowPlayingBar), findsOneWidget);
  });
}
