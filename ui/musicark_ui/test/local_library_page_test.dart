import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/desktop_file_actions.dart';
import 'package:musicark_ui/folder_picker.dart';
import 'package:musicark_ui/l10n/app_localizations.dart';
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
    List<int>? rootIds,
  }) async {
    final base = await super.localTracks(
      limit: limit,
      offset: offset,
      search: '',
      sort: sort,
      rootId: rootId,
      rootIds: rootIds,
    );
    if ((base['count'] as int? ?? 0) == 0) return base;
    var items = <Map<String, dynamic>>[
      {
        'id': 11,
        'rootId': 1,
        'path': r'C:\Music\Zulu.flac',
        'fileName': 'Zulu.flac',
        'title': 'Zulu',
        'artists': ['Alpha Artist'],
        'album': 'First',
        'durationSeconds': 100.0,
        'codec': 'flac',
      },
      {
        'id': 12,
        'rootId': 1,
        'path': r'C:\Music\Alpha.mp3',
        'fileName': 'Alpha.mp3',
        'title': 'Alpha',
        'artists': ['Zulu Artist'],
        'album': 'Second',
        'durationSeconds': 200.0,
        'codec': 'mp3',
      },
    ];
    final query = search.toLowerCase();
    if (query.isNotEmpty) {
      items = items
          .where(
            (item) =>
                '${item['title']} ${item['artists']} ${item['album']} ${item['fileName']}'
                    .toLowerCase()
                    .contains(query),
          )
          .toList();
    }
    if (sort == 'title') {
      items.sort((a, b) => '${a['title']}'.compareTo('${b['title']}'));
    } else if (sort == 'artist') {
      items.sort((a, b) => '${a['artists']}'.compareTo('${b['artists']}'));
    }
    return {
      'count': items.length,
      'limit': limit,
      'offset': offset,
      'items': items.skip(offset).take(limit).toList(),
    };
  }
}

class MultiRootLocalBridge extends FakeMusicArkBridge {
  MultiRootLocalBridge({int largeRootTrackCount = 1})
    : _largeRootTrackCount = largeRootTrackCount,
      super(startSignedIn: true) {
    _roots.addAll([
      _root(1, r'C:\Music\One'),
      _root(2, r'D:\Music\Two'),
      _root(3, r'E:\Archive\Three'),
    ]);
  }

  final int _largeRootTrackCount;
  final List<Map<String, dynamic>> _roots = [];
  final List<List<int>?> rootIdQueries = [];

  static Map<String, dynamic> _root(int id, String path) => {
    'id': id,
    'path': path,
    'normalizedPath': path.toLowerCase(),
    'enabled': true,
    'createdAt': '2026-08-17T00:00:00Z',
    'lastScannedAt': '2026-08-17T18:00:00Z',
  };

  List<Map<String, dynamic>> get _tracks {
    final rootOne = List.generate(
      _largeRootTrackCount,
      (index) => {
        'id': 1000 + index,
        'rootId': 1,
        'path': r'C:\Music\One\track-$index.mp3',
        'fileName': 'track-$index.mp3',
        'title': index == 0 ? 'One Track' : 'One Track $index',
        'artists': ['Shared Artist'],
        'album': 'Root One',
        'year': 2020,
        'durationSeconds': 180.0 + index,
        'codec': 'mp3',
      },
    );
    return [
      ...rootOne,
      {
        'id': 2001,
        'rootId': 2,
        'path': r'D:\Music\Two\two.mp3',
        'fileName': 'two.mp3',
        'title': 'Two Track',
        'artists': ['Shared Artist'],
        'album': 'Root Two',
        'year': 2021,
        'durationSeconds': 200.0,
        'codec': 'mp3',
      },
      {
        'id': 3001,
        'rootId': 3,
        'path': r'E:\Archive\Three\three.flac',
        'fileName': 'three.flac',
        'title': 'Three Track',
        'artists': ['Other Artist'],
        'album': 'Root Three',
        'year': 2022,
        'durationSeconds': 220.0,
        'codec': 'flac',
      },
    ];
  }

  @override
  Future<Map<String, dynamic>> localRoots() async => {
    'count': _roots.length,
    'items': _roots.map(Map<String, dynamic>.from).toList(),
  };

  @override
  Future<Map<String, dynamic>> localRootAdd(String path) async {
    final nextId = _roots.isEmpty
        ? 1
        : _roots.map((root) => root['id'] as int).reduce((a, b) => a > b ? a : b) + 1;
    final root = _root(nextId, path);
    _roots.add(root);
    return {'root': root, 'roots': await localRoots()};
  }

  @override
  Future<Map<String, dynamic>> localRootRemove(int rootId) async {
    _roots.removeWhere((root) => root['id'] == rootId);
    return {'removed': true, 'roots': await localRoots()};
  }

  @override
  Future<Map<String, dynamic>> localScan({int? rootId}) async {
    localScanCalls++;
    return {
      'added': 0,
      'updated': 0,
      'removed': 0,
      'unchanged': _tracks.length,
      'errors': 0,
      'scanned': _tracks.length,
      'errorItems': <Map<String, dynamic>>[],
    };
  }

  @override
  Future<Map<String, dynamic>> localTracks({
    int limit = 1000,
    int offset = 0,
    String search = '',
    String sort = 'artist',
    int? rootId,
    List<int>? rootIds,
  }) async {
    if (rootId != null && rootIds != null) {
      throw ArgumentError('rootId and rootIds cannot both be supplied.');
    }
    rootIdQueries.add(rootIds == null ? null : List<int>.from(rootIds));
    var items = _tracks;
    if (rootIds != null) {
      final selected = rootIds.toSet();
      items = items.where((item) => selected.contains(item['rootId'])).toList();
    } else if (rootId != null) {
      items = items.where((item) => item['rootId'] == rootId).toList();
    }
    final query = search.trim().toLowerCase();
    if (query.isNotEmpty) {
      items = items
          .where(
            (item) =>
                '${item['title']} ${item['artists']} ${item['album']} ${item['fileName']}'
                    .toLowerCase()
                    .contains(query),
          )
          .toList();
    }
    if (sort == 'title') {
      items.sort((a, b) => '${a['title']}'.compareTo('${b['title']}'));
    } else if (sort == 'album') {
      items.sort((a, b) => '${a['album']}'.compareTo('${b['album']}'));
    }
    final count = items.length;
    return {
      'count': count,
      'limit': limit,
      'offset': offset,
      'items': items.skip(offset).take(limit).toList(),
    };
  }
}

class QueueFolderPicker implements LocalFolderPicker {
  QueueFolderPicker(Iterable<String?> paths) : _paths = List.of(paths);
  final List<String?> _paths;

  @override
  Future<String?> pickDirectory() async => _paths.isEmpty ? null : _paths.removeAt(0);
}

class FakeLocalFileActions implements LocalFileActions {
  final List<String> played = [];
  final List<String> revealed = [];

  @override
  Future<void> play(String path) async => played.add(path);

  @override
  Future<void> reveal(String path) async => revealed.add(path);
}

void main() {
  Future<void> desktop(WidgetTester tester, Widget widget) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    await tester.pumpWidget(
      MaterialApp(
        locale: const Locale('ru'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: widget,
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> applyRootSelection(
    WidgetTester tester,
    Iterable<int> selectedIds,
  ) async {
    final selected = selectedIds.toSet();
    await tester.tap(find.byKey(const Key('local-folder-filter')));
    await tester.pumpAndSettle();
    for (final id in [1, 2, 3]) {
      final checkbox = tester.widget<CheckboxListTile>(
        find.byKey(Key('local-filter-root-$id')),
      );
      final wanted = selected.contains(id);
      if (checkbox.value != wanted) {
        await tester.tap(find.byKey(Key('local-filter-root-$id')));
        await tester.pump();
      }
    }
    await tester.tap(find.byKey(const Key('local-filter-apply')));
    await tester.pumpAndSettle();
  }

  tearDown(() async {
    await TestWidgetsFlutterBinding.ensureInitialized().setSurfaceSize(null);
  });

  testWidgets('main navigation opens Local Library independently of Yandex', (
    tester,
  ) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    await tester.pumpWidget(MusicArkDesktopApp(bridge: bridge));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('nav-local-library')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('local-library-page')), findsOneWidget);
    expect(find.byKey(const Key('local-empty')), findsOneWidget);
  });

  testWidgets('empty state can add root, scan, show tracks and compact result', (
    tester,
  ) async {
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
    expect(bridge.localScanCalls, greaterThanOrEqualTo(1));
    expect(find.textContaining('Добавлено 2'), findsOneWidget);
    expect(find.byKey(const Key('local-track-list')), findsOneWidget);
    expect(find.text('Zulu'), findsOneWidget);
    expect(find.text('Alpha'), findsOneWidget);
  });

  testWidgets('local search and sorting use the bridge query contract', (
    tester,
  ) async {
    final bridge = SortingLocalBridge();
    await bridge.localRootAdd(r'C:\Music');
    await desktop(
      tester,
      LocalLibraryPage(
        bridge: bridge,
        folderPicker: FakeLocalFolderPicker(null),
      ),
    );

    expect(
      tester.getTopLeft(find.text('Zulu')).dy,
      lessThan(tester.getTopLeft(find.text('Alpha')).dy),
    );

    await tester.tap(find.byKey(const Key('local-sort')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Название').last);
    await tester.pumpAndSettle();
    expect(
      tester.getTopLeft(find.text('Alpha')).dy,
      lessThan(tester.getTopLeft(find.text('Zulu')).dy),
    );

    await tester.enterText(find.byKey(const Key('local-search')), 'Zulu Artist');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    expect(find.text('Alpha'), findsOneWidget);
    expect(find.text('Zulu'), findsNothing);
  });

  testWidgets('track can be played and revealed from compact actions', (
    tester,
  ) async {
    final bridge = SortingLocalBridge();
    final actions = FakeLocalFileActions();
    await bridge.localRootAdd(r'C:\Music');
    await desktop(
      tester,
      LocalLibraryPage(
        bridge: bridge,
        folderPicker: FakeLocalFolderPicker(null),
        fileActions: actions,
      ),
    );

    const path = r'C:\Music\Zulu.flac';
    expect(find.text(path), findsNothing);
    await tester.tap(find.byKey(const Key('local-play-11')));
    await tester.tap(find.byKey(const Key('local-track-menu-11')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('local-reveal-11')));
    await tester.pump();
    expect(actions.played, [path]);
    expect(actions.revealed, [path]);

    await tester.tap(find.text('Zulu'));
    await tester.pumpAndSettle();
    expect(find.text(path), findsNothing);
    await tester.tap(find.byKey(const Key('local-detail-path-11')));
    await tester.pumpAndSettle();
    expect(find.text(path), findsOneWidget);
  });

  testWidgets('removing a root requires explicit index-only confirmation', (
    tester,
  ) async {
    final bridge = SortingLocalBridge();
    await bridge.localRootAdd(r'C:\Music');
    await desktop(
      tester,
      LocalLibraryPage(
        bridge: bridge,
        folderPicker: FakeLocalFolderPicker(null),
      ),
    );
    await tester.tap(find.byKey(const Key('local-root-menu-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('local-remove-root-1')));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Музыкальные файлы на диске не изменяются и не удаляются.'),
      findsOneWidget,
    );
    await tester.tap(find.text('Убрать из MusicArk').last);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('local-empty')), findsOneWidget);
  });

  testWidgets('all roots are selected by default and arbitrary subset is queried', (
    tester,
  ) async {
    final bridge = MultiRootLocalBridge();
    await desktop(tester, LocalLibraryPage(bridge: bridge));

    expect(find.text('One Track'), findsOneWidget);
    expect(find.text('Two Track'), findsOneWidget);
    expect(find.text('Three Track'), findsOneWidget);
    expect(bridge.rootIdQueries.last, isNull);

    await applyRootSelection(tester, [1, 3]);
    expect(find.text('One Track'), findsOneWidget);
    expect(find.text('Two Track'), findsNothing);
    expect(find.text('Three Track'), findsOneWidget);
    expect(bridge.rootIdQueries.last, [1, 3]);
    expect(find.text('2 из 3 папок'), findsOneWidget);
  });

  testWidgets('single root and empty selection have distinct view states', (
    tester,
  ) async {
    final bridge = MultiRootLocalBridge();
    await desktop(tester, LocalLibraryPage(bridge: bridge));

    await applyRootSelection(tester, [2]);
    expect(find.text('One Track'), findsNothing);
    expect(find.text('Two Track'), findsOneWidget);
    expect(find.text('Three Track'), findsNothing);
    expect(bridge.rootIdQueries.last, [2]);

    await applyRootSelection(tester, []);
    expect(find.byKey(const Key('local-no-folders-selected')), findsOneWidget);
    expect(bridge.rootIdQueries.last, <int>[]);
  });

  testWidgets('master checkbox restores all folders from empty selection', (
    tester,
  ) async {
    final bridge = MultiRootLocalBridge();
    await desktop(tester, LocalLibraryPage(bridge: bridge));
    await applyRootSelection(tester, []);

    await tester.tap(find.byKey(const Key('local-folder-filter')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('local-filter-all')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('local-filter-apply')));
    await tester.pumpAndSettle();

    expect(find.text('One Track'), findsOneWidget);
    expect(find.text('Two Track'), findsOneWidget);
    expect(find.text('Three Track'), findsOneWidget);
    expect(bridge.rootIdQueries.last, isNull);
  });

  testWidgets('search and sort preserve the selected root subset', (tester) async {
    final bridge = MultiRootLocalBridge();
    await desktop(tester, LocalLibraryPage(bridge: bridge));
    await applyRootSelection(tester, [1, 3]);

    await tester.enterText(find.byKey(const Key('local-search')), 'Other Artist');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    expect(bridge.rootIdQueries.last, [1, 3]);
    expect(find.text('Three Track'), findsOneWidget);

    await tester.tap(find.byKey(const Key('local-sort')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Альбом').last);
    await tester.pumpAndSettle();
    expect(bridge.rootIdQueries.last, [1, 3]);
  });

  testWidgets('load more keeps the same selected root subset', (tester) async {
    final bridge = MultiRootLocalBridge(largeRootTrackCount: 501);
    await desktop(tester, LocalLibraryPage(bridge: bridge));
    await applyRootSelection(tester, [1]);

    expect(find.byKey(const Key('local-load-more')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('local-load-more')));
    await tester.tap(find.byKey(const Key('local-load-more')));
    await tester.pumpAndSettle();
    expect(bridge.rootIdQueries.last, [1]);
    expect(find.text('One Track 500'), findsOneWidget);
  });

  testWidgets('removing a selected root drops its stale id from the subset', (
    tester,
  ) async {
    final bridge = MultiRootLocalBridge();
    await desktop(tester, LocalLibraryPage(bridge: bridge));
    await applyRootSelection(tester, [1, 3]);

    await tester.tap(find.byKey(const Key('local-root-menu-3')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('local-remove-root-3')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Убрать из MusicArk').last);
    await tester.pumpAndSettle();

    expect(bridge.rootIdQueries.last, [1]);
    expect(find.text('One Track'), findsOneWidget);
    expect(find.text('Three Track'), findsNothing);
    expect(find.text('1 из 2 папок'), findsOneWidget);
  });

  testWidgets('new root joins selection only when the previous state was all', (
    tester,
  ) async {
    final allBridge = MultiRootLocalBridge();
    await desktop(
      tester,
      LocalLibraryPage(
        bridge: allBridge,
        folderPicker: QueueFolderPicker([r'F:\New All']),
      ),
    );
    await tester.tap(find.byKey(const Key('local-add-folder')));
    await tester.pumpAndSettle();
    expect(allBridge.rootIdQueries.last, isNull);
    expect(find.textContaining('4 папок'), findsOneWidget);

    final subsetBridge = MultiRootLocalBridge();
    await desktop(
      tester,
      LocalLibraryPage(
        bridge: subsetBridge,
        folderPicker: QueueFolderPicker([r'G:\New Subset']),
      ),
    );
    await applyRootSelection(tester, [1]);
    await tester.tap(find.byKey(const Key('local-add-folder')));
    await tester.pumpAndSettle();
    expect(subsetBridge.rootIdQueries.last, [1]);
    expect(find.text('1 из 4 папок'), findsOneWidget);
  });
}
