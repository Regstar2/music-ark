import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/local_library_page.dart';
import 'package:musicark_ui/musicark_bridge.dart';
import 'package:musicark_ui/yandex_workspace.dart' as yandex;

Map<String, dynamic> _localTrack(int id, String title) => {
  'id': id,
  'rootId': 1,
  'path': 'C:/Music/$title.mp3',
  'fileName': '$title.mp3',
  'title': title,
  'artists': const ['Artist'],
  'album': 'Album',
  'durationSeconds': 180.0,
  'codec': 'mp3',
};

Map<String, dynamic> _localPage(
  List<Map<String, dynamic>> items, {
  int? count,
  int limit = 250,
  int offset = 0,
}) => {
  'count': count ?? items.length,
  'limit': limit,
  'offset': offset,
  'items': items,
};

class _LargeLocalBridge extends FakeMusicArkBridge {
  _LargeLocalBridge() : super(startSignedIn: true);

  final List<int> requestedLimits = [];

  @override
  Future<Map<String, dynamic>> localTracks({
    int limit = 1000,
    int offset = 0,
    String search = '',
    String sort = 'artist',
    int? rootId,
    List<int>? rootIds,
  }) async {
    requestedLimits.add(limit);
    final available = (10_000 - offset).clamp(0, limit).toInt();
    return {
      'count': 10_000,
      'limit': limit,
      'offset': offset,
      'items': List.generate(
        available,
        (index) {
          final id = offset + index + 1;
          return {
            'id': id,
            'rootId': 1,
            'path': 'C:/Music/track-$id.mp3',
            'fileName': 'track-$id.mp3',
            'title': 'Track $id',
            'artists': ['Artist ${id % 50}'],
            'album': 'Album ${id % 100}',
            'durationSeconds': 180.0,
            'codec': 'mp3',
          };
        },
        growable: false,
      ),
    };
  }
}

class _StaleLocalBridge extends FakeMusicArkBridge {
  _StaleLocalBridge() : super(startSignedIn: true);

  final Completer<Map<String, dynamic>> firstSearch = Completer();
  final Completer<Map<String, dynamic>> secondSearch = Completer();

  @override
  Future<Map<String, dynamic>> localTracks({
    int limit = 1000,
    int offset = 0,
    String search = '',
    String sort = 'artist',
    int? rootId,
    List<int>? rootIds,
  }) {
    if (search == 'first') return firstSearch.future;
    if (search == 'second') return secondSearch.future;
    return Future.value(_localPage([_localTrack(1, 'Initial')], limit: limit));
  }
}

void main() {
  Future<void> pumpLocal(WidgetTester tester, MusicArkBridgeClient bridge) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        locale: const Locale('ru'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: LocalLibraryPage(bridge: bridge),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('Local Library opens cache-first and requests only one 250-row page', (
    tester,
  ) async {
    final bridge = _LargeLocalBridge();
    await bridge.localRootAdd(r'C:\Music');

    await pumpLocal(tester, bridge);

    expect(bridge.localScanCalls, 0);
    expect(bridge.requestedLimits, isNotEmpty);
    expect(bridge.requestedLimits.first, 250);
    expect(find.byKey(const Key('local-library-page')), findsOneWidget);
    expect(find.text('Track 10000'), findsNothing);
  });

  testWidgets('Local Library ignores a slower stale async search result', (
    tester,
  ) async {
    final bridge = _StaleLocalBridge();
    await bridge.localRootAdd(r'C:\Music');
    await pumpLocal(tester, bridge);
    expect(find.text('Initial'), findsOneWidget);

    final search = find.byKey(const Key('local-search'));
    await tester.enterText(search, 'first');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pump();

    await tester.enterText(search, 'second');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pump();

    bridge.secondSearch.complete(_localPage([_localTrack(2, 'Second Result')]));
    await tester.pumpAndSettle();
    expect(find.text('Second Result'), findsOneWidget);

    bridge.firstSearch.complete(_localPage([_localTrack(3, 'First Stale Result')]));
    await tester.pumpAndSettle();
    expect(find.text('Second Result'), findsOneWidget);
    expect(find.text('First Stale Result'), findsNothing);
  });

  testWidgets('Yandex track search is debounced and track list has fixed extent', (
    tester,
  ) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(yandex.MusicArkDesktopApp(bridge: bridge));
    await tester.pumpAndSettle();

    final list = tester.widget<ListView>(find.byKey(const Key('track-list')));
    expect(list.itemExtent, 72);
    expect(find.text('Courtesy Call'), findsOneWidget);
    expect(find.text('Animal I Have Become'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('track-search')), 'Animal');
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('Courtesy Call'), findsOneWidget);

    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('Courtesy Call'), findsNothing);
    expect(find.text('Animal I Have Become'), findsOneWidget);
  });
}
