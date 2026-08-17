import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

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

void main() {
  testWidgets('Yandex workspace resizes without layout exceptions', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1920, 1080));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MusicArkDesktopApp(
        bridge: FakeMusicArkBridge(startSignedIn: true),
        contentLabelBridge: _NoLabels(),
      ),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);

    for (final size in const [
      Size(1600, 900),
      Size(1366, 768),
      Size(900, 700),
    ]) {
      await tester.binding.setSurfaceSize(size);
      await tester.pumpAndSettle();
      expect(
        tester.takeException(),
        isNull,
        reason: 'layout exception at $size',
      );
    }
  });
}
