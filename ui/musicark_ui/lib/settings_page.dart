import 'package:flutter/material.dart';

import 'account_session.dart';
import 'app_localizations_ext.dart';
import 'app_settings.dart';
import 'app_ui_tokens.dart';

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
      body: ListView(
        padding: const EdgeInsets.all(AppUiTokens.pagePadding),
        children: [
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: AppUiTokens.utilityContentMaxWidth,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _SettingsHeader(
                    title: l10n.settingsTitle,
                    subtitle: l10n.settingsSubtitle,
                    autoSaveLabel: l10n.settingsAutoSaveStatus,
                  ),
                  const SizedBox(height: AppUiTokens.sectionGap),
                  _PreferenceCard(
                    icon: Icons.contrast_outlined,
                    title: l10n.settingsAppearance,
                    subtitle: l10n.settingsAppearanceHint,
                    selector: SegmentedButton<AppThemePreference>(
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
                  ),
                  const SizedBox(height: AppUiTokens.sectionGap),
                  _PreferenceCard(
                    icon: Icons.translate_outlined,
                    title: l10n.settingsLanguage,
                    subtitle: l10n.settingsLanguageHint,
                    footer: l10n.systemLocaleFallback,
                    selector: SegmentedButton<AppLocalePreference>(
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
                  ),
                  const SizedBox(height: AppUiTokens.sectionGap),
                  _ProviderAccountCard(
                    session: session,
                    onOpenYandex: onOpenYandex,
                  ),
                  const SizedBox(height: AppUiTokens.sectionGap * 1.5),
                  Text(
                    l10n.settingsSupportSection,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: AppUiTokens.compactGap),
                  Card(
                    clipBehavior: Clip.antiAlias,
                    child: Column(
                      children: [
                        ListTile(
                          key: const Key('settings-help'),
                          leading: const Icon(Icons.help_outline),
                          title: Text(l10n.settingsHelp),
                          subtitle: Text(l10n.settingsHelpSubtitle),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: onOpenHelp,
                        ),
                        const Divider(),
                        ListTile(
                          key: const Key('settings-about'),
                          leading: const Icon(Icons.info_outline),
                          title: Text(l10n.settingsAbout),
                          subtitle: Text(l10n.settingsAboutSubtitle),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: onOpenAbout,
                        ),
                      ],
                    ),
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

class _SettingsHeader extends StatelessWidget {
  const _SettingsHeader({
    required this.title,
    required this.subtitle,
    required this.autoSaveLabel,
  });

  final String title;
  final String subtitle;
  final String autoSaveLabel;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final heading = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 4),
            Text(
              subtitle,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
        );
        final status = Chip(
          key: const Key('settings-auto-save-status'),
          avatar: const Icon(Icons.check, size: 18),
          label: Text(autoSaveLabel),
        );
        if (constraints.maxWidth >= 700) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: heading),
              const SizedBox(width: AppUiTokens.sectionGap),
              status,
            ],
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            heading,
            const SizedBox(height: AppUiTokens.compactGap),
            status,
          ],
        );
      },
    );
  }
}

class _PreferenceCard extends StatelessWidget {
  const _PreferenceCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.selector,
    this.footer,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Widget selector;
  final String? footer;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final description = _SettingDescription(
              icon: icon,
              title: title,
              subtitle: subtitle,
            );
            final selectorBlock = Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                selector,
                if (footer != null) ...[
                  const SizedBox(height: AppUiTokens.compactGap),
                  Text(
                    footer!,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ],
            );
            if (constraints.maxWidth >= AppUiTokens.utilityRowWide) {
              return Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Expanded(child: description),
                  const SizedBox(width: 32),
                  SizedBox(width: 480, child: selectorBlock),
                ],
              );
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                description,
                const SizedBox(height: 16),
                selectorBlock,
              ],
            );
          },
        ),
      ),
    );
  }
}

class _SettingDescription extends StatelessWidget {
  const _SettingDescription({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            color: scheme.secondaryContainer,
            borderRadius: AppUiTokens.mediumRadius,
          ),
          child: Icon(icon, color: scheme.onSecondaryContainer),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
              const SizedBox(height: 3),
              Text(
                subtitle,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ProviderAccountCard extends StatelessWidget {
  const _ProviderAccountCard({
    required this.session,
    required this.onOpenYandex,
  });

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
            if (session.initializing) {
              return _AccountLayout(
                avatar: const CircleAvatar(
                  radius: 28,
                  child: Icon(Icons.person_outline),
                ),
                title: l10n.accountLoading,
                subtitle: l10n.settingsAccountHint,
              );
            }

            if (!session.isSignedIn) {
              return _AccountLayout(
                avatar: const CircleAvatar(
                  radius: 28,
                  child: Icon(Icons.person_outline),
                ),
                title: l10n.settingsYandex,
                subtitle: l10n.yandexAccountSignedOut,
                action: FilledButton.tonalIcon(
                  key: const Key('settings-account-sign-in'),
                  onPressed: onOpenYandex,
                  icon: const Icon(Icons.login),
                  label: Text(l10n.signIn),
                ),
              );
            }

            final title = session.displayName.isNotEmpty
                ? session.displayName
                : l10n.accountProvider;
            final initials = session.initials;
            return _AccountLayout(
              avatar: CircleAvatar(
                radius: 28,
                child: initials.isNotEmpty
                    ? Text(initials)
                    : const Icon(Icons.person),
              ),
              title: title,
              subtitle: l10n.yandexAccountSignedIn,
              status: _ActiveSessionStatus(label: l10n.accountActiveSession),
              note: l10n.noAvatarFallback,
              action: FilledButton.tonalIcon(
                onPressed: onOpenYandex,
                icon: const Icon(Icons.open_in_new),
                label: Text(l10n.openYandexMusic),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _AccountLayout extends StatelessWidget {
  const _AccountLayout({
    required this.avatar,
    required this.title,
    required this.subtitle,
    this.status,
    this.note,
    this.action,
  });

  final Widget avatar;
  final String title;
  final String subtitle;
  final Widget? status;
  final String? note;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final identity = Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            avatar,
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    subtitle,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                  if (status != null) ...[
                    const SizedBox(height: 8),
                    status!,
                  ],
                  if (note != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      note!,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        );
        if (action == null) return identity;
        if (constraints.maxWidth >= 720) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(child: identity),
              const SizedBox(width: 24),
              action!,
            ],
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            identity,
            const SizedBox(height: 16),
            Align(alignment: Alignment.centerLeft, child: action!),
          ],
        );
      },
    );
  }
}

class _ActiveSessionStatus extends StatelessWidget {
  const _ActiveSessionStatus({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.primary,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 7),
        Text(label, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}
