import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/folder_picker.dart';
import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/local_library_page.dart';
import 'package:musicark_ui/musicark_bridge.dart';
import 'package:musicark_ui/yandex_upload_bridge.dart';

class _NoFolderPicker implements LocalFolderPicker {
  const _NoFolderPicker();

  @override
  Future<String?> pickDirectory() async => null;
}

class _LocalUploadBridge extends FakeMusicArkBridge {
  _LocalUploadBridge() : super(startSignedIn: true);

  @override
  Future<Map<String, dynamic>> localRoots() async => {
    'count': 1,
    'items': [
      {
        'id': 1,
        'path': r'C:\Music',
        'normalizedPath': r'c:\music',
        'enabled': true,
        'createdAt': '2026-08-19T00:00:00Z',
        'lastScannedAt': '2026-08-19T00:00:00Z',
      },
    ],
  };

  @override
  Future<Map<String, dynamic>> localScan({int? rootId}) async => {
    'added': 0,
    'updated': 0,
    'removed': 0,
    'unchanged': 1,
    'errors': 0,
    'scanned': 1,
    'errorItems': <Map<String, dynamic>>[],
  };

  @override
  Future<Map<String, dynamic>> localTracks({
    int limit = 1000,
    int offset = 0,
    String search = '',
    String sort = 'artist',
    int? rootId,
    List<int>? rootIds,
  }) async => {
    'count': 1,
    'limit': limit,
    'offset': offset,
    'items': [
      {
        'id': 77,
        'rootId': 1,
        'path': r'C:\Music\Artist - Track.mp3',
        'fileName': 'Artist - Track.mp3',
        'title': 'Track',
        'artists': ['Artist'],
        'album': 'Album',
        'extension': '.mp3',
        'codec': 'mp3',
        'fileSize': 1024,
        'durationSeconds': 180.0,
      },
    ],
  };
}

void main() {
  testWidgets(
    'Local Library exposes single-track Yandex upload action for MP3',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1400, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final uploadBridge = FakeYandexUploadBridge(
        playlists: const [
          YandexUploadTarget(
            playlistKind: '7',
            title: 'My playlist',
            trackCount: 0,
          ),
        ],
      );
      await tester.pumpWidget(
        MaterialApp(
          locale: const Locale('ru'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: LocalLibraryPage(
            bridge: _LocalUploadBridge(),
            folderPicker: const _NoFolderPicker(),
            yandexUploadBridge: uploadBridge,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('local-upload-yandex-77')), findsOneWidget);
      expect(find.byTooltip('Загрузить в Яндекс Музыку'), findsOneWidget);

      await tester.tap(find.byKey(const Key('local-upload-yandex-77')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('yandex-upload-dialog')), findsOneWidget);
      expect(find.textContaining('Artist - Track.mp3'), findsOneWidget);
    },
  );
}
