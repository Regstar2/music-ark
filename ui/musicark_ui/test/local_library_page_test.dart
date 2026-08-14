import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/folder_picker.dart';
import 'package:musicark_ui/local_library_page.dart';
import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/musicark_bridge.dart';

class SortingLocalBridge extends FakeMusicArkBridge {
  SortingLocalBridge() : super(startSignedIn: true);

  @override
  Future<Map<String, dynamic>> localTracks({
    int limit = 1000,
    int offset = 0,
    String search = '',
    String sort = 'artist',
    int? rootId,
  }) async {
    final base = await super.localTracks(limit: limit, offset: offset, search: '', sort: sort, rootId: rootId);
    if ((base['count'] as int? ?? 0) == 0) return base;
    var items = <Map<String, dynamic>>[
      {'id': 11, 'rootId': 1, 'path': r'C:\Music\Zulu.flac', 'fileName': 'Zulu.flac', 'title': 'Zulu', 'artists': ['Alpha Artist'], 'album': 'First', 'durationSeconds': 100.0, 'codec': 'flac'},
      {'id': 12, 'rootId': 1, 'path': r'C:\Music\Alpha.mp3', 'fileName': 'Alpha.mp3', 'title': 'Alpha', 'artists': ['Zulu Artist'], 'album': 'Second', 'durationSeconds': 200.0, 'codec': 'mp3'},
    ];
    final query = search.toLowerCase();
    if (query.isNotEmpty) {
      items = items.where((item) => '${item['title']} ${item['artists']} ${item['album']} ${item['fileName']}'.toLowerCase().contains(query)).toList();
    }
    if (sort == 'title') {
      items.sort((a, b) => '${a['title']}'.compareTo('${b['title']}'));
    } else if (sort == 'artist') {
      items.sort((a, b) => '${a['artists']}'.compareTo('${b['artists']}'));
    }
    return {'count': items.length, 'limit': limit, 'offset': offset, 'items': items};
  }
}

void main() {
  Future<void> desktop(WidgetTester tester, Widget widget) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    await tester.pumpWidget(MaterialApp(home: widget));
    await tester.pumpAndSettle();
  }

  tearDown(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
  });

  testWidgets('main navigation opens Local Library independently of Yandex', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    await tester.pumpWidget(MusicArkDesktopApp(bridge: bridge));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('nav-local-library')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('local-library-page')), findsOneWidget);
    expect(find.byKey(const Key('local-empty')), findsOneWidget);
    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('empty state can add root, scan, show tracks and result', (tester) async {
    final bridge = SortingLocalBridge();
    await desktop(
      tester,
      LocalLibraryPage(
        bridge: bridge,
        folderPicker: FakeLocalFolderPicker(r'C:\Music'),
      ),
    );
    expect(find.byKey(const Key('local-empty')), findsOneWidget);

    await tester.tap(find.byKey(const Key('local-add-folder')));
    await tester.pumpAndSettle();
    expect(find.text(r'C:\Music'), findsOneWidget);
    expect(find.byKey(const Key('local-roots')), findsOneWidget);

    await tester.tap(find.byKey(const Key('local-scan-all')));
    await tester.pumpAndSettle();
    expect(bridge.localScanCalls, 1);
    expect(find.textContaining('добавлено: 2'), findsOneWidget);
    expect(find.byKey(const Key('local-track-list')), findsOneWidget);
    expect(find.text('Zulu'), findsOneWidget);
    expect(find.text('Alpha'), findsOneWidget);
    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('local search and sorting use the bridge query contract', (tester) async {
    final bridge = SortingLocalBridge();
    await bridge.localRootAdd(r'C:\Music');
    await desktop(tester, LocalLibraryPage(bridge: bridge, folderPicker: FakeLocalFolderPicker(null)));

    expect(tester.getTopLeft(find.text('Zulu')).dy, lessThan(tester.getTopLeft(find.text('Alpha')).dy));

    await tester.tap(find.byKey(const Key('local-sort')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Название').last);
    await tester.pumpAndSettle();
    expect(tester.getTopLeft(find.text('Alpha')).dy, lessThan(tester.getTopLeft(find.text('Zulu')).dy));

    await tester.enterText(find.byKey(const Key('local-search')), 'Zulu Artist');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    expect(find.text('Alpha'), findsOneWidget);
    expect(find.text('Zulu'), findsNothing);
    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('removing a root requires explicit index-only confirmation', (tester) async {
    final bridge = SortingLocalBridge();
    await bridge.localRootAdd(r'C:\Music');
    await desktop(tester, LocalLibraryPage(bridge: bridge, folderPicker: FakeLocalFolderPicker(null)));
    await tester.tap(find.byKey(const Key('local-remove-root-1')));
    await tester.pumpAndSettle();
    expect(find.textContaining('Музыкальные файлы на диске не изменяются и не удаляются.'), findsOneWidget);
    await tester.tap(find.text('Убрать'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('local-empty')), findsOneWidget);
    await tester.binding.setSurfaceSize(null);
  });
}
