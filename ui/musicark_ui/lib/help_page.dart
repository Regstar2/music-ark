import 'package:flutter/material.dart';

import 'app_localizations_ext.dart';
import 'app_ui_tokens.dart';

class HelpPage extends StatelessWidget {
  const HelpPage({super.key, this.onBackToSettings});

  final VoidCallback? onBackToSettings;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final groups = [
      _HelpGroupData(
        title: l10n.helpGroupLibrary,
        topics: [
          _HelpTopicData(
            id: 'help-topic-yandex',
            title: l10n.helpYandexTitle,
            summary: l10n.helpYandexSummary,
            details: l10n.helpYandexDetails,
            icon: Icons.cloud_outlined,
          ),
          _HelpTopicData(
            id: 'help-topic-local',
            title: l10n.helpLocalTitle,
            summary: l10n.helpLocalSummary,
            details: l10n.helpLocalDetails,
            icon: Icons.library_music_outlined,
          ),
        ],
      ),
      _HelpGroupData(
        title: l10n.helpGroupAnalysis,
        topics: [
          _HelpTopicData(
            id: 'help-topic-matching',
            title: l10n.helpMatchingTitle,
            summary: l10n.helpMatchingSummary,
            details: l10n.helpMatchingDetails,
            icon: Icons.compare_arrows,
          ),
          _HelpTopicData(
            id: 'help-topic-variant',
            title: l10n.helpVariantTitle,
            summary: l10n.helpVariantSummary,
            details: l10n.helpVariantDetails,
            icon: Icons.rule_outlined,
          ),
          _HelpTopicData(
            id: 'help-topic-missing',
            title: l10n.helpMissingTitle,
            summary: l10n.helpMissingSummary,
            details: l10n.helpMissingDetails,
            icon: Icons.playlist_remove,
          ),
        ],
      ),
      _HelpGroupData(
        title: l10n.helpGroupRecovery,
        topics: [
          _HelpTopicData(
            id: 'help-topic-downloads',
            title: l10n.helpDownloadsTitle,
            summary: l10n.helpDownloadsSummary,
            details: l10n.helpDownloadsDetails,
            icon: Icons.download_outlined,
          ),
          _HelpTopicData(
            id: 'help-topic-sync',
            title: l10n.helpSyncTitle,
            summary: l10n.helpSyncSummary,
            details: l10n.helpSyncDetails,
            icon: Icons.sync,
          ),
          _HelpTopicData(
            id: 'help-topic-metadata',
            title: l10n.helpMetadataTitle,
            summary: l10n.helpMetadataSummary,
            details: l10n.helpMetadataDetails,
            icon: Icons.edit_note_outlined,
          ),
        ],
      ),
      _HelpGroupData(
        title: l10n.helpGroupApplication,
        topics: [
          _HelpTopicData(
            id: 'help-topic-artwork',
            title: l10n.helpArtworkTitle,
            summary: l10n.helpArtworkSummary,
            details: l10n.helpArtworkDetails,
            icon: Icons.album_outlined,
          ),
          _HelpTopicData(
            id: 'help-topic-settings',
            title: l10n.helpSettingsTitle,
            summary: l10n.helpSettingsSummary,
            details: l10n.helpSettingsDetails,
            icon: Icons.settings_outlined,
          ),
          _HelpTopicData(
            id: 'help-topic-safety',
            title: l10n.helpSafetyTitle,
            summary: l10n.helpSafetySummary,
            details: l10n.helpSafetyDetails,
            icon: Icons.shield_outlined,
          ),
        ],
      ),
    ];

    return Scaffold(
      key: const Key('help-page'),
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
                  _UtilityBreadcrumb(
                    current: l10n.helpTitle,
                    settingsLabel: l10n.settingsTitle,
                    onBack: onBackToSettings,
                  ),
                  const SizedBox(height: AppUiTokens.compactGap),
                  Text(
                    l10n.helpTitle,
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    l10n.helpIntro,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                  const SizedBox(height: AppUiTokens.sectionGap),
                  _HelpIntroCard(
                    title: l10n.helpGettingStartedTitle,
                    body: l10n.helpGettingStartedBody,
                  ),
                  const SizedBox(height: AppUiTokens.sectionGap * 1.5),
                  for (var index = 0; index < groups.length; index++) ...[
                    _HelpGroup(data: groups[index]),
                    if (index != groups.length - 1)
                      const SizedBox(height: AppUiTokens.sectionGap * 1.5),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _UtilityBreadcrumb extends StatelessWidget {
  const _UtilityBreadcrumb({
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
            key: const Key('help-back-settings'),
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

class _HelpIntroCard extends StatelessWidget {
  const _HelpIntroCard({required this.title, required this.body});

  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: scheme.secondaryContainer,
                borderRadius: AppUiTokens.mediumRadius,
              ),
              child: Icon(Icons.help_outline, color: scheme.onSecondaryContainer),
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
                  const SizedBox(height: 4),
                  Text(
                    body,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HelpGroupData {
  const _HelpGroupData({required this.title, required this.topics});

  final String title;
  final List<_HelpTopicData> topics;
}

class _HelpTopicData {
  const _HelpTopicData({
    required this.id,
    required this.title,
    required this.summary,
    required this.details,
    required this.icon,
  });

  final String id;
  final String title;
  final String summary;
  final String details;
  final IconData icon;
}

class _HelpGroup extends StatelessWidget {
  const _HelpGroup({required this.data});

  final _HelpGroupData data;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          data.title,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w700,
              ),
        ),
        const SizedBox(height: AppUiTokens.compactGap),
        Card(
          clipBehavior: Clip.antiAlias,
          child: Column(
            children: [
              for (var index = 0; index < data.topics.length; index++) ...[
                _HelpTopic(topic: data.topics[index]),
                if (index != data.topics.length - 1) const Divider(),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _HelpTopic extends StatelessWidget {
  const _HelpTopic({required this.topic});

  final _HelpTopicData topic;

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      key: Key(topic.id),
      leading: Icon(topic.icon),
      title: Text(
        topic.title,
        style: Theme.of(context).textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w600,
            ),
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 3),
        child: Text(
          topic.summary,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
      ),
      childrenPadding: const EdgeInsets.fromLTRB(56, 0, 20, 18),
      expandedCrossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          topic.details,
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      ],
    );
  }
}
