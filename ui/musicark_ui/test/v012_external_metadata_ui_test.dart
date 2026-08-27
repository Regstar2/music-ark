import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:musicark_ui/account_session.dart';
import 'package:musicark_ui/app_settings.dart';
import 'package:musicark_ui/external_metadata_bridge.dart';
import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/metadata_bridge.dart';
import 'package:musicark_ui/metadata_editor_page.dart';
import 'package:musicark_ui/settings_page.dart';

class _MemorySettingsStorage implements AppSettingsStorage {
  Map<String, dynamic> value = {};

  @override
  Future<Map<String, dynamic>> read() async => value;

  @override
  Future<void> write(Map<String, dynamic> value) async =>
      this.value = Map.of(value);
}

void main() {
  Widget localized(Widget child) => MaterialApp(
        locale: const Locale('ru'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: child,
      );

  testWidgets('Settings exposes only System Direct and Custom proxy modes', (
    tester,
  ) async {
    final settings = AppSettingsController(storage: _MemorySettingsStorage());
    await settings.load();
    final session = AccountSessionController()..finishInitialization();
    final external = FakeExternalMetadataBridge(networkMode: 'system');

    await tester.pumpWidget(
      localized(
        SettingsPage(
          settings: settings,
          session: session,
          onOpenYandex: () {},
          onOpenHelp: () {},
          onOpenAbout: () {},
          externalBridge: external,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('network-settings-card')), findsOneWidget);
    expect(find.byKey(const Key('network-mode-selector')), findsOneWidget);
    expect(find.text('Системный'), findsOneWidget);
    expect(find.text('Прямое'), findsOneWidget);
    expect(find.text('Прокси'), findsOneWidget);
    expect(find.text('Cloudflare WARP'), findsNothing);
    expect(find.byKey(const Key('warp-install')), findsNothing);
    expect(find.byKey(const Key('warp-status-label')), findsNothing);
    expect(find.byKey(const Key('external-sources-card')), findsNothing);
  });

  testWidgets('Custom proxy is saved before connectivity test', (
    tester,
  ) async {
    final settings = AppSettingsController(storage: _MemorySettingsStorage());
    await settings.load();
    final session = AccountSessionController()..finishInitialization();
    final external = FakeExternalMetadataBridge(networkMode: 'direct');

    await tester.pumpWidget(
      localized(
        SettingsPage(
          settings: settings,
          session: session,
          onOpenYandex: () {},
          onOpenHelp: () {},
          onOpenAbout: () {},
          externalBridge: external,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Прокси'));
    await tester.pumpAndSettle();
    expect(external.networkMode, 'custom_proxy');

    await tester.enterText(
      find.byKey(const Key('proxy-host')),
      '127.0.0.1',
    );
    await tester.enterText(find.byKey(const Key('proxy-port')), '1080');
    await tester.tap(find.byKey(const Key('network-test')));
    await tester.pumpAndSettle();
    expect(external.networkMode, 'custom_proxy');
  });

  testWidgets('legacy WARP value is presented as System without WARP controls', (
    tester,
  ) async {
    final settings = AppSettingsController(storage: _MemorySettingsStorage());
    await settings.load();
    final session = AccountSessionController()..finishInitialization();
    final external = FakeExternalMetadataBridge(networkMode: 'warp');

    await tester.pumpWidget(
      localized(
        SettingsPage(
          settings: settings,
          session: session,
          onOpenYandex: () {},
          onOpenHelp: () {},
          onOpenAbout: () {},
          externalBridge: external,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final selector = tester.widget<SegmentedButton<String>>(
      find.byKey(const Key('network-mode-selector')),
    );
    expect(selector.selected, {'system'});
    expect(find.text('Cloudflare WARP'), findsNothing);
  });

  testWidgets('Metadata Editor shows normalized external candidates', (
    tester,
  ) async {
    final metadata = FakeMetadataBridge();
    final external = FakeExternalMetadataBridge(
      candidates: [
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
      ],
    );

    await tester.pumpWidget(
      localized(
        MetadataEditorPage(
          localFileId: 7,
          bridge: metadata,
          externalBridge: external,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.ensureVisible(
      find.byKey(const Key('metadata-external-identify')),
    );
    await tester.tap(find.byKey(const Key('metadata-external-identify')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('external-metadata-dialog')), findsOneWidget);
    expect(find.text('Numb'), findsOneWidget);
    expect(find.textContaining('MusicBrainz'), findsWidgets);
    expect(find.byKey(const Key('external-more-alternatives')), findsOneWidget);
  });
}
