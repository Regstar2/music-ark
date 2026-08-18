part of 'matching_workspace_page.dart';

class _MatchingSummary extends StatelessWidget {
  const _MatchingSummary({required this.summary, required this.l10n});

  final Map<String, dynamic> summary;
  final AppLocalizations l10n;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
        key: const Key('matching-summary'),
        builder: (context, constraints) {
          final columns = constraints.maxWidth >= 1100
              ? 5
              : constraints.maxWidth >= 720
                  ? 3
                  : 2;
          final gap = AppUiTokens.compactGap;
          final width = (constraints.maxWidth - gap * (columns - 1)) / columns;
          final metrics = [
            _MetricData(
              const Key('matching-summary-yandex'),
              l10n.matchingSummaryYandex,
              _asInt(summary['yandexTracks']),
              Icons.cloud_outlined,
            ),
            _MetricData(
              const Key('matching-summary-local'),
              l10n.matchingSummaryLocal,
              _asInt(summary['localTracks']),
              Icons.library_music_outlined,
            ),
            _MetricData(
              const Key('matching-summary-matched'),
              l10n.matchingSummaryMatched,
              _asInt(summary['matched']),
              Icons.check_circle_outline,
            ),
            _MetricData(
              const Key('matching-summary-conflict'),
              l10n.matchingSummaryConflict,
              _asInt(summary['conflicts']),
              Icons.rule_folder_outlined,
            ),
            _MetricData(
              const Key('matching-summary-unmatched'),
              l10n.matchingSummaryUnmatched,
              _asInt(summary['unmatched']),
              Icons.link_off_outlined,
            ),
          ];
          return Wrap(
            spacing: gap,
            runSpacing: gap,
            children: [
              for (final metric in metrics)
                SizedBox(
                  width: width,
                  child: _MetricCard(data: metric),
                ),
            ],
          );
        },
      );
}

class _MetricData {
  const _MetricData(this.key, this.label, this.value, this.icon);
  final Key key;
  final String label;
  final int value;
  final IconData icon;
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.data});
  final _MetricData data;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      key: data.key,
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            Icon(data.icon, color: scheme.onSurfaceVariant),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    data.label,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.labelMedium?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${data.value}',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w700,
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

class _InfoBanner extends StatelessWidget {
  const _InfoBanner({
    super.key,
    required this.icon,
    required this.text,
    this.tonal = false,
  });

  final IconData icon;
  final String text;
  final bool tonal;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: tonal ? scheme.surfaceContainerHighest : scheme.secondaryContainer,
        borderRadius: AppUiTokens.smallRadius,
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        child: Row(
          children: [
            Icon(
              icon,
              size: 18,
              color: tonal
                  ? scheme.onSurfaceVariant
                  : scheme.onSecondaryContainer,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                text,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: tonal
                          ? scheme.onSurfaceVariant
                          : scheme.onSecondaryContainer,
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({super.key, required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: AppUiTokens.smallRadius,
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        child: Row(
          children: [
            Icon(Icons.error_outline, size: 18, color: scheme.onErrorContainer),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                text,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: scheme.onErrorContainer,
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({
    super.key,
    required this.label,
    required this.selected,
    required this.onSelected,
  });

  final String label;
  final bool selected;
  final VoidCallback onSelected;

  @override
  Widget build(BuildContext context) => ChoiceChip(
        label: Text(label),
        selected: selected,
        showCheckmark: true,
        onSelected: (_) => onSelected(),
      );
}

class _MatchingTableHeader extends StatelessWidget {
  const _MatchingTableHeader({required this.l10n});
  final AppLocalizations l10n;

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.labelMedium?.copyWith(
          fontWeight: FontWeight.w700,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        );
    return ColoredBox(
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Row(
          children: [
            Expanded(
              flex: 34,
              child: Text(l10n.matchingColumnYandex, style: style),
            ),
            const SizedBox(width: 12),
            Expanded(
              flex: 38,
              child: Text(l10n.matchingColumnLocal, style: style),
            ),
            const SizedBox(width: 12),
            Expanded(
              flex: 12,
              child: Text(l10n.matchingColumnConfidence, style: style),
            ),
            const SizedBox(width: 12),
            Expanded(
              flex: 18,
              child: Text(l10n.matchingColumnStatus, style: style),
            ),
          ],
        ),
      ),
    );
  }
}

class _MatchingResultRow extends StatelessWidget {
  const _MatchingResultRow({
    required this.row,
    required this.l10n,
    required this.onTap,
  });

  final Map<String, dynamic> row;
  final AppLocalizations l10n;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final provider = _asMap(row['provider']);
    final local = row['local'] is Map
        ? _asMap(row['local'])
        : const <String, dynamic>{};
    final status = '${row['status'] ?? ''}';
    final variant = row['variant'] is Map
        ? _asMap(row['variant'])
        : const <String, dynamic>{};
    final confidence =
        (_asDouble(row['confidence']) * 100).round().clamp(0, 100).toInt();

    return Semantics(
      button: true,
      label: '${_artistText(provider['artists'], l10n.yandexUnknownArtist)} — '
          '${provider['title'] ?? l10n.yandexUnknownTitle}',
      child: InkWell(
        key: Key('matching-row-${row['externalId']}'),
        onTap: onTap,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 88),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Expanded(
                  flex: 34,
                  child: _TrackCell(
                    icon: Icons.cloud_outlined,
                    title:
                        '${_artistText(provider['artists'], l10n.yandexUnknownArtist)} — '
                        '${provider['title'] ?? l10n.yandexUnknownTitle}',
                    secondary:
                        '${provider['album_title'] ?? provider['album'] ?? ''}'
                            .trim(),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 38,
                  child: local.isEmpty
                      ? _MissingLocalCell(label: l10n.matchingLocalNotFound)
                      : _TrackCell(
                          icon: Icons.audio_file_outlined,
                          title:
                              '${_artistText(local['artists'], l10n.localUnknownArtist)} — '
                              '${local['title'] ?? l10n.localUnknownTrack}',
                          secondary: '${local['path'] ?? ''}',
                          tooltip: '${local['path'] ?? ''}',
                        ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 12,
                  child: _ConfidenceCell(
                    confidence: confidence,
                    showMeter: status != 'unmatched',
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 18,
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _StatusBadge(
                          label: _matchingStatusLabel(l10n, status),
                          tone: _matchingTone(status),
                        ),
                        if (status == 'matched') ...[
                          const SizedBox(height: 5),
                          _StatusBadge(
                            key: Key('variant-badge-${row['externalId']}'),
                            label: _variantLabel(
                              l10n,
                              '${variant['variantStatus'] ?? 'not_checked'}',
                            ),
                            tone: _variantTone(
                              '${variant['variantStatus'] ?? 'not_checked'}',
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _TrackCell extends StatelessWidget {
  const _TrackCell({
    required this.icon,
    required this.title,
    required this.secondary,
    this.tooltip,
  });

  final IconData icon;
  final String title;
  final String secondary;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final secondaryText = Text(
      secondary.isEmpty ? '—' : secondary,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
    );
    return Row(
      children: [
        Container(
          width: AppUiTokens.artworkSize,
          height: AppUiTokens.artworkSize,
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            borderRadius: AppUiTokens.smallRadius,
          ),
          alignment: Alignment.center,
          child: Icon(
            icon,
            size: 22,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
              ),
              const SizedBox(height: 4),
              if (tooltip != null && tooltip!.isNotEmpty)
                Tooltip(message: tooltip!, child: secondaryText)
              else
                secondaryText,
            ],
          ),
        ),
      ],
    );
  }
}

class _MissingLocalCell extends StatelessWidget {
  const _MissingLocalCell({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) => Row(
        children: [
          Container(
            width: AppUiTokens.artworkSize,
            height: AppUiTokens.artworkSize,
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.errorContainer,
              borderRadius: AppUiTokens.smallRadius,
            ),
            alignment: Alignment.center,
            child: Icon(
              Icons.link_off_outlined,
              color: Theme.of(context).colorScheme.onErrorContainer,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ),
        ],
      );
}

class _ConfidenceCell extends StatelessWidget {
  const _ConfidenceCell({required this.confidence, required this.showMeter});

  final int confidence;
  final bool showMeter;

  @override
  Widget build(BuildContext context) {
    if (!showMeter) {
      return Text(
        '—',
        key: const Key('matching-confidence-unmatched'),
        style: Theme.of(context).textTheme.titleMedium,
      );
    }
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '$confidence%',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w700,
              ),
        ),
        const SizedBox(height: 7),
        SizedBox(
          width: 96,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              key: const Key('matching-confidence-meter'),
              value: confidence / 100,
              minHeight: 6,
            ),
          ),
        ),
      ],
    );
  }
}

enum _BadgeTone {
  matched,
  conflict,
  unmatched,
  same,
  altered,
  different,
  neutral,
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({super.key, required this.label, required this.tone});

  final String label;
  final _BadgeTone tone;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (background, foreground) = switch (tone) {
      _BadgeTone.matched =>
        (scheme.primaryContainer, scheme.onPrimaryContainer),
      _BadgeTone.conflict =>
        (scheme.tertiaryContainer, scheme.onTertiaryContainer),
      _BadgeTone.unmatched => (scheme.errorContainer, scheme.onErrorContainer),
      _BadgeTone.same =>
        (scheme.secondaryContainer, scheme.onSecondaryContainer),
      _BadgeTone.altered =>
        (scheme.tertiaryContainer, scheme.onTertiaryContainer),
      _BadgeTone.different => (scheme.errorContainer, scheme.onErrorContainer),
      _BadgeTone.neutral =>
        (scheme.surfaceContainerHighest, scheme.onSurfaceVariant),
    };
    return DecoratedBox(
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
        child: Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: foreground,
              ),
        ),
      ),
    );
  }
}

class _MatchingTableFooter extends StatelessWidget {
  const _MatchingTableFooter({
    required this.shown,
    required this.total,
    required this.loadingMore,
    required this.hasMore,
    required this.l10n,
    required this.onLoadMore,
  });

  final int shown;
  final int total;
  final bool loadingMore;
  final bool hasMore;
  final AppLocalizations l10n;
  final VoidCallback onLoadMore;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        child: Row(
          children: [
            Text(
              l10n.matchingShownCount(shown, total),
              key: const Key('matching-shown-count'),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
            const Spacer(),
            if (hasMore)
              OutlinedButton(
                key: const Key('matching-load-more'),
                onPressed: loadingMore ? null : onLoadMore,
                child: Text(
                  loadingMore ? l10n.matchingLoadingMore : l10n.localLoadMore,
                ),
              ),
          ],
        ),
      );
}

class _EmptyMatchingState extends StatelessWidget {
  const _EmptyMatchingState({super.key, required this.title, required this.body});

  final String title;
  final String body;

  @override
  Widget build(BuildContext context) => Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.compare_arrows_outlined,
                size: 42,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
              const SizedBox(height: 12),
              Text(
                title,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 6),
              Text(
                body,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
            ],
          ),
        ),
      );
}
