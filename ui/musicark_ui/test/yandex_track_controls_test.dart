import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/content_label_bridge.dart';
import 'package:musicark_ui/yandex_app.dart' as yandex;

class _DelayedPlaybackBridge extends FakeMusicArkBridge {
  _DelayedPlaybackBridge() : super(startSignedIn: true);

  final playback = Completer<Map<String, dynamic>>();

  @override
  Future<Map<String, dynamic>> yandexPlaybackPrepare(String externalId) {
    yandexPlaybackPrepareCalls++;
    return playback.future;
  }
}

void main() {
  Future<void> desktop(
    WidgetTester tester,
    MusicArkBridgeClient bridge,
    ContentLabelBridgeClient labels,
  ) async {
    tester.platformDispatcher.localeTestValue = const Locale('ru');
    addTearDown(tester.platformDispatcher.clearLocaleTestValue);
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      yandex.MusicArkDesktopApp(
        bridge: bridge,
        contentLabelBridge: labels,
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('Yandex rows expose artwork playback and inline content labels', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    final labels = FakeContentLabelBridge()..providerLabels['101'] = 'original';

    await desktop(tester, bridge, labels);

    expect(find.byKey(const Key('yandex-artwork-101')), findsOneWidget);
    expect(find.byKey(const Key('yandex-play-101')), findsOneWidget);
    expect(find.byKey(const Key('yandex-inline-content-label-101')), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const Key('yandex-inline-content-label-101')),
        matching: find.text('ОРИГИНАЛ'),
      ),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const Key('yandex-inline-content-label-menu-101')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('ЦЕНЗУРА').last);
    await tester.pumpAndSettle();

    expect(labels.providerLabels['101'], 'censored');
    expect(
      find.descendant(
        of: find.byKey(const Key('yandex-inline-content-label-101')),
        matching: find.text('ЦЕНЗУРА'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('Yandex playback exposes a non-blocking preparation indicator', (tester) async {
    final bridge = _DelayedPlaybackBridge();
    final labels = FakeContentLabelBridge();

    await desktop(tester, bridge, labels);
    await tester.tap(find.byKey(const Key('yandex-play-101')));
    await tester.pump();

    expect(bridge.yandexPlaybackPrepareCalls, 1);
    expect(
      find.descendant(
        of: find.byKey(const Key('yandex-play-101')),
        matching: find.byType(CircularProgressIndicator),
      ),
      findsOneWidget,
    );
    expect(find.byKey(const Key('yandex-track-102')), findsOneWidget);
  });

  testWidgets('playlist tracks receive the same Yandex controls', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    final labels = FakeContentLabelBridge();

    await desktop(tester, bridge, labels);
    await tester.tap(find.byKey(const Key('nav-playlists')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('playlist-row-501')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('yandex-artwork-201')), findsOneWidget);
    expect(find.byKey(const Key('yandex-play-201')), findsOneWidget);
    expect(find.byKey(const Key('yandex-inline-content-label-menu-201')), findsOneWidget);
  });
}
