import 'package:flutter/material.dart';

import 'about_page.dart';
import 'account_control.dart';
import 'account_session.dart';
import 'app_localizations_ext.dart';
import 'app_settings.dart';
import 'app_ui_tokens.dart';
import 'audio_player.dart';
import 'content_label_bridge.dart';
import 'coverage_bridge.dart';
import 'coverage_page.dart';
import 'download_bridge.dart';
import 'download_page.dart';
import 'help_page.dart';
import 'local_library_page.dart';
import 'matching_bridge.dart';
import 'matching_page.dart';
import 'metadata_bridge.dart';
import 'musicark_mark.dart';
import 'settings_page.dart';
import 'sync_bridge.dart';
import 'sync_page.dart';
import 'yandex_app.dart' as yandex;
import 'yandex_batch_upload_bridge.dart';
import 'yandex_upload_bridge.dart';

class MusicArkShell extends StatefulWidget {
  const MusicArkShell({
    super.key,
    required this.bridge,
    required this.matchingBridge,
    required this.coverageBridge,
    required this.downloadBridge,
    required this.syncBridge,
    required this.settings,
    required this.accountSession,
    this.metadataBridge = const MetadataBridge(),
    this.contentLabelBridge = const ContentLabelBridge(),
    this.yandexUploadBridge,
  });

  final MusicArkBridgeClient bridge;
  final MatchingBridgeClient matchingBridge;
  final CoverageBridgeClient coverageBridge;
  final DownloadBridgeClient downloadBridge;
  final SyncBridgeClient syncBridge;
  final AppSettingsController settings;
  final AccountSessionController accountSession;

  // Feature bridges stay explicit dependencies. The Yandex bridge is wrapped by
  // v0.9.x session observation and must never be used as a runtime capability test.
  final MetadataBridgeClient? metadataBridge;
  final ContentLabelBridgeClient? contentLabelBridge;
  final YandexUploadBridgeClient? yandexUploadBridge;

  @override
  State<MusicArkShell> createState() => _MusicArkShellState();
}

class _MusicArkShellState extends State<MusicArkShell> {
  static const _settingsIndex = 6;
  static const _helpIndex = 7;
  static const _aboutIndex = 8;

  int _index = 0;
  bool _localLibraryOpened = false;
  bool _matchingOpened = false;
  bool _coverageOpened = false;
  bool _downloadsOpened = false;
  bool _syncOpened = false;

  // Data pages re-read authoritative state when they are activated. The Yandex
  // page remains alive continuously so playlist scope survives theme/locale changes.
  final List<int> _activationRevision = List<int>.filled(6, 0);

  @override
  void initState() {
    super.initState();
    widget.accountSession.addListener(_accountChanged);
  }

  @override
  void dispose() {
    widget.accountSession.removeListener(_accountChanged);
    super.dispose();
  }

  void _accountChanged() {
    if (mounted) setState(() {});
  }

  void _selectSection(int index) {
    setState(() {
      _index = index;
      if (index > 0 && index < _activationRevision.length) {
        _activationRevision[index]++;
      }
      if (index == 1) _localLibraryOpened = true;
      if (index == 2) _matchingOpened = true;
      if (index == 3) _coverageOpened = true;
      if (index == 4) _downloadsOpened = true;
      if (index == 5) _syncOpened = true;
    });
  }

  Future<void> _logout() async {
    try {
      await widget.bridge.logout();
    } on MusicArkBridgeException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${context.l10n.genericError} ${error.message}')),
      );
    }
  }

  Widget _buildYandexSection() => yandex.MusicArkHomePage(
        key: ValueKey('yandex-${widget.accountSession.logoutRevision}'),
        bridge: widget.bridge,
        contentLabelBridge: widget.contentLabelBridge,
      );

  Widget _buildBrand(BuildContext context) => SizedBox(
        width: AppUiTokens.sidebarWidth - 28,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(4, 8, 4, 12),
          child: Row(
            children: [
              const MusicArkMark(size: 32),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'MusicArk',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
              ),
            ],
          ),
        ),
      );

  Widget _buildSidebar(BuildContext context) {
    final l10n = context.l10n;
    final destinations = [
      NavigationRailDestination(
        icon: const Icon(Icons.cloud_outlined),
        selectedIcon: const Icon(Icons.cloud),
        label: Text(l10n.navYandex),
      ),
      NavigationRailDestination(
        icon: const Icon(Icons.library_music_outlined, key: Key('nav-local-library')),
        selectedIcon: const Icon(Icons.library_music),
        label: Text(l10n.navLocalLibrary),
      ),
      NavigationRailDestination(
        icon: const Icon(Icons.compare_arrows_outlined, key: Key('nav-matching')),
        selectedIcon: const Icon(Icons.compare_arrows),
        label: Text(l10n.navMatching),
      ),
      NavigationRailDestination(
        icon: const Icon(Icons.playlist_remove, key: Key('nav-coverage')),
        selectedIcon: const Icon(Icons.playlist_remove),
        label: Text(l10n.navMissing),
      ),
      NavigationRailDestination(
        icon: const Icon(Icons.download_outlined, key: Key('nav-downloads')),
        selectedIcon: const Icon(Icons.download),
        label: Text(l10n.navDownloads),
      ),
      NavigationRailDestination(
        icon: const Icon(Icons.sync_outlined, key: Key('nav-sync')),
        selectedIcon: const Icon(Icons.sync),
        label: Text(l10n.navSync),
      ),
    ];

    return SizedBox(
      key: const Key('musicark-primary-sidebar'),
      width: AppUiTokens.sidebarWidth,
      child: Material(
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: NavigationRail(
                key: const Key('main-navigation'),
                extended: true,
                scrollable: true,
                minWidth: 64,
                minExtendedWidth: AppUiTokens.sidebarWidth,
                useIndicator: true,
                selectedIndex: _index < _settingsIndex ? _index : null,
                onDestinationSelected: _selectSection,
                groupAlignment: -1,
                leading: _buildBrand(context),
                destinations: destinations,
              ),
            ),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 6),
              child: ListTile(
                key: const Key('nav-settings'),
                selected: _index >= _settingsIndex,
                leading: const Icon(Icons.settings_outlined),
                title: Text(
                  l10n.navSettings,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: AppUiTokens.mediumRadius,
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 12),
                onTap: () => _selectSection(_settingsIndex),
              ),
            ),
            const Divider(height: 1),
            AccountControl(
              session: widget.accountSession,
              onOpenYandex: () => _selectSection(0),
              onLogout: _logout,
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          _buildSidebar(context),
          const VerticalDivider(width: 1),
          Expanded(
            child: Column(
              children: [
                Expanded(
                  child: IndexedStack(
                    index: _index,
                    children: [
                      _buildYandexSection(),
                      _localLibraryOpened
                          ? LocalLibraryPage(
                              key: ValueKey('local-${_activationRevision[1]}'),
                              bridge: widget.bridge,
                              metadataBridge: widget.metadataBridge,
                              contentLabelBridge: widget.contentLabelBridge,
                              yandexUploadBridge: widget.yandexUploadBridge,
                            )
                          : const SizedBox.shrink(),
                      _matchingOpened
                          ? MatchingPage(
                              key: ValueKey('matching-${_activationRevision[2]}'),
                              bridge: widget.matchingBridge,
                            )
                          : const SizedBox.shrink(),
                      _coverageOpened
                          ? CoveragePage(
                              key: ValueKey('coverage-${_activationRevision[3]}'),
                              bridge: widget.coverageBridge,
                              matchingBridge: widget.matchingBridge,
                              downloadBridge: widget.downloadBridge,
                              onOpenMatching: () => _selectSection(2),
                              onOpenDownloads: () => _selectSection(4),
                            )
                          : const SizedBox.shrink(),
                      _downloadsOpened
                          ? DownloadPage(
                              key: ValueKey('downloads-${_activationRevision[4]}'),
                              bridge: widget.downloadBridge,
                              coverageBridge: widget.coverageBridge,
                              active: _index == 4,
                            )
                          : const SizedBox.shrink(),
                      _syncOpened
                          ? SyncPage(
                              key: ValueKey('sync-${_activationRevision[5]}'),
                              bridge: widget.syncBridge,
                              managedPlaylistBridge: const YandexBatchUploadBridge(),
                              onOpenDownloads: () => _selectSection(4),
                              onOpenMatching: () => _selectSection(2),
                            )
                          : const SizedBox.shrink(),
                      SettingsPage(
                        settings: widget.settings,
                        session: widget.accountSession,
                        onOpenYandex: () => _selectSection(0),
                        onOpenHelp: () => _selectSection(_helpIndex),
                        onOpenAbout: () => _selectSection(_aboutIndex),
                      ),
                      HelpPage(
                        onBackToSettings: () => _selectSection(_settingsIndex),
                      ),
                      AboutPage(
                        settings: widget.settings,
                        onBackToSettings: () => _selectSection(_settingsIndex),
                      ),
                    ],
                  ),
                ),
                const MusicArkNowPlayingBar(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
