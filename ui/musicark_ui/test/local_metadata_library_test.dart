import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/painting.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/local_library_page.dart';
import 'package:musicark_ui/metadata_bridge.dart';
import 'package:musicark_ui/musicark_bridge.dart';

class ArtworkLocalBridge extends FakeMusicArkBridge {
  ArtworkLocalBridge() : super(startSignedIn: true);

  @override
  Future<Map<String, dynamic>> localRoots() async => {
    'items': [
      {'id': 1, 'path': r'C:\Music', 'enabled': true},
    ],
  };

  @override
  Future<Map<String, dynamic>> localTracks({
    int limit = 1000,
    int offset = 0,
    String search = '',
    String sort = 'artist',
    int? rootId,
    List<int>? rootIds,
  }) async {
    if (rootIds != null && rootIds.isEmpty) {
      return {'count': 0, 'limit': limit, 'offset': offset, 'items': []};
    }
    return {
      'count': 2,
      'limit': limit,
      'offset': offset,
      'items': [
        {
          'id': 11,
          'rootId': 1,
          'path': r'C:\Music\Cover.mp3',
          'fileName': 'Cover.mp3',
          'title': 'Cover Track',
          'artists': ['Artist'],
          'album': 'Album',
          'year': 2024,
          'durationSeconds': 180.0,
          'codec': 'mp3',
        },
        {
          'id': 12,
          'rootId': 1,
          'path': r'C:\Music\Placeholder.mp3',
          'fileName': 'Placeholder.mp3',
          'title': 'Placeholder Track',
          'artists': ['Artist'],
          'album': 'Album',
          'year': 2024,
          'durationSeconds': 181.0,
          'codec': 'mp3',
        },
      ],
    };
  }
}

Map<String, dynamic> document(int id, {String? artworkPath}) => {
  'localFileId': id,
  'path': id == 11 ? r'C:\Music\Cover.mp3' : r'C:\Music\Placeholder.mp3',
  'format': 'mp3',
  'writable': true,
  'fields': {
    'title': id == 11 ? 'Cover Track' : 'Placeholder Track',
    'artists': ['Artist'],
    'album': 'Album',
    'albumArtists': ['Artist'],
    'genres': ['Rock'],
  },
  'allTags': <Map<String, dynamic>>[],
  'artwork': {
    'present': artworkPath != null,
    'cachePath': artworkPath,
    'mime': artworkPath == null ? null : 'image/png',
    'width': artworkPath == null ? null : 1,
    'height': artworkPath == null ? null : 1,
  },
  'identity': {'status': 'not_set'},
  'technical': {
    'durationSeconds': 180.0,
    'bitrate': 320000,
    'sampleRate': 44100,
  },
};

void main() {
  testWidgets(
    'Local Library shows cached artwork, placeholder and Edit Metadata action',
    (tester) async {
      late Directory temp;
      late File image;
      await tester.runAsync(() async {
        temp = await Directory.systemTemp.createTemp('musicark-artwork-test-');
        image = File('${temp.path}${Platform.pathSeparator}cover.png');
        await image.writeAsBytes(
          base64Decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABpfZFQAAAAABJRU5ErkJggg==',
          ),
          flush: true,
        );
      });

      final metadata = FakeMetadataBridge(
        documents: {
          11: document(11, artworkPath: image.path),
          12: document(12),
        },
      );
      await tester.binding.setSurfaceSize(const Size(1500, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          locale: const Locale('ru'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: LocalLibraryPage(
            bridge: ArtworkLocalBridge(),
            metadataBridge: metadata,
          ),
        ),
      );
      // FileImage completes on the host event loop. Finite pumps are enough for
      // fake bridge state and avoid waiting indefinitely on image settlement.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(Image), findsOneWidget);
      expect(find.byIcon(Icons.album_outlined), findsOneWidget);
      expect(find.byKey(const Key('local-edit-11')), findsOneWidget);
      expect(find.byKey(const Key('local-edit-12')), findsOneWidget);

      await tester.tap(find.byKey(const Key('local-edit-11')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));
      expect(find.byKey(const Key('metadata-editor-page')), findsOneWidget);
      expect(find.byKey(const Key('metadata-field-title')), findsOneWidget);

      // FileImage may keep a Windows file handle alive after widget removal.
      // Clear the image caches and use best-effort synchronous cleanup.
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
      PaintingBinding.instance.imageCache.clear();
      PaintingBinding.instance.imageCache.clearLiveImages();
      try {
        if (image.existsSync()) image.deleteSync();
        if (temp.existsSync()) temp.deleteSync();
      } on FileSystemException {
        // A transient decoder handle must not change the widget-test result.
      }
    },
  );
}
