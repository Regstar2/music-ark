import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/main.dart';

void main() {
  testWidgets('login loads liked tracks', (WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(1200, 900));
    await tester.pumpWidget(
      const MusicArkDesktopApp(bridge: FakeMusicArkBridge()),
    );

    expect(find.text('Вход в Яндекс Музыку'), findsOneWidget);
    expect(find.text('Мне нравится'), findsNothing);

    await tester.enterText(find.byType(TextField), 'test-token');
    await tester.tap(find.text('Войти'));
    await tester.pumpAndSettle();

    expect(find.text('Мне нравится'), findsOneWidget);
    expect(find.text('Tester'), findsOneWidget);
    expect(find.text('Courtesy Call'), findsOneWidget);
    expect(find.textContaining('Thousand Foot Krutch'), findsOneWidget);

    await tester.binding.setSurfaceSize(null);
  });
}
