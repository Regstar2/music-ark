import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app_info.dart';
import 'app_localizations_ext.dart';
import 'app_settings.dart';
import 'app_ui_tokens.dart';
import 'musicark_mark.dart';

class AboutPage extends StatelessWidget {
  const AboutPage({
    super.key,
    required this.settings,
    this.onBackToSettings,
  });

  final AppSettingsController settings;
  final VoidCallback? onBackToSettings;

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

  Future<void> _copyRepository(BuildContext context) async {
    await Clipboard.setData(const ClipboardData(text: AppInfo.repositoryUrl));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(context.l10n.repositoryCopied)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      key: const Key('about-page'),
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
                  _AboutBreadcrumb(
                    current: l10n.aboutTitle,
                    settingsLabel: l10n.settingsTitle,
                    onBack: onBackToSettings,
                  ),
                  const SizedBox(height: AppUiTokens.compactGap),
                  Text(
                    l10n.aboutTitle,
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: AppUiTokens.sectionGap),
                  _ProductCard(onCopyRepository: () => _copyRepository(context)),
                  const SizedBox(height: AppUiTokens.sectionGap * 1.5),
                  _SectionTitle(label: l10n.aboutVersionAndEnvironment),
                  const SizedBox(height: AppUiTokens.compactGap),
                  _EnvironmentCard(
                    left: [
                      _InfoValue(label: l10n.versionLabel, value: AppInfo.version),
                      _InfoValue(
                        label: l10n.backendVersionLabel,
                        value: AppInfo.backendVersion,
                      ),
                      _InfoValue(
                        label: l10n.databaseSchemaLabel,
                        value: AppInfo.databaseSchemaVersion,
                      ),
                    ],
                    right: [
                      _InfoValue(
                        label: l10n.platformLabel,
                        value: '${Platform.operatingSystem} ${Platform.operatingSystemVersion}',
                      ),
                      _InfoValue(label: l10n.themeLabel, value: _themeValue(context)),
                      _InfoValue(label: l10n.localeLabel, value: _localeValue(context)),
                    ],
                  ),
                  const SizedBox(height: AppUiTokens.sectionGap * 1.5),
                  _SectionTitle(label: l10n.aboutDiagnosticsAndLicenses),
                  const SizedBox(height: AppUiTokens.compactGap),
                  Card(
                    clipBehavior: Clip.antiAlias,
                    child: Column(
                      children: [
                        _AboutActionRow(
                          icon: Icons.info_outline,
                          title: l10n.technicalDetails,
                          subtitle: l10n.diagnosticsPrivacy,
                          action: FilledButton.tonalIcon(
                            key: const Key('copy-diagnostics'),
                            onPressed: () => _copyDiagnostics(context),
                            icon: const Icon(Icons.copy_outlined),
                            label: Text(l10n.copyDiagnostics),
                          ),
                        ),
                        const Divider(),
                        _AboutActionRow(
                          icon: Icons.description_outlined,
                          title: l10n.openSourceLicenses,
                          subtitle: l10n.licensesDescription,
                          action: OutlinedButton.icon(
                            key: const Key('open-source-licenses'),
                            onPressed: () => showLicensePage(
                              context: context,
                              applicationName: AppInfo.name,
                              applicationVersion: AppInfo.version,
                            ),
                            icon: const Icon(Icons.chevron_right),
                            label: Text(l10n.openSourceLicenses),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppUiTokens.sectionGap * 1.5),
                  _SectionTitle(label: l10n.aboutProjectSection),
                  const SizedBox(height: AppUiTokens.compactGap),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: _ProjectRow(
                        title: l10n.repositoryLabel,
                        url: AppInfo.repositoryUrl,
                        actionLabel: l10n.copyRepository,
                        onCopy: () => _copyRepository(context),
                      ),
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

class _AboutBreadcrumb extends StatelessWidget {
  const _AboutBreadcrumb({
    required this.current,
    required this.settingsLabel,
    required this.onBack,
  });

  final String current;
  final String settingsLabel;
  final VoidCallback? onBack;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        if (onBack != null)
          TextButton(
            key: const Key('about-back-settings'),
            onPressed: onBack,
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              minimumSize: const Size(0, 32),
            ),
            child: Text(settingsLabel),
          )
        else
          Text(
            settingsLabel,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 4),
          child: Icon(Icons.chevron_right, size: 16),
        ),
        Flexible(
          child: Text(
            current,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
        ),
      ],
    );
  }
}

class _ProductCard extends StatelessWidget {
  const _ProductCard({required this.onCopyRepository});

  final VoidCallback onCopyRepository;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Card(
      key: const Key('about-product-card'),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final identity = Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const MusicArkMark(size: 72),
                const SizedBox(width: 18),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        AppInfo.name,
                        style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                      const SizedBox(height: 6),
                      Chip(label: Text(AppInfo.version)),
                      const SizedBox(height: 8),
                      Text(
                        l10n.aboutDescription,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                      ),
                    ],
                  ),
                ),
              ],
            );
            final action = OutlinedButton.icon(
              key: const Key('copy-repository-hero'),
              onPressed: onCopyRepository,
              icon: const Icon(Icons.code),
              label: Text(l10n.copyRepository),
            );
            if (constraints.maxWidth >= AppUiTokens.utilityRowWide) {
              return Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Expanded(child: identity),
                  const SizedBox(width: 24),
                  action,
                ],
              );
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                identity,
                const SizedBox(height: 16),
                Align(alignment: Alignment.centerLeft, child: action),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Text(
      label,
      style: Theme.of(context).textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w700,
          ),
    );
  }
}

class _InfoValue {
  const _InfoValue({required this.label, required this.value});

  final String label;
  final String value;
}

class _EnvironmentCard extends StatelessWidget {
  const _EnvironmentCard({required this.left, required this.right});

  final List<_InfoValue> left;
  final List<_InfoValue> right;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('about-environment-card'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: LayoutBuilder(
          builder: (context, constraints) {
            if (constraints.maxWidth >= AppUiTokens.utilityGridWide) {
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: _InfoColumn(values: left)),
                  const SizedBox(width: 32),
                  Expanded(child: _InfoColumn(values: right)),
                ],
              );
            }
            return Column(
              children: [
                _InfoColumn(values: left, stacked: true),
                const Divider(),
                _InfoColumn(values: right, stacked: true),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _InfoColumn extends StatelessWidget {
  const _InfoColumn({required this.values, this.stacked = false});

  final List<_InfoValue> values;
  final bool stacked;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (var index = 0; index < values.length; index++) ...[
          _InfoRow(value: values[index], stacked: stacked),
          if (index != values.length - 1) const Divider(),
        ],
      ],
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.value, required this.stacked});

  final _InfoValue value;
  final bool stacked;

  @override
  Widget build(BuildContext context) {
    final secondary = Theme.of(context).textTheme.bodyMedium?.copyWith(
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        );
    if (stacked) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 9),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(value.label),
            const SizedBox(height: 3),
            Text(value.value, style: secondary),
          ],
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 9),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(flex: 2, child: Text(value.label)),
          const SizedBox(width: 12),
          Expanded(
            flex: 3,
            child: Text(value.value, textAlign: TextAlign.end, style: secondary),
          ),
        ],
      ),
    );
  }
}

class _AboutActionRow extends StatelessWidget {
  const _AboutActionRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.action,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Widget action;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final copy = Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                    ),
                  ],
                ),
              ),
            ],
          );
          if (constraints.maxWidth >= 720) {
            return Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Expanded(child: copy),
                const SizedBox(width: 24),
                action,
              ],
            );
          }
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              copy,
              const SizedBox(height: 14),
              Align(alignment: Alignment.centerLeft, child: action),
            ],
          );
        },
      ),
    );
  }
}

class _ProjectRow extends StatelessWidget {
  const _ProjectRow({
    required this.title,
    required this.url,
    required this.actionLabel,
    required this.onCopy,
  });

  final String title;
  final String url;
  final String actionLabel;
  final VoidCallback onCopy;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final identity = Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.code),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                  const SizedBox(height: 4),
                  SelectableText(
                    url,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ),
            ),
          ],
        );
        final action = OutlinedButton.icon(
          key: const Key('copy-repository'),
          onPressed: onCopy,
          icon: const Icon(Icons.copy_outlined),
          label: Text(actionLabel),
        );
        if (constraints.maxWidth >= 720) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(child: identity),
              const SizedBox(width: 24),
              action,
            ],
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            identity,
            const SizedBox(height: 14),
            Align(alignment: Alignment.centerLeft, child: action),
          ],
        );
      },
    );
  }
}
