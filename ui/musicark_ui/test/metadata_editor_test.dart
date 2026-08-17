import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/metadata_bridge.dart';
import 'package:musicark_ui/metadata_editor_page.dart';

Map<String, dynamic> localDocument() => {
      'localFileId': 2,
      'path': r'C:\Music\Призраков Не Существует.mp3',
      'fileName': 'Призраков Не Существует.mp3',
      'format': 'mp3',
      'writable': true,
      'fields': {
        'title': 'Призраков Не Существует',
        'artists': ['drivemusic.me', 'Second Artist'],
        'album': '',
        'albumArtists': <String>[],
        'trackNumber': null,
        'totalTracks': null,
        'discNumber': null,
        'totalDiscs': null,
        'releaseDate': null,
        'year': null,
        'genres': <String>[],
        'isrc': null,
        'publisher': null,
        'copyright': null,
        'explicit': null,
      },
      'allTags': [
        {
          'key': 'TIT2',
          'frameId': 'TIT2',
          'description': null,
          'values': ['Призраков Не Существует'],
          'editable': true,
          'provenance': false,
        },
        {
          'key': 'TXXX:UNKNOWN_VENDOR_TAG',
          'frameId': 'TXXX',
          'description': 'UNKNOWN_VENDOR_TAG',
          'values': ['keep-me'],
          'editable': true,
          'provenance': false,
        },
      ],
      'artwork': {'present': false, 'cachePath': null, 'width': null, 'height': null},
      'identity': {'status': 'not_set'},
      'technical': {'durationSeconds': 178.0, 'bitrate': 320000, 'sampleRate': 44100},
    };

Map<String, dynamic> yandexTrack() => {
      'fields': {
        'title': 'ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ',
        'artists': ['ЯМАУГЛИ'],
        'album': 'Album',
        'albumArtists': ['ЯМАУГЛИ'],
        'year': 2024,
        'isrc': 'RUA012345678',
      },
      'identity': {'providerId': 'yandex_music', 'externalId': '123456', 'trackId': '123456'},
      'artwork': {'present': false, 'cachePath': null},
      'similarity': .65,
    };

void main() {
  Future<FakeMetadataBridge> openEditor(WidgetTester tester) async {
    final bridge = FakeMetadataBridge(
      documents: {2: localDocument()},
      searchItems: [yandexTrack()],
    );
    await tester.binding.setSurfaceSize(const Size(1500, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(MaterialApp(home: MetadataEditorPage(localFileId: 2, bridge: bridge)));
    await tester.pumpAndSettle();
    return bridge;
  }

  Future<void> reveal(WidgetTester tester, Key key) async {
    await tester.ensureVisible(find.byKey(key));
    await tester.pump();
  }

  testWidgets('shows artwork placeholder, basic fields, multiple artists and advanced tags', (tester) async {
    await openEditor(tester);
    expect(find.byKey(const Key('metadata-editor-page')), findsOneWidget);
    expect(find.byKey(const Key('metadata-field-fileName')), findsOneWidget);
    expect(find.byKey(const Key('metadata-field-title')), findsOneWidget);
    expect(find.text('drivemusic.me'), findsOneWidget);
    expect(find.text('Second Artist'), findsOneWidget);
    expect(find.byKey(const Key('metadata-remove-artwork')), findsOneWidget);
    expect(find.byKey(const Key('metadata-yandex-search')), findsOneWidget);

    await reveal(tester, const Key('metadata-all-tags'));
    await tester.tap(find.byKey(const Key('metadata-all-tags')));
    await tester.pumpAndSettle();
    expect(find.text('TXXX:UNKNOWN_VENDOR_TAG'), findsOneWidget);
    expect(find.byKey(const Key('metadata-add-custom-tag')), findsOneWidget);
  });

  testWidgets('ordinary Save uses metadata update and does not bind identity', (tester) async {
    final bridge = await openEditor(tester);
    await tester.enterText(find.byKey(const Key('metadata-field-title')), 'Исправленное название');
    await reveal(tester, const Key('metadata-save'));
    await tester.tap(find.byKey(const Key('metadata-save')));
    await tester.pumpAndSettle();
    expect(bridge.updates, hasLength(1));
    expect((bridge.updates.single['changes'] as Map)['title'], 'Исправленное название');
    expect(bridge.applies, isEmpty);
    expect(find.byKey(const Key('metadata-success')), findsOneWidget);
  });

  testWidgets('Yandex search opens compare and Apply Metadata stays non-exact', (tester) async {
    final bridge = await openEditor(tester);
    await reveal(tester, const Key('metadata-yandex-search'));
    await tester.tap(find.byKey(const Key('metadata-yandex-search')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('yandex-search-dialog')), findsOneWidget);
    expect(find.byKey(const Key('yandex-search-title')), findsOneWidget);
    expect(find.byKey(const Key('yandex-search-artist')), findsOneWidget);
    expect(find.byKey(const Key('yandex-result-123456')), findsOneWidget);
    await tester.enterText(find.byKey(const Key('yandex-search-title')), 'Нужное название');
    await tester.enterText(find.byKey(const Key('yandex-search-artist')), 'Нужный автор');
    await tester.tap(find.byKey(const Key('yandex-search-run')));
    await tester.pumpAndSettle();
    expect(bridge.searches.last['title'], 'Нужное название');
    expect(bridge.searches.last['artist'], 'Нужный автор');

    await tester.tap(find.byKey(const Key('yandex-result-123456')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('metadata-compare-dialog')), findsOneWidget);
    expect(find.byKey(const Key('compare-select-all')), findsOneWidget);
    expect(find.byKey(const Key('compare-select-none')), findsOneWidget);
    expect(find.byKey(const Key('compare-apply-metadata')), findsOneWidget);
    expect(find.byKey(const Key('compare-apply-bind')), findsOneWidget);
    expect(find.byKey(const Key('compare-field-fileName')), findsOneWidget);

    await tester.tap(find.byKey(const Key('compare-select-none')));
    await tester.tap(find.byKey(const Key('compare-select-all')));
    await tester.tap(find.byKey(const Key('compare-apply-metadata')));
    await tester.pumpAndSettle();
    expect(bridge.applies, hasLength(1));
    expect(bridge.applies.single['bindIdentity'], isFalse);
    expect(find.byKey(const Key('metadata-success')), findsOneWidget);
    expect(find.textContaining('Применены поля:'), findsOneWidget);
  });

  testWidgets('filename can be edited and suggested from current artist and title', (tester) async {
    final bridge = await openEditor(tester);
    await tester.enterText(find.byKey(const Key('metadata-field-title')), 'Новая песня');
    await reveal(tester, const Key('metadata-suggest-filename'));
    await tester.tap(find.byKey(const Key('metadata-suggest-filename')));
    await tester.pump();
    final field = tester.widget<TextField>(find.byKey(const Key('metadata-field-fileName')));
    expect(field.controller!.text, 'Second Artist - Новая песня.mp3');
    await reveal(tester, const Key('metadata-save'));
    await tester.tap(find.byKey(const Key('metadata-save')));
    await tester.pumpAndSettle();
    expect((bridge.updates.single['changes'] as Map)['fileName'], 'Second Artist - Новая песня.mp3');
  });

  testWidgets('Apply + Bind explicitly requests exact user-confirmed identity', (tester) async {
    final bridge = await openEditor(tester);
    await reveal(tester, const Key('metadata-yandex-search'));
    await tester.tap(find.byKey(const Key('metadata-yandex-search')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('yandex-result-123456')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('compare-apply-bind')));
    await tester.pumpAndSettle();
    expect(bridge.applies, hasLength(1));
    expect(bridge.applies.single['bindIdentity'], isTrue);
    expect(bridge.applies.single['externalId'], '123456');
    expect(find.byKey(const Key('metadata-success')), findsOneWidget);
    expect(find.textContaining('Exact-связь'), findsOneWidget);
  });
}
