import 'package:flutter/material.dart';

import 'account_session.dart';
import 'app_localizations_ext.dart';
import 'app_settings.dart';
import 'app_ui_tokens.dart';
import 'external_metadata_bridge.dart';
import 'v012_strings.dart';

class SettingsPage extends StatelessWidget {
  const SettingsPage({
    super.key,
    required this.settings,
    required this.session,
    required this.onOpenYandex,
    required this.onOpenHelp,
    required this.onOpenAbout,
    this.externalBridge = const ExternalMetadataBridge(),
  });

  final AppSettingsController settings;
  final AccountSessionController session;
  final VoidCallback onOpenYandex;
  final VoidCallback onOpenHelp;
  final VoidCallback onOpenAbout;
  final ExternalMetadataBridgeClient externalBridge;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      key: const Key('settings-page'),
      body: ListView(
        padding: const EdgeInsets.all(AppUiTokens.pagePadding),
        children: [
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: AppUiTokens.utilityContentMaxWidth),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(children: [
                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(l10n.settingsTitle, style: Theme.of(context).textTheme.headlineMedium),
                      const SizedBox(height: 4),
                      Text(l10n.settingsSubtitle, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
                    ])),
                    Chip(key: const Key('settings-auto-save-status'), avatar: const Icon(Icons.check, size: 18), label: Text(l10n.settingsAutoSaveStatus)),
                  ]),
                  const SizedBox(height: AppUiTokens.sectionGap),
                  _PreferenceCard(
                    icon: Icons.contrast_outlined,
                    title: l10n.settingsAppearance,
                    subtitle: l10n.settingsAppearanceHint,
                    child: SegmentedButton<AppThemePreference>(
                      key: const Key('theme-selector'),
                      segments: [
                        ButtonSegment(value: AppThemePreference.system, icon: const Icon(Icons.brightness_auto_outlined), label: Text(l10n.themeSystem)),
                        ButtonSegment(value: AppThemePreference.light, icon: const Icon(Icons.light_mode_outlined), label: Text(l10n.themeLight)),
                        ButtonSegment(value: AppThemePreference.dark, icon: const Icon(Icons.dark_mode_outlined), label: Text(l10n.themeDark)),
                      ],
                      selected: {settings.themePreference},
                      onSelectionChanged: (value) { if (value.isNotEmpty) settings.setThemePreference(value.first); },
                    ),
                  ),
                  const SizedBox(height: AppUiTokens.sectionGap),
                  _PreferenceCard(
                    icon: Icons.translate_outlined,
                    title: l10n.settingsLanguage,
                    subtitle: l10n.settingsLanguageHint,
                    child: SegmentedButton<AppLocalePreference>(
                      key: const Key('locale-selector'),
                      segments: [
                        ButtonSegment(value: AppLocalePreference.system, icon: const Icon(Icons.language_outlined), label: Text(l10n.languageSystem)),
                        ButtonSegment(value: AppLocalePreference.ru, label: Text(l10n.languageRussian)),
                        ButtonSegment(value: AppLocalePreference.en, label: Text(l10n.languageEnglish)),
                      ],
                      selected: {settings.localePreference},
                      onSelectionChanged: (value) { if (value.isNotEmpty) settings.setLocalePreference(value.first); },
                    ),
                  ),
                  const SizedBox(height: AppUiTokens.sectionGap),
                  _NetworkAccessCard(bridge: externalBridge),
                  const SizedBox(height: AppUiTokens.sectionGap),
                  _ProviderAccountCard(session: session, onOpenYandex: onOpenYandex),
                  const SizedBox(height: AppUiTokens.sectionGap * 1.5),
                  Text(l10n.settingsSupportSection, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: AppUiTokens.compactGap),
                  Card(
                    clipBehavior: Clip.antiAlias,
                    child: Column(children: [
                      ListTile(key: const Key('settings-help'), leading: const Icon(Icons.help_outline), title: Text(l10n.settingsHelp), subtitle: Text(l10n.settingsHelpSubtitle), trailing: const Icon(Icons.chevron_right), onTap: onOpenHelp),
                      const Divider(),
                      ListTile(key: const Key('settings-about'), leading: const Icon(Icons.info_outline), title: Text(l10n.settingsAbout), subtitle: Text(l10n.settingsAboutSubtitle), trailing: const Icon(Icons.chevron_right), onTap: onOpenAbout),
                    ]),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PreferenceCard extends StatelessWidget {
  const _PreferenceCard({required this.icon, required this.title, required this.subtitle, required this.child});
  final IconData icon;
  final String title;
  final String subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: LayoutBuilder(builder: (context, constraints) {
            final description = Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(icon),
              const SizedBox(width: 14),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 3),
                Text(subtitle, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
              ])),
            ]);
            if (constraints.maxWidth >= AppUiTokens.utilityRowWide) {
              return Row(children: [Expanded(child: description), const SizedBox(width: 32), SizedBox(width: 480, child: child)]);
            }
            return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [description, const SizedBox(height: 16), child]);
          }),
        ),
      );
}

class _NetworkAccessCard extends StatefulWidget {
  const _NetworkAccessCard({required this.bridge});
  final ExternalMetadataBridgeClient bridge;

  @override
  State<_NetworkAccessCard> createState() => _NetworkAccessCardState();
}

class _NetworkAccessCardState extends State<_NetworkAccessCard> {
  String _mode = 'auto';
  String _proxyScheme = 'socks5';
  String _warp = 'unknown';
  String _warpMessage = '';
  String _warpServiceMode = '';
  bool _busy = false;
  String? _message;
  List<Map<String, dynamic>> _networkItems = const [];
  final _host = TextEditingController(text: '127.0.0.1');
  final _port = TextEditingController(text: '1080');
  final _username = TextEditingController();
  final _password = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadInitial());
  }

  @override
  void dispose() {
    _host.dispose();
    _port.dispose();
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  Map<String, dynamic> _visibleSettings() => {
        'networkMode': _mode,
        'proxyScheme': _proxyScheme,
        'proxyHost': _host.text.trim(),
        'proxyPort': int.tryParse(_port.text) ?? 1080,
        'proxyUsername': _username.text.trim(),
        if (_password.text.isNotEmpty) 'proxyPassword': _password.text,
      };

  void _applyResult(Map<String, dynamic> result) {
    final settings = result['settings'];
    if (settings is Map) {
      _mode = '${settings['mode'] ?? _mode}';
      _proxyScheme = '${settings['proxy_scheme'] ?? settings['proxyScheme'] ?? _proxyScheme}';
      _host.text = '${settings['proxy_host'] ?? settings['proxyHost'] ?? _host.text}';
      _port.text = '${settings['proxy_port'] ?? settings['proxyPort'] ?? _port.text}';
      _username.text = '${settings['proxy_username'] ?? settings['proxyUsername'] ?? _username.text}';
    }
    final warp = result['warp'];
    if (warp is Map) {
      _warp = '${warp['state'] ?? _warp}';
      _warpMessage = '${warp['message'] ?? ''}';
      _warpServiceMode = '${warp['serviceMode'] ?? ''}';
    }
    final items = result['items'];
    if (items is List) {
      _networkItems = items.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList();
    }
  }

  Future<void> _run(Future<Map<String, dynamic>> Function() action) async {
    if (_busy) return;
    setState(() { _busy = true; _message = null; });
    try {
      _applyResult(await action());
    } catch (error) {
      _message = '$error';
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _loadInitial() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final results = await Future.wait([widget.bridge.getNetworkSettings(), widget.bridge.warpStatus()]);
      _applyResult(results[0]);
      _applyResult(results[1]);
    } catch (error) {
      _message = '$error';
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _saveVisibleSettings() => _run(() => widget.bridge.updateNetworkSettings(_visibleSettings()));

  Future<void> _changeMode(String mode) async {
    if (_busy || mode == _mode) return;
    setState(() => _mode = mode);
    await _saveVisibleSettings();
  }

  Future<void> _testVisibleSettings() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _message = null;
      _networkItems = const [];
    });
    try {
      _applyResult(await widget.bridge.updateNetworkSettings(_visibleSettings()));
      _applyResult(await widget.bridge.testNetwork());
    } catch (error) {
      _message = '$error';
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _sourceLabel(String source) => switch (source) {
        'musicbrainz' => 'MusicBrainz',
        'listenbrainz_mapper' => 'MusicBrainz Mapper',
        'acoustid' => 'AcoustID',
        'cover_art_archive' => 'Cover Art Archive',
        'discogs' => 'Discogs',
        'theaudiodb' => 'TheAudioDB',
        'lastfm' => 'Last.fm',
        _ => source,
      };

  String _networkDetail(Map<String, dynamic> item, V012Strings s) {
    if (item['reachable'] == true) {
      final status = item['statusCode'];
      if (status == null) return 'OK';
      if (status is num && status >= 400) return 'HTTP $status · ${s.hostReached}';
      return 'HTTP $status';
    }
    final error = '${item['error'] ?? 'unreachable'}';
    final detail = '${item['errorDetail'] ?? ''}'.trim();
    return detail.isEmpty ? error : '$error · $detail';
  }

  IconData _networkIcon(Map<String, dynamic> item) {
    if (item['reachable'] != true) return Icons.error_outline;
    final status = item['statusCode'];
    if (status is num && status >= 400) return Icons.warning_amber_outlined;
    return Icons.check_circle_outline;
  }

  @override
  Widget build(BuildContext context) {
    final s = V012Strings.of(context);
    final warpLabel = switch (_warp) {
      'not_installed' => s.notInstalled,
      'proxy_ready' => s.localProxyReady,
      'connected' => s.localProxyNotReady,
      'connecting' => s.configuring,
      'installed' || 'disconnected' => s.installed,
      _ => _warp,
    };
    final warpDetails = [
      if (_warpServiceMode.isNotEmpty) _warpServiceMode,
      if (_warpMessage.isNotEmpty) _warpMessage,
    ].join(' · ');
    final apiOk = _networkItems.where((item) {
      final status = item['statusCode'];
      return item['reachable'] == true && status is num && status < 400;
    }).length;
    final hostReached = _networkItems.where((item) {
      final status = item['statusCode'];
      return item['reachable'] == true && status is num && status >= 400;
    }).length;
    final failed = _networkItems.where((item) => item['reachable'] != true).length;

    return Card(
      key: const Key('network-settings-card'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            const Icon(Icons.public),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(s.networkTitle, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
              Text(s.networkHint, style: Theme.of(context).textTheme.bodySmall),
            ])),
          ]),
          const SizedBox(height: 16),
          SegmentedButton<String>(
            key: const Key('network-mode-selector'),
            segments: [
              ButtonSegment(value: 'auto', label: Text(s.automatic)),
              ButtonSegment(value: 'direct', label: Text(s.direct)),
              ButtonSegment(value: 'warp', label: Text(s.warp)),
              ButtonSegment(value: 'custom_proxy', label: Text(s.proxy)),
            ],
            selected: {_mode},
            onSelectionChanged: _busy ? null : (value) { if (value.isNotEmpty) _changeMode(value.first); },
          ),
          if (_mode == 'custom_proxy') ...[
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              key: const Key('proxy-scheme'),
              value: _proxyScheme,
              decoration: InputDecoration(labelText: s.proxyType),
              items: const [
                DropdownMenuItem(value: 'socks5', child: Text('SOCKS5')),
                DropdownMenuItem(value: 'http', child: Text('HTTP')),
                DropdownMenuItem(value: 'https', child: Text('HTTPS')),
              ],
              onChanged: _busy ? null : (value) { if (value != null) setState(() => _proxyScheme = value); },
            ),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(child: TextField(key: const Key('proxy-host'), controller: _host, decoration: InputDecoration(labelText: s.host))),
              const SizedBox(width: 8),
              SizedBox(width: 110, child: TextField(key: const Key('proxy-port'), controller: _port, keyboardType: TextInputType.number, decoration: InputDecoration(labelText: s.port))),
            ]),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(child: TextField(key: const Key('proxy-username'), controller: _username, decoration: InputDecoration(labelText: s.username))),
              const SizedBox(width: 8),
              Expanded(child: TextField(key: const Key('proxy-password'), controller: _password, obscureText: true, decoration: InputDecoration(labelText: s.password))),
            ]),
          ],
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
            FilledButton.tonalIcon(key: const Key('network-save'), onPressed: _busy ? null : _saveVisibleSettings, icon: const Icon(Icons.save_outlined), label: Text(s.save)),
            OutlinedButton.icon(key: const Key('network-test'), onPressed: _busy ? null : _testVisibleSettings, icon: const Icon(Icons.network_check), label: Text(s.testConnection)),
            OutlinedButton.icon(key: const Key('warp-refresh'), onPressed: _busy ? null : () => _run(widget.bridge.warpStatus), icon: const Icon(Icons.refresh), label: Text(s.refreshStatus)),
            if (_warp == 'not_installed') FilledButton.tonal(key: const Key('warp-install'), onPressed: _busy ? null : () => _run(widget.bridge.installWarp), child: Text(s.installWarp)),
            if (_warp == 'installed' || _warp == 'disconnected') FilledButton.tonal(key: const Key('warp-enable'), onPressed: _busy ? null : () => _run(widget.bridge.enableWarp), child: Text(s.enableWarp)),
            if (_warp == 'connected') FilledButton.tonal(key: const Key('warp-configure-proxy'), onPressed: _busy ? null : () => _run(widget.bridge.enableWarp), child: Text(s.configureWarpProxy)),
            if (_warp == 'connected' || _warp == 'proxy_ready' || _warp == 'connecting') OutlinedButton(key: const Key('warp-disable'), onPressed: _busy ? null : () => _run(widget.bridge.disableWarp), child: Text(s.disableWarp)),
            Text('${s.warp}: $warpLabel', key: const Key('warp-status-label')),
            if (_busy) const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
          ]),
          if (warpDetails.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(warpDetails, key: const Key('warp-status-detail'), style: Theme.of(context).textTheme.bodySmall),
          ],
          if (_message != null) ...[
            const SizedBox(height: 8),
            Text(_message!, key: const Key('network-result')),
          ] else if (_networkItems.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(s.networkSummary(apiOk, hostReached, failed), key: const Key('network-result')),
          ],
          if (_networkItems.isNotEmpty) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final item in _networkItems)
                  Chip(
                    key: Key('network-source-${item['source']}'),
                    avatar: Icon(_networkIcon(item), size: 18),
                    label: Text('${_sourceLabel('${item['source'] ?? ''}')} · ${_networkDetail(item, s)}'),
                  ),
              ],
            ),
          ],
        ]),
      ),
    );
  }
}

class _ProviderAccountCard extends StatelessWidget {
  const _ProviderAccountCard({required this.session, required this.onOpenYandex});
  final AccountSessionController session;
  final VoidCallback onOpenYandex;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Card(
      key: const Key('settings-account-card'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: AnimatedBuilder(
          animation: session,
          builder: (context, _) {
            final signedIn = session.isSignedIn;
            final title = signedIn && session.displayName.isNotEmpty ? session.displayName : l10n.settingsYandex;
            final subtitle = signedIn ? l10n.yandexAccountSignedIn : l10n.yandexAccountSignedOut;
            return Row(children: [
              CircleAvatar(radius: 28, child: signedIn && session.initials.isNotEmpty ? Text(session.initials) : const Icon(Icons.person_outline)),
              const SizedBox(width: 14),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                Text(subtitle),
              ])),
              FilledButton.tonalIcon(
                key: signedIn ? const Key('settings-account-open') : const Key('settings-account-sign-in'),
                onPressed: onOpenYandex,
                icon: Icon(signedIn ? Icons.open_in_new : Icons.login),
                label: Text(signedIn ? l10n.openYandexMusic : l10n.signIn),
              ),
            ]);
          },
        ),
      ),
    );
  }
}
