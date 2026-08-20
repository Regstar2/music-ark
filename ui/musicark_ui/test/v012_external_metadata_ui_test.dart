import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:musicark_ui/account_session.dart';
import 'package:musicark_ui/app_settings.dart';
import 'package:musicark_ui/external_metadata_bridge.dart';
import 'package:musicark_ui/metadata_bridge.dart';
import 'package:musicark_ui/metadata_editor_page.dart';
import 'package:musicark_ui/settings_page.dart';

class _MemorySettingsStorage implements AppSettingsStorage {
  Map<String, dynamic> value = {};
  @override
  Future<Map<String, dynamic>> read() async => value;
  @override
  Future<void> write(Map<String, dynamic> value) async => this.value = Map.of(value);
}

void main() {
  testWidgets('Settings exposes network modes and WARP install state', (tester) async {
    final settings = AppSettingsController(storage: _MemorySettingsStorage());
    await settings.load();
    final session = AccountSessionController()..finishInitialization();
    final external = FakeExternalMetadataBridge(warpState: 'not_installed');

    await tester.pumpWidget(MaterialApp(
      home: SettingsPage(
        settings: settings,
        session: session,
        onOpenYandex: () {},
        onOpenHelp: () {},
        onOpenAbout: () {},
        externalBridge: external,
      ),
    ));

    expect(find.byKey(const Key('network-settings-card')), findsOneWidget);
    expect(find.byKey(const Key('network-mode-selector')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('warp-refresh')));
    await tester.tap(find.byKey(const Key('warp-refresh')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('warp-install')), findsOneWidget);
  });

  testWidgets('Metadata Editor shows normalized external candidates', (tester) async {
    final metadata = FakeMetadataBridge();
    final external = FakeExternalMetadataBridge(candidates: [
      {
        'candidateId': 'candidate-1',
        'source': 'musicbrainz',
        'sourceDisplayName': 'MusicBrainz',
        'confidence': 'strong',
        'fields': {
          'title': 'Numb',
          'artists': ['Linkin Park'],
          'album': 'Meteora',
          'year': 2003,
        },
        'artwork': {'cachePath': null},
        'evidence': [
          {'type': 'EXACT_RECORDING_MBID', 'source': 'musicbrainz'},
        ],
      },
    ]);

    await tester.pumpWidget(MaterialApp(
      home: MetadataEditorPage(
        localFileId: 7,
        bridge: metadata,
        externalBridge: external,
      ),
    ));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('metadata-external-identify')));
    await tester.tap(find.byKey(const Key('metadata-external-identify')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('external-metadata-dialog')), findsOneWidget);
    expect(find.text('Numb'), findsOneWidget);
    expect(find.textContaining('MusicBrainz'), findsWidgets);
    expect(find.byKey(const Key('external-more-alternatives')), findsOneWidget);
  });
}
