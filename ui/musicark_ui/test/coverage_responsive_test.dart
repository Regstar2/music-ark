import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/coverage_bridge.dart';
import 'package:musicark_ui/coverage_page.dart';
import 'package:musicark_ui/download_bridge.dart';
import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/matching_bridge.dart';

void main() {
  Widget app({
    required CoverageBridgeClient coverage,
    DownloadBridgeClient? downloads,
  }) => MaterialApp(
        locale: const Locale('ru'),
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: CoveragePage(
            bridge: coverage,
            matchingBridge: FakeMatchingBridge(),
            downloadBridge: downloads,
          ),
        ),
      );

  testWidgets('coverage filters stay inside narrow content width', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(315, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final coverage = FakeCoverageBridge()..items.clear();
    await tester.pumpWidget(app(coverage: coverage));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    final collection = find.byKey(const Key('coverage-collection'));
    expect(collection, findsOneWidget);
    expect(tester.getSize(collection).width, lessThanOrEqualTo(267));
  });

  testWidgets('Missing download action stays visible at compact desktop width', (
    tester,
  ) async {
    const surface = Size(760, 900);
    await tester.binding.setSurfaceSize(surface);
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      app(
        coverage: FakeCoverageBridge(),
        downloads: FakeDownloadBridge(),
      ),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    final download = find.byKey(const ValueKey('coverage-download-203'));
    expect(download, findsOneWidget);
    expect(find.text('Скачать'), findsOneWidget);
    final rect = tester.getRect(download);
    expect(rect.left, greaterThanOrEqualTo(0));
    expect(rect.right, lessThanOrEqualTo(surface.width));
  });

  testWidgets('summary and track row avoid overflow at 1024 width', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1024, 768));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(app(coverage: FakeCoverageBridge()));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.byKey(const Key('coverage-summary')), findsOneWidget);
    expect(find.byKey(const ValueKey('coverage-row-203')), findsOneWidget);
  });
}
