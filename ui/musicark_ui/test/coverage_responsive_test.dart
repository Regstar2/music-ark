import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/coverage_bridge.dart';
import 'package:musicark_ui/coverage_page.dart';
import 'package:musicark_ui/matching_bridge.dart';

void main() {
  testWidgets('coverage filters stay inside narrow content width', (tester) async {
    await tester.binding.setSurfaceSize(const Size(315, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final coverage = FakeCoverageBridge()..items.clear();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CoveragePage(
            bridge: coverage,
            matchingBridge: FakeMatchingBridge(),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    final collection = find.byKey(const Key('coverage-collection'));
    expect(collection, findsOneWidget);
    expect(tester.getSize(collection).width, lessThanOrEqualTo(267));
  });
}
