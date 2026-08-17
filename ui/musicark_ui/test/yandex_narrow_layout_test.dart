import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/musicark_bridge.dart';

void main() {
  testWidgets('Yandex section remains usable on a narrow desktop window', (
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

    expect(find.byKey(const Key('musicark-primary-sidebar')), findsOneWidget);
    expect(find.byKey(const Key('library-sidebar')), findsNothing);
    expect(find.byKey(const Key('yandex-primary-tabs')), findsOneWidget);
    expect(find.byKey(const Key('nav-liked')), findsOneWidget);
    expect(find.byKey(const Key('nav-playlists')), findsOneWidget);
    expect(find.byKey(const Key('nav-albums')), findsOneWidget);
    expect(find.byKey(const Key('track-list')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
