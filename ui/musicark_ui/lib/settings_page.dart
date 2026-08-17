import 'package:flutter/material.dart';

import 'account_session.dart';
import 'app_localizations_ext.dart';
import 'app_settings.dart';

class SettingsPage extends StatelessWidget {
  const SettingsPage({
    super.key,
    required this.settings,
    required this.session,
    required this.onOpenYandex,
    required this.onOpenHelp,
    required this.onOpenAbout,
  });

  final AppSettingsController settings;
  final AccountSessionController session;
  final VoidCallback onOpenYandex;
  final VoidCallback onOpenHelp;
  final VoidCallback onOpenAbout;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      key: const Key('settings-page'),
      appBar: AppBar(title: Text(l10n.settingsTitle)),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _SettingsSection(
            title: l10n.settingsAppearance,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(l10n.themeTitle, style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 10),
                SegmentedButton<AppThemePreference>(
                  key: const Key('theme-selector'),
                  showSelectedIcon: true,
                  segments: [
                    ButtonSegment(
                      value: AppThemePreference.system,
                      icon: const Icon(Icons.brightness_auto_outlined),
                      label: Text(l10n.themeSystem),
                    ),
                    ButtonSegment(
                      value: AppThemePreference.light,
                      icon: const Icon(Icons.light_mode_outlined),
                      label: Text(l10n.themeLight),
                    ),
                    ButtonSegment(
                      value: AppThemePreference.dark,
                      icon: const Icon(Icons.dark_mode_outlined),
                      label: Text(l10n.themeDark),
                    ),
                  ],
                  selected: {settings.themePreference},
                  onSelectionChanged: (value) {
                    if (value.isNotEmpty) {
                      settings.setThemePreference(value.first);
                    }
                  },
                ),
              ],
            ),
          ),
          _SettingsSection(
            title: l10n.settingsLanguage,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(l10n.languageTitle, style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 10),
                SegmentedButton<AppLocalePreference>(
                  key: const Key('locale-selector'),
                  showSelectedIcon: true,
                  segments: [
                    ButtonSegment(
                      value: AppLocalePreference.system,
                      icon: const Icon(Icons.language_outlined),
                      label: Text(l10n.languageSystem),
                    ),
                    ButtonSegment(
                      value: AppLocalePreference.ru,
                      label: Text(l10n.languageRussian),
                    ),
                    ButtonSegment(
                      value: AppLocalePreference.en,
                      label: Text(l10n.languageEnglish),
                    ),
                  ],
                  selected: {settings.localePreference},
                  onSelectionChanged: (value) {
                    if (value.isNotEmpty) {
                      settings.setLocalePreference(value.first);
                    }
                  },
                ),
                const SizedBox(height: 10),
                Text(l10n.systemLocaleFallback, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
          _SettingsSection(
            title: l10n.settingsYandex,
            child: Column(
              children: [
                ListTile(
                  leading: Icon(
                    session.isSignedIn ? Icons.verified_user_outlined : Icons.person_outline,
                  ),
                  title: Text(
                    session.isSignedIn
                        ? l10n.yandexAccountSignedIn
                        : l10n.yandexAccountSignedOut,
                  ),
                  subtitle: Text(l10n.settingsAccountHint),
                  trailing: TextButton(
                    onPressed: onOpenYandex,
                    child: Text(l10n.openYandexMusic),
                  ),
                ),
                ListTile(
                  leading: const Icon(Icons.account_circle_outlined),
                  title: Text(l10n.noAvatarFallback),
                ),
              ],
            ),
          ),
          _SettingsSection(
            title: l10n.settingsGeneral,
            child: Text(l10n.settingsSavedAutomatically),
          ),
          Card(
            child: Column(
              children: [
                ListTile(
                  key: const Key('settings-help'),
                  leading: const Icon(Icons.help_outline),
                  title: Text(l10n.settingsHelp),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: onOpenHelp,
                ),
                const Divider(height: 1),
                ListTile(
                  key: const Key('settings-about'),
                  leading: const Icon(Icons.info_outline),
                  title: Text(l10n.settingsAbout),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: onOpenAbout,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingsSection extends StatelessWidget {
  const _SettingsSection({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 12),
              child,
            ],
          ),
        ),
      ),
    );
  }
}
