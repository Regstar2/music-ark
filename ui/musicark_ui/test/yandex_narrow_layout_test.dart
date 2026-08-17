import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/musicark_bridge.dart';

void main() {
  testWidgets('Yandex section keeps a safe desktop workspace on narrow windows', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(700, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MusicArkDesktopApp(
        bridge: FakeMusicArkBridge(startSignedIn: true),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('yandex-horizontal-viewport')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('library-sidebar')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
