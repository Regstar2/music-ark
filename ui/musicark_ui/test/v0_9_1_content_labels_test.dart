import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/app_settings.dart';
import 'package:musicark_ui/content_label_bridge.dart';
import 'package:musicark_ui/main.dart';

class _EnglishSettings implements AppSettingsStorage {
  @override
  Future<Map<String, dynamic>> read() async => {
    'schemaVersion': 1,
    'themeMode': 'light',
    'localeMode': 'en',
  };

  @override
  Future<void> write(Map<String, dynamic> value) async {}
}

class _Labels implements ContentLabelBridgeClient {
  final provider = <String, String>{'101': 'original', '102': 'censored'};

  @override
  Future<Map<String, dynamic>> batch({
    List<int> localFileIds = const [],
    List<String> externalIds = const [],
    String providerId = 'yandex_music',
  }) async => {
    'provider': {
      for (final id in externalIds)
        if (provider[id] != null) id: provider[id],
    },
  };

  @override
  Future<Map<String, dynamic>> setLocal(int localFileId, String label) async =>
      {};

  @override
  Future<Map<String, dynamic>> setProvider(
    String externalId,
    String label, {
    String providerId = 'yandex_music',
  }) async {
    label.isEmpty ? provider.remove(externalId) : provider[externalId] = label;
    return {};
  }
}

class _UnavailableBridge extends FakeMusicArkBridge {
  _UnavailableBridge() : super(startSignedIn: true);

  Map<String, dynamic> _patch(Map<String, dynamic> input) {
    final payload = Map<String, dynamic>.from(input);
    final liked = Map<String, dynamic>.from(payload['liked'] as Map);
    final tracks = (liked['tracks'] as List)
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
    tracks.first['availability'] = 'unavailable';
    liked['tracks'] = tracks;
    payload['liked'] = liked;
    payload['library'] = liked;
    return payload;
  }

  @override
  Future<Map<String, dynamic>> bootstrap() async =>
      _patch(await super.bootstrap());

  @override
  Future<Map<String, dynamic>> libraryRefresh() async =>
      _patch(await super.libraryRefresh());
}

void main() {
  Future<void> pumpShellReady(WidgetTester tester) async {
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pump(const Duration(milliseconds: 250));
  }

  Future<_Labels> pumpApp(
    WidgetTester tester,
    MusicArkBridgeClient bridge,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final labels = _Labels();
    await tester.pumpWidget(
      MusicArkDesktopApp(
        bridge: bridge,
        contentLabelBridge: labels,
        settingsStorage: _EnglishSettings(),
      ),
    );
    await pumpShellReady(tester);
    return labels;
  }

  testWidgets('content labels remain available through the session wrapper', (
    tester,
  ) async {
    final labels = await pumpApp(
      tester,
      FakeMusicArkBridge(startSignedIn: true),
    );
    expect(
      find.byKey(const Key('yandex-inline-content-label-101')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('yandex-inline-content-label-102')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('yandex-content-labels-open')), findsOneWidget);

    tester
        .widget<PopupMenuButton<String>>(
          find.byKey(const Key('yandex-inline-content-label-menu-101')),
        )
        .onSelected
        ?.call('censored');
    await tester.pump(const Duration(milliseconds: 300));
    expect(labels.provider['101'], 'censored');

    tester
        .widget<PopupMenuButton<String>>(
          find.byKey(const Key('yandex-inline-content-label-menu-101')),
        )
        .onSelected
        ?.call('');
    await tester.pump(const Duration(milliseconds: 300));
    expect(labels.provider.containsKey('101'), isFalse);
  });

  testWidgets('availability text is hidden and unavailable play is disabled', (
    tester,
  ) async {
    await pumpApp(tester, _UnavailableBridge());
    expect(find.text('available'), findsNothing);
    expect(find.text('unavailable'), findsNothing);
    final play = tester.widget<IconButton>(
      find.byKey(const Key('yandex-play-101')),
    );
    expect(play.onPressed, isNull);
    final tooltip = find.ancestor(
      of: find.byKey(const Key('yandex-play-101')),
      matching: find.byType(Tooltip),
    );
    expect(tooltip, findsOneWidget);
    expect(
      tester.widget<Tooltip>(tooltip).message,
      'Track is unavailable in Yandex Music',
    );
  });
}
