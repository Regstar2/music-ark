import 'package:flutter/material.dart';

import 'app_localizations_ext.dart';

class HelpPage extends StatelessWidget {
  const HelpPage({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final topics = [
      (l10n.helpYandexTitle, l10n.helpYandexBody, Icons.cloud_outlined),
      (l10n.helpLocalTitle, l10n.helpLocalBody, Icons.library_music_outlined),
      (l10n.helpMatchingTitle, l10n.helpMatchingBody, Icons.compare_arrows),
      (l10n.helpMissingTitle, l10n.helpMissingBody, Icons.playlist_remove),
      (l10n.helpDownloadsTitle, l10n.helpDownloadsBody, Icons.download_outlined),
      (l10n.helpSyncTitle, l10n.helpSyncBody, Icons.sync),
      (l10n.helpMetadataTitle, l10n.helpMetadataBody, Icons.edit_note_outlined),
    ];
    return Scaffold(
      key: const Key('help-page'),
      appBar: AppBar(title: Text(l10n.helpTitle)),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(l10n.helpIntro, style: Theme.of(context).textTheme.bodyLarge),
          const SizedBox(height: 16),
          for (final topic in topics)
            Card(
              child: ExpansionTile(
                leading: Icon(topic.$3),
                title: Text(topic.$1),
                childrenPadding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                expandedCrossAxisAlignment: CrossAxisAlignment.start,
                children: [Text(topic.$2)],
              ),
            ),
        ],
      ),
    );
  }
}
