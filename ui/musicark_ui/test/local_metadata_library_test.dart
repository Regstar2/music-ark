import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/painting.dart';
import 'package:flutter_test/flutter_test.dart';

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
  }) async => {
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
      'technical': {'durationSeconds': 180.0, 'bitrate': 320000, 'sampleRate': 44100},
    };

void main() {
  testWidgets('Local Library shows cached artwork, placeholder and Edit Metadata action', (tester) async {
    final temp = await Directory.systemTemp.createTemp('musicark-artwork-test-');
    final image = File('${temp.path}${Platform.pathSeparator}cover.png');
    await image.writeAsBytes(base64Decode(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABpfZFQAAAAABJRU5ErkJggg==',
    ));

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
        home: LocalLibraryPage(
          bridge: ArtworkLocalBridge(),
          metadataBridge: metadata,
        ),
      ),
    );
    // FileImage completes on the host event loop. Finite pumps are enough for the
    // fake bridge state and avoid waiting indefinitely on image-cache settlement.
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

    // FileImage may keep a Windows file handle alive after the widget is removed.
    // Cleanup must therefore never await recursive filesystem deletion: doing so
    // can stall the entire widget test for minutes. Clear Flutter's image caches,
    // then perform best-effort synchronous cleanup and tolerate a transient lock.
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    PaintingBinding.instance.imageCache.clear();
    PaintingBinding.instance.imageCache.clearLiveImages();
    try {
      if (image.existsSync()) image.deleteSync();
      if (temp.existsSync()) temp.deleteSync();
    } on FileSystemException {
      // The OS temp directory can retain this tiny fixture until the decoder
      // releases its handle; cleanup must not affect the test result.
    }
  });
}
