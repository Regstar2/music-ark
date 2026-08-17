import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:media_kit/media_kit.dart';

import 'account_session.dart';
import 'app_localizations_ext.dart';
import 'app_settings.dart';
import 'app_shell.dart';
import 'app_theme.dart';
import 'coverage_bridge.dart';
import 'download_bridge.dart';
import 'l10n/app_localizations.dart';
import 'matching_bridge.dart';
import 'musicark_bridge.dart';
import 'sync_bridge.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  MediaKit.ensureInitialized();
  runApp(const MusicArkDesktopApp());
}

class MusicArkDesktopApp extends StatefulWidget {
  const MusicArkDesktopApp({
    super.key,
    this.bridge,
    this.matchingBridge,
    this.coverageBridge,
    this.downloadBridge,
    this.syncBridge,
    this.settingsStorage,
  });

  final MusicArkBridgeClient? bridge;
  final MatchingBridgeClient? matchingBridge;
  final CoverageBridgeClient? coverageBridge;
  final DownloadBridgeClient? downloadBridge;
  final SyncBridgeClient? syncBridge;
  final AppSettingsStorage? settingsStorage;

  @override
  State<MusicArkDesktopApp> createState() => _MusicArkDesktopAppState();
}

class _MusicArkDesktopAppState extends State<MusicArkDesktopApp> {
  late final AppSettingsController _settings;
  late final AccountSessionController _accountSession;
  late final SessionAwareMusicArkBridge _bridge;
  late final MatchingBridgeClient _matchingBridge;
  late final CoverageBridgeClient _coverageBridge;
  late final DownloadBridgeClient _downloadBridge;
  late final SyncBridgeClient _syncBridge;

  @override
  void initState() {
    super.initState();
    _settings = AppSettingsController(storage: widget.settingsStorage);
    _accountSession = AccountSessionController();
    _bridge = SessionAwareMusicArkBridge(
      widget.bridge ?? MusicArkBridge(),
      _accountSession,
    );
    _matchingBridge = widget.matchingBridge ?? MatchingBridge();
    _coverageBridge = widget.coverageBridge ?? CoverageBridge();
    _downloadBridge = widget.downloadBridge ?? DownloadBridge();
    _syncBridge = widget.syncBridge ?? SyncBridge();
    _initialize();
  }

  Future<void> _initialize() async {
    await _settings.load();
    try {
      await _bridge.bootstrap();
    } on Object {
      // The Yandex page owns structured provider error rendering. The global
      // account control only needs to leave its bootstrap progress state.
      _accountSession.finishInitialization();
    }
  }

  @override
  void dispose() {
    _settings.dispose();
    _accountSession.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _settings,
      builder: (context, _) => MaterialApp(
        onGenerateTitle: (context) => context.l10n.appName,
        theme: AppTheme.light,
        darkTheme: AppTheme.dark,
        themeMode: _settings.themeMode,
        locale: _settings.locale,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        localeResolutionCallback: (locale, _) {
          final language = locale?.languageCode.toLowerCase();
          if (language == 'en') return const Locale('en');
          if (language == 'ru') return const Locale('ru');
          return const Locale('ru');
        },
        home: MusicArkShell(
          bridge: _bridge,
          matchingBridge: _matchingBridge,
          coverageBridge: _coverageBridge,
          downloadBridge: _downloadBridge,
          syncBridge: _syncBridge,
          settings: _settings,
          accountSession: _accountSession,
        ),
      ),
    );
  }
}
