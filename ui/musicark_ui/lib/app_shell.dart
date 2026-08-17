import 'package:flutter/material.dart';

import 'about_page.dart';
import 'account_control.dart';
import 'account_session.dart';
import 'app_localizations_ext.dart';
import 'app_settings.dart';
import 'audio_player.dart';
import 'coverage_bridge.dart';
import 'coverage_page.dart';
import 'download_bridge.dart';
import 'download_page.dart';
import 'help_page.dart';
import 'local_library_page.dart';
import 'matching_bridge.dart';
import 'matching_page.dart';
import 'musicark_bridge.dart';
import 'settings_page.dart';
import 'sync_bridge.dart';
import 'sync_page.dart';
import 'yandex_app.dart' as yandex;
import 'yandex_content_labels.dart';

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
  });

  final MusicArkBridgeClient bridge;
  final MatchingBridgeClient matchingBridge;
  final CoverageBridgeClient coverageBridge;
  final DownloadBridgeClient downloadBridge;
  final SyncBridgeClient syncBridge;
  final AppSettingsController settings;
  final AccountSessionController accountSession;

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

  // IndexedStack deliberately keeps pages alive, but the data pages must not keep
  // stale database snapshots. Bumping the activation revision gives the selected
  // page a fresh State/initState on every navigation activation. This is also the
  // cross-screen invalidation boundary: mutations already reload their own page;
  // any other page re-reads authoritative state the next time it is opened.
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

  Widget _buildYandexSection() {
    return LayoutBuilder(
      builder: (context, constraints) {
        // The Yandex page still contains its own fixed-width 280 px sidebar and
        // desktop track controls. Letting the outer shell squeeze that nested
        // layout to phone-like widths makes ListTile.trailing consume the whole
        // row and can trigger a render exception. Until the Yandex page gets a
        // dedicated compact layout, keep a safe desktop workspace and scroll it
        // horizontally on unusually narrow windows instead of crashing.
        const minimumWorkspaceWidth = 920.0;
        final workspaceWidth = constraints.maxWidth < minimumWorkspaceWidth
            ? minimumWorkspaceWidth
            : constraints.maxWidth;
        final nestedTheme = Theme.of(context).copyWith(
          // The application shell owns the product title. Hide the legacy nested
          // app bar so stale historical version labels are not shown in the UI.
          appBarTheme: Theme.of(context).appBarTheme.copyWith(toolbarHeight: 0),
        );
        return SingleChildScrollView(
          key: const Key('yandex-horizontal-viewport'),
          scrollDirection: Axis.horizontal,
          child: SizedBox(
            width: workspaceWidth,
            child: Theme(
              data: nestedTheme,
              child: yandex.MusicArkHomePage(
                key: ValueKey('yandex-${widget.accountSession.logoutRevision}'),
                bridge: widget.bridge,
              ),
            ),
          ),
        );
      },
    );
  }

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
      width: 220,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: NavigationRail(
              key: const Key('main-navigation'),
              selectedIndex: _index < _settingsIndex ? _index : null,
              onDestinationSelected: _selectSection,
              labelType: NavigationRailLabelType.all,
              groupAlignment: -1,
              leading: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text('MusicArk', style: Theme.of(context).textTheme.titleMedium),
              ),
              destinations: destinations,
            ),
          ),
          const Divider(height: 1),
          ListTile(
            key: const Key('nav-settings'),
            selected: _index >= _settingsIndex,
            leading: const Icon(Icons.settings_outlined),
            title: Text(l10n.navSettings),
            onTap: () => _selectSection(_settingsIndex),
          ),
          const Divider(height: 1),
          AccountControl(
            session: widget.accountSession,
            onOpenYandex: () => _selectSection(0),
            onLogout: _logout,
          ),
        ],
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
                      // Keep the Yandex page stateful. Theme and locale rebuild the
                      // MaterialApp, but this State remains and preserves playlist scope.
                      Column(
                        children: [
                          Padding(
                            padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
                            child: Align(
                              alignment: Alignment.centerRight,
                              child: YandexContentLabelsButton(bridge: widget.bridge),
                            ),
                          ),
                          Expanded(child: _buildYandexSection()),
                        ],
                      ),
                      _localLibraryOpened
                          ? LocalLibraryPage(
                              key: ValueKey('local-${_activationRevision[1]}'),
                              bridge: widget.bridge,
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
                      const HelpPage(),
                      AboutPage(settings: widget.settings),
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
