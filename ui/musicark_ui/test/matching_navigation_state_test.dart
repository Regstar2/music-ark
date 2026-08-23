import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/matching_bridge.dart';
import 'package:musicark_ui/matching_progress_bridge.dart';
import 'package:musicark_ui/musicark_bridge.dart';

class BlockingMatchingBridge extends FakeMatchingBridge
    implements MatchingProgressSource {
  final ValueNotifier<MatchingRunProgress> progress =
      ValueNotifier<MatchingRunProgress>(const MatchingRunProgress.idle());
  final Completer<Map<String, dynamic>> _runCompleter = Completer();

  @override
  ValueListenable<MatchingRunProgress> get matchingProgress => progress;

  @override
  Future<Map<String, dynamic>> matchingRun() {
    runCalls++;
    progress.value = const MatchingRunProgress(
      running: true,
      processed: 25,
      total: 100,
    );
    return _runCompleter.future;
  }

  void finish() {
    if (_runCompleter.isCompleted) return;
    progress.value = const MatchingRunProgress(
      running: false,
      processed: 100,
      total: 100,
    );
    _runCompleter.complete({
      'total': 3,
      'matched': 1,
      'conflicts': 1,
      'unmatched': 1,
      'unchanged': 0,
      'invalidated': 0,
      'indexUpdates': 0,
      'comparisons': 5,
      'durationSeconds': 0.01,
      'matcherVersion': 1,
      'summary': <String, dynamic>{},
    });
  }
}

void main() {
  testWidgets('in-flight matching survives navigation away and back', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 950));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final yandex = FakeMusicArkBridge(startSignedIn: true);
    final matching = BlockingMatchingBridge();
    addTearDown(matching.progress.dispose);

    await tester.pumpWidget(
      MusicArkDesktopApp(bridge: yandex, matchingBridge: matching),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    await tester.tap(find.byKey(const Key('nav-matching')));
    await tester.pump(const Duration(milliseconds: 150));
    await tester.tap(find.byKey(const Key('matching-run')));
    await tester.pump(const Duration(milliseconds: 50));

    expect(matching.runCalls, 1);
    expect(find.byKey(const Key('matching-global-progress')), findsOneWidget);
    expect(find.text('25 / 100'), findsOneWidget);

    await tester.tap(find.byKey(const Key('nav-local-library')));
    await tester.pump(const Duration(milliseconds: 150));
    await tester.tap(find.byKey(const Key('nav-matching')));
    await tester.pump(const Duration(milliseconds: 100));

    expect(matching.runCalls, 1);
    expect(find.byKey(const Key('matching-page')), findsOneWidget);
    final button = tester.widget<FilledButton>(
      find.byKey(const Key('matching-run')),
    );
    expect(button.onPressed, isNull);
    expect(find.byKey(const Key('matching-global-progress')), findsOneWidget);

    matching.finish();
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.byKey(const Key('matching-global-progress')), findsNothing);
  });
}
