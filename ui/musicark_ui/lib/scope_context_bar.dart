import 'package:flutter/material.dart';

import 'app_localizations_ext.dart';
import 'app_ui_tokens.dart';
import 'v0111_localizations_ext.dart';

/// Persistent, responsive context for screens whose results depend on a
/// Yandex collection and/or a local root selection.
class ScopeContextBar extends StatelessWidget {
  const ScopeContextBar({
    super.key,
    required this.collection,
    required this.localFolders,
    this.localFoldersTooltip,
    this.localNotRequired = false,
  });

  final String collection;
  final String localFolders;
  final String? localFoldersTooltip;
  final bool localNotRequired;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final colors = Theme.of(context).colorScheme;
    return Container(
      key: const Key('scope-context-bar'),
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: colors.surfaceContainerLow,
        borderRadius: AppUiTokens.mediumRadius,
        border: Border.all(color: colors.outlineVariant),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 640;
          final collectionItem = _ScopeContextItem(
            key: const Key('scope-context-collection'),
            icon: Icons.library_music_outlined,
            label: l10n.v0111Collection,
            value: collection,
          );
          final folderItem = _ScopeContextItem(
            key: const Key('scope-context-folder'),
            icon: localNotRequired ? Icons.folder_off_outlined : Icons.folder_outlined,
            label: l10n.v0111LocalFolder,
            value: localFolders,
            tooltip: localFoldersTooltip,
          );
          if (compact) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                collectionItem,
                const SizedBox(height: 8),
                folderItem,
              ],
            );
          }
          return Row(
            children: [
              Expanded(child: collectionItem),
              const SizedBox(width: AppUiTokens.sectionGap),
              Expanded(child: folderItem),
            ],
          );
        },
      ),
    );
  }
}

class _ScopeContextItem extends StatelessWidget {
  const _ScopeContextItem({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    this.tooltip,
  });

  final IconData icon;
  final String label;
  final String value;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final child = Row(
      children: [
        Icon(icon, size: 19, color: colors.onSurfaceVariant),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: colors.onSurfaceVariant,
                ),
              ),
              Text(
                value,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ],
    );
    final message = (tooltip ?? value).trim();
    if (message.isEmpty) return child;
    return Tooltip(message: message, child: child);
  }
}
