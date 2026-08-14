import 'package:flutter/material.dart';

import 'local_library_page.dart';
import 'matching_bridge.dart';
import 'matching_page.dart';
import 'musicark_bridge.dart';
import 'yandex_app.dart' as yandex;

void main() => runApp(const MusicArkDesktopApp());

class MusicArkDesktopApp extends StatelessWidget {
  const MusicArkDesktopApp({super.key, this.bridge, this.matchingBridge});

  final MusicArkBridgeClient? bridge;
  final MatchingBridgeClient? matchingBridge;

  @override
  Widget build(BuildContext context) {
    final client = bridge ?? MusicArkBridge();
    final matchingClient = matchingBridge ?? MatchingBridge();
    return MaterialApp(
      title: 'MusicArk 0.5',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
        useMaterial3: true,
      ),
      home: _MusicArkShell(bridge: client, matchingBridge: matchingClient),
    );
  }
}

class _MusicArkShell extends StatefulWidget {
  const _MusicArkShell({required this.bridge, required this.matchingBridge});

  final MusicArkBridgeClient bridge;
  final MatchingBridgeClient matchingBridge;

  @override
  State<_MusicArkShell> createState() => _MusicArkShellState();
}

class _MusicArkShellState extends State<_MusicArkShell> {
  int _index = 0;
  bool _localLibraryOpened = false;
  bool _matchingOpened = false;

  void _selectSection(int index) {
    setState(() {
      _index = index;
      if (index == 1) _localLibraryOpened = true;
      if (index == 2) _matchingOpened = true;
    });
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
            ],
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: IndexedStack(
              index: _index,
              children: [
                yandex.MusicArkHomePage(bridge: widget.bridge),
                _localLibraryOpened
                    ? LocalLibraryPage(bridge: widget.bridge)
                    : const SizedBox.shrink(),
                _matchingOpened
                    ? MatchingPage(bridge: widget.matchingBridge)
                    : const SizedBox.shrink(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
