import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:media_kit/media_kit.dart';

import 'account_session.dart';
import 'app_localizations_ext.dart';
import 'app_settings.dart';
import 'app_shell.dart';
import 'app_theme.dart';
import 'content_label_bridge.dart';
import 'coverage_bridge.dart';
import 'download_bridge.dart';
import 'l10n/app_localizations.dart';
import 'matching_bridge.dart';
import 'metadata_bridge.dart';
import 'musicark_bridge.dart';
import 'sync_bridge.dart';
import 'yandex_upload_bridge.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  MediaKit.ensureInitialized();
  runApp(const MusicArkDesktopApp());
}

Locale resolveAppLocale(Locale? locale) {
  final language = locale?.languageCode.toLowerCase();
  return language == 'en' ? const Locale('en') : const Locale('ru');
}

class _InjectedDefaultsStorage implements AppSettingsStorage {
  const _InjectedDefaultsStorage();

  @override
  Future<Map<String, dynamic>> read() async => const {};

  @override
  Future<void> write(Map<String, dynamic> value) async {}
}

class MusicArkDesktopApp extends StatefulWidget {
  const MusicArkDesktopApp({
    super.key,
    this.bridge,
    this.matchingBridge,
    this.coverageBridge,
    this.downloadBridge,
    this.syncBridge,
    this.metadataBridge,
    this.contentLabelBridge,
    this.yandexUploadBridge,
    this.settingsStorage,
  });

  final MusicArkBridgeClient? bridge;
  final MatchingBridgeClient? matchingBridge;
  final CoverageBridgeClient? coverageBridge;
  final DownloadBridgeClient? downloadBridge;
  final SyncBridgeClient? syncBridge;
  final MetadataBridgeClient? metadataBridge;
  final ContentLabelBridgeClient? contentLabelBridge;
  final YandexUploadBridgeClient? yandexUploadBridge;
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
    final injectedMode = widget.bridge != null;
    _settings = AppSettingsController(
      storage: widget.settingsStorage ??
          (injectedMode ? const _InjectedDefaultsStorage() : null),
    );
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
    final injectedMode = widget.bridge != null;
    final featureLabels = widget.contentLabelBridge ??
        (injectedMode ? null : const ContentLabelBridge());
    final featureYandexUpload = widget.yandexUploadBridge ??
        (injectedMode ? null : const YandexUploadBridge());
    return AnimatedBuilder(
      animation: _settings,
      builder: (context, _) {
        final effectiveLocale = _settings.locale ??
            resolveAppLocale(
              WidgetsBinding.instance.platformDispatcher.locale,
            );
        return MaterialApp(
          onGenerateTitle: (context) => context.l10n.appName,
          theme: AppTheme.light,
          darkTheme: AppTheme.dark,
          themeMode: _settings.themeMode,
          locale: effectiveLocale,
          localizationsDelegates: const [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          supportedLocales: AppLocalizations.supportedLocales,
          home: MusicArkShell(
            bridge: _bridge,
            matchingBridge: _matchingBridge,
            coverageBridge: _coverageBridge,
            downloadBridge: _downloadBridge,
            syncBridge: _syncBridge,
            metadataBridge: widget.metadataBridge ?? const MetadataBridge(),
            contentLabelBridge: featureLabels,
            yandexUploadBridge: featureYandexUpload,
            settings: _settings,
            accountSession: _accountSession,
          ),
        );
      },
    );
  }
}
