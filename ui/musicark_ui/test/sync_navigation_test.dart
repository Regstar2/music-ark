import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/musicark_bridge.dart';
import 'package:musicark_ui/sync_bridge.dart';

void main() {
  testWidgets('main navigation opens Controlled Sync', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    final sync = FakeSyncBridge();
    await tester.pumpWidget(
      MusicArkDesktopApp(
        bridge: FakeMusicArkBridge(startSignedIn: true),
        syncBridge: sync,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('nav-sync')), findsOneWidget);
    await tester.tap(find.byKey(const Key('nav-sync')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sync-page')), findsOneWidget);
    expect(find.text('Синхронизация'), findsOneWidget);
    await tester.binding.setSurfaceSize(null);
  });
}
