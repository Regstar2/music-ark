// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/main.dart';

void main() {
  testWidgets('desktop app renders dashboard shell', (WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1200));
    await tester.pumpWidget(
      const MusicArkDesktopApp(bridge: FakeMusicArkBridge()),
    );
    await tester.pumpAndSettle();

    expect(find.text('MusicArk Desktop v0.9'), findsOneWidget);
    expect(find.text('Dashboard'), findsAtLeastNWidgets(1));
    expect(find.text('Run Yandex Scan'), findsOneWidget);
    await tester.binding.setSurfaceSize(null);
  });
}
