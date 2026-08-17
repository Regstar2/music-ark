import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app_info.dart';
import 'app_localizations_ext.dart';
import 'app_settings.dart';

class AboutPage extends StatelessWidget {
  const AboutPage({super.key, required this.settings});

  final AppSettingsController settings;

  String _themeValue(BuildContext context) => switch (settings.themePreference) {
        AppThemePreference.system => context.l10n.themeSystem,
        AppThemePreference.light => context.l10n.themeLight,
        AppThemePreference.dark => context.l10n.themeDark,
      };

  String _localeValue(BuildContext context) => switch (settings.localePreference) {
        AppLocalePreference.system => context.l10n.languageSystem,
        AppLocalePreference.ru => context.l10n.languageRussian,
        AppLocalePreference.en => context.l10n.languageEnglish,
      };

  String get _diagnostics => [
        '${AppInfo.name}: ${AppInfo.version}',
        'Backend: ${AppInfo.backendVersion}',
        'Database schema: ${AppInfo.databaseSchemaVersion}',
        'OS: ${Platform.operatingSystem} ${Platform.operatingSystemVersion}',
        'Theme: ${settings.themePreference.name}',
        'Locale: ${settings.localePreference.name}',
      ].join('\n');

  Future<void> _copyDiagnostics(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: _diagnostics));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(context.l10n.diagnosticsCopied)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      key: const Key('about-page'),
      appBar: AppBar(title: Text(l10n.aboutTitle)),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(AppInfo.name, style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 8),
          Text(l10n.aboutDescription),
          const SizedBox(height: 20),
          Card(
            child: Column(
              children: [
                _InfoRow(label: l10n.versionLabel, value: AppInfo.version),
                _InfoRow(label: l10n.backendVersionLabel, value: AppInfo.backendVersion),
                _InfoRow(
                  label: l10n.databaseSchemaLabel,
                  value: AppInfo.databaseSchemaVersion,
                ),
                _InfoRow(label: l10n.platformLabel, value: Platform.operatingSystemVersion),
                _InfoRow(label: l10n.themeLabel, value: _themeValue(context)),
                _InfoRow(label: l10n.localeLabel, value: _localeValue(context)),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: ListTile(
              title: Text(l10n.repositoryLabel),
              subtitle: const SelectableText(AppInfo.repositoryUrl),
              leading: const Icon(Icons.code),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(l10n.diagnosticsPrivacy),
                  const SizedBox(height: 12),
                  FilledButton.tonalIcon(
                    key: const Key('copy-diagnostics'),
                    onPressed: () => _copyDiagnostics(context),
                    icon: const Icon(Icons.copy_outlined),
                    label: Text(l10n.copyDiagnostics),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: () => showLicensePage(
                      context: context,
                      applicationName: AppInfo.name,
                      applicationVersion: AppInfo.version,
                    ),
                    icon: const Icon(Icons.description_outlined),
                    label: Text(l10n.openSourceLicenses),
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

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      dense: true,
      title: Text(label),
      trailing: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 440),
        child: Text(value, textAlign: TextAlign.end, overflow: TextOverflow.ellipsis),
      ),
    );
  }
}
