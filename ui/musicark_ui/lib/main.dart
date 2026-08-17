import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';

import 'audio_player.dart';
import 'coverage_bridge.dart';
import 'coverage_page.dart';
import 'download_bridge.dart';
import 'download_page.dart';
import 'local_library_page.dart';
import 'matching_bridge.dart';
import 'matching_page.dart';
import 'musicark_bridge.dart';
import 'sync_bridge.dart';
import 'sync_page.dart';
import 'yandex_app.dart' as yandex;
import 'yandex_content_labels.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  MediaKit.ensureInitialized();
  runApp(const MusicArkDesktopApp());
}

class MusicArkDesktopApp extends StatelessWidget {
  const MusicArkDesktopApp({
    super.key,
    this.bridge,
    this.matchingBridge,
    this.coverageBridge,
    this.downloadBridge,
    this.syncBridge,
  });

  final MusicArkBridgeClient? bridge;
  final MatchingBridgeClient? matchingBridge;
  final CoverageBridgeClient? coverageBridge;
  final DownloadBridgeClient? downloadBridge;
  final SyncBridgeClient? syncBridge;

  @override
  Widget build(BuildContext context) {
    final client = bridge ?? MusicArkBridge();
    final matchingClient = matchingBridge ?? MatchingBridge();
    final coverageClient = coverageBridge ?? CoverageBridge();
    final downloadClient = downloadBridge ?? DownloadBridge();
    final syncClient = syncBridge ?? SyncBridge();
    return MaterialApp(
      title: 'MusicArk 0.8',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
        useMaterial3: true,
      ),
      home: _MusicArkShell(
        bridge: client,
        matchingBridge: matchingClient,
        coverageBridge: coverageClient,
        downloadBridge: downloadClient,
        syncBridge: syncClient,
      ),
    );
  }
}

class _MusicArkShell extends StatefulWidget {
  const _MusicArkShell({
    required this.bridge,
    required this.matchingBridge,
    required this.coverageBridge,
    required this.downloadBridge,
    required this.syncBridge,
  });

  final MusicArkBridgeClient bridge;
  final MatchingBridgeClient matchingBridge;
  final CoverageBridgeClient coverageBridge;
  final DownloadBridgeClient downloadBridge;
  final SyncBridgeClient syncBridge;

  @override
  State<_MusicArkShell> createState() => _MusicArkShellState();
}

class _MusicArkShellState extends State<_MusicArkShell> {
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
        return SingleChildScrollView(
          key: const Key('yandex-horizontal-viewport'),
          scrollDirection: Axis.horizontal,
          child: SizedBox(
            width: workspaceWidth,
            child: yandex.MusicArkHomePage(bridge: widget.bridge),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            key: const Key('main-navigation'),
            selectedIndex: _index,
            onDestinationSelected: _selectSection,
            labelType: NavigationRailLabelType.all,
            leading: Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text('MusicArk', style: Theme.of(context).textTheme.titleMedium),
            ),
            destinations: const [
              NavigationRailDestination(
                icon: Icon(Icons.cloud_outlined),
                selectedIcon: Icon(Icons.cloud),
                label: Text('Яндекс Музыка'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.library_music_outlined, key: Key('nav-local-library')),
                selectedIcon: Icon(Icons.library_music),
                label: Text('Локальная библиотека'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.compare_arrows_outlined, key: Key('nav-matching')),
                selectedIcon: Icon(Icons.compare_arrows),
                label: Text('Сопоставление'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.playlist_remove, key: Key('nav-coverage')),
                selectedIcon: Icon(Icons.playlist_remove),
                label: Text('Недостающие'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.download_outlined, key: Key('nav-downloads')),
                selectedIcon: Icon(Icons.download),
                label: Text('Загрузки'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.sync_outlined, key: Key('nav-sync')),
                selectedIcon: Icon(Icons.sync),
                label: Text('Синхронизация'),
              ),
            ],
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: Column(
              children: [
                Expanded(
                  child: IndexedStack(
                    index: _index,
                    children: [
                      // Keep the Yandex page stateful: recreating it would lose the
                      // currently opened playlist and could change matching scope.
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
