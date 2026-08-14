import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/main.dart';

void main() {
  testWidgets('login persists session UI and search filters liked tracks', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1400, 900));
    await tester.pumpWidget(
      const MusicArkDesktopApp(bridge: FakeMusicArkBridge()),
    );
    await tester.pumpAndSettle();

    expect(find.text('Вход в Яндекс Музыку'), findsOneWidget);
    expect(find.text('Мне нравится'), findsNothing);

    await tester.enterText(find.byType(TextField).first, 'test-token');
    await tester.tap(find.text('Войти'));
    await tester.pumpAndSettle();

    expect(find.text('Мне нравится'), findsOneWidget);
    expect(find.text('Tester'), findsOneWidget);
    expect(find.text('Courtesy Call'), findsOneWidget);
    expect(find.text('Animal I Have Become'), findsOneWidget);

    await tester.enterText(find.byType(TextField).first, 'Animal');
    await tester.pump();
    expect(find.text('Animal I Have Become'), findsOneWidget);
    expect(find.text('Courtesy Call'), findsNothing);

    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('stored session opens library without token and logout clears it', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1400, 900));
    await tester.pumpWidget(
      const MusicArkDesktopApp(
        bridge: FakeMusicArkBridge(startSignedIn: true),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Вход в Яндекс Музыку'), findsNothing);
    expect(find.text('Мне нравится'), findsOneWidget);
    expect(find.text('Courtesy Call'), findsOneWidget);

    await tester.tap(find.text('Выйти'));
    await tester.pumpAndSettle();
    expect(find.text('Вход в Яндекс Музыку'), findsOneWidget);

    await tester.binding.setSurfaceSize(null);
  });
}
