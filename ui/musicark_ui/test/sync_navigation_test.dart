import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/musicark_bridge.dart';
import 'package:musicark_ui/sync_bridge.dart';

void main() {
  Future<void> pumpShellReady(WidgetTester tester) async {
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pump(const Duration(milliseconds: 250));
  }

  testWidgets('main navigation opens Controlled Sync', (tester) async {
    tester.platformDispatcher.localeTestValue = const Locale('ru');
    addTearDown(tester.platformDispatcher.clearLocaleTestValue);
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final sync = FakeSyncBridge();
    await tester.pumpWidget(
      MusicArkDesktopApp(
        bridge: FakeMusicArkBridge(startSignedIn: true),
        syncBridge: sync,
      ),
    );
    await pumpShellReady(tester);

    expect(find.byKey(const Key('nav-sync')), findsOneWidget);
    await tester.tap(find.byKey(const Key('nav-sync')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 250));
    expect(find.byKey(const Key('sync-page')), findsOneWidget);
    expect(find.text('Синхронизация'), findsWidgets);
  });
}
