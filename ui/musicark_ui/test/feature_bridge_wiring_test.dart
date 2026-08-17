import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/account_session.dart';
import 'package:musicark_ui/app_settings.dart';
import 'package:musicark_ui/app_shell.dart';
import 'package:musicark_ui/content_label_bridge.dart';
import 'package:musicark_ui/coverage_bridge.dart';
import 'package:musicark_ui/download_bridge.dart';
import 'package:musicark_ui/matching_bridge.dart';
import 'package:musicark_ui/metadata_bridge.dart';
import 'package:musicark_ui/sync_bridge.dart';

class _MemorySettingsStorage implements AppSettingsStorage {
  @override
  Future<Map<String, dynamic>> read() async => const {};

  @override
  Future<void> write(Map<String, dynamic> value) async {}
}

void main() {
  test('session-aware bridge does not disable track feature bridges', () {
    final accountSession = AccountSessionController();
    final settings = AppSettingsController(storage: _MemorySettingsStorage());
    final shell = MusicArkShell(
      bridge: SessionAwareMusicArkBridge(
        FakeMusicArkBridge(startSignedIn: false),
        accountSession,
      ),
      matchingBridge: MatchingBridge(),
      coverageBridge: CoverageBridge(),
      downloadBridge: DownloadBridge(),
      syncBridge: SyncBridge(),
      settings: settings,
      accountSession: accountSession,
    );

    expect(shell.metadataBridge, isA<MetadataBridgeClient>());
    expect(shell.contentLabelBridge, isA<ContentLabelBridgeClient>());

    settings.dispose();
    accountSession.dispose();
  });
}
