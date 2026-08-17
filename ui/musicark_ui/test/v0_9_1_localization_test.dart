import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/app_settings.dart';
import 'package:musicark_ui/content_label_bridge.dart';
import 'package:musicark_ui/main.dart';

class _NoLabels implements ContentLabelBridgeClient {
  @override
  Future<Map<String, dynamic>> batch({
    List<int> localFileIds = const [],
    List<String> externalIds = const [],
    String providerId = 'yandex_music',
  }) async => {'provider': <String, String>{}};

  @override
  Future<Map<String, dynamic>> setLocal(int localFileId, String label) async => {};

  @override
  Future<Map<String, dynamic>> setProvider(
    String externalId,
    String label, {
    String providerId = 'yandex_music',
  }) async => {};
}

class _EnglishSettings implements AppSettingsStorage {
  @override
  Future<Map<String, dynamic>> read() async => {
        'schemaVersion': 1,
        'themeMode': 'light',
        'localeMode': 'en',
      };

  @override
  Future<void> write(Map<String, dynamic> value) async {}
}

void main() {
  testWidgets('new Yandex controls use English locale', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MusicArkDesktopApp(
        bridge: FakeMusicArkBridge(startSignedIn: true),
        contentLabelBridge: _NoLabels(),
        settingsStorage: _EnglishSettings(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Tracks'), findsWidgets);
    expect(find.text('Playlists'), findsWidgets);
    expect(find.text('Albums'), findsWidgets);
    expect(find.text('Version labels'), findsOneWidget);
    expect(find.text('Yandex order'), findsOneWidget);
    expect(find.text('available'), findsNothing);
  });
}
