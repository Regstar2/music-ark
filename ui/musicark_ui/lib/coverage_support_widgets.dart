part of 'coverage_page.dart';

class _BulkBar extends StatelessWidget {
  const _BulkBar({
    required this.count,
    required this.onWanted,
    required this.onIgnored,
    required this.onReset,
  });

  final int count;
  final VoidCallback onWanted;
  final VoidCallback onIgnored;
  final VoidCallback onReset;

  @override
  Widget build(BuildContext context) => Material(
        key: const Key('coverage-bulk-bar'),
        color: Theme.of(context).colorScheme.secondaryContainer,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 6),
          child: Wrap(
            spacing: 8,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                context.l10n.coverageBulkSelected(count),
                style: Theme.of(context).textTheme.labelLarge,
              ),
              TextButton(
                key: const Key('coverage-bulk-wanted'),
                onPressed: onWanted,
                child: Text(context.l10n.coverageBulkWanted),
              ),
              TextButton(
                key: const Key('coverage-bulk-ignored'),
                onPressed: onIgnored,
                child: Text(context.l10n.coverageIgnore),
              ),
              TextButton(
                key: const Key('coverage-bulk-reset'),
                onPressed: onReset,
                child: Text(context.l10n.coverageBulkReset),
              ),
            ],
          ),
        ),
      );
}

class _Pagination extends StatelessWidget {
  const _Pagination({
    required this.offset,
    required this.limit,
    required this.total,
    required this.onPrevious,
    required this.onNext,
  });

  final int offset;
  final int limit;
  final int total;
  final VoidCallback? onPrevious;
  final VoidCallback? onNext;

  @override
  Widget build(BuildContext context) {
    final start = offset + 1;
    final end = (offset + limit).clamp(0, total);
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 4, 24, 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          Text(context.l10n.coveragePagination(start, end, total)),
          IconButton(
            key: const Key('coverage-page-previous'),
            tooltip: context.l10n.coveragePreviousPage,
            onPressed: onPrevious,
            icon: const Icon(Icons.chevron_left),
          ),
          IconButton(
            key: const Key('coverage-page-next'),
            tooltip: context.l10n.coverageNextPage,
            onPressed: onNext,
            icon: const Icon(Icons.chevron_right),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({
    required this.title,
    this.subtitle,
    this.actionLabel,
    this.onAction,
    this.secondaryAction,
  });

  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;
  final VoidCallback? secondaryAction;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(title, textAlign: TextAlign.center),
              if (subtitle != null) ...[
                const SizedBox(height: 8),
                Text(subtitle!, textAlign: TextAlign.center),
              ],
              if (actionLabel != null) ...[
                const SizedBox(height: 12),
                FilledButton(
                  key: const Key('coverage-run-matching'),
                  onPressed: onAction,
                  child: Text(actionLabel!),
                ),
              ],
              if (secondaryAction != null) ...[
                const SizedBox(height: 4),
                TextButton(
                  onPressed: secondaryAction,
                  child: Text(context.l10n.coverageOpenMatching),
                ),
              ],
            ],
          ),
        ),
      );
}

class _CoverageDetailsDialog extends StatelessWidget {
  const _CoverageDetailsDialog({
    required this.payload,
    required this.onOpenMatching,
  });

  final Map<String, dynamic> payload;
  final VoidCallback? onOpenMatching;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final track = payload['track'] is Map
        ? Map<String, dynamic>.from(payload['track'] as Map)
        : const <String, dynamic>{};
    final provider = track['provider'] is Map
        ? Map<String, dynamic>.from(track['provider'] as Map)
        : const <String, dynamic>{};
    final matching = payload['matching'] is Map
        ? Map<String, dynamic>.from(payload['matching'] as Map)
        : null;
    final variant = payload['variant'] is Map
        ? Map<String, dynamic>.from(payload['variant'] as Map)
        : const <String, dynamic>{};
    final artists = provider['artists'] is List
        ? (provider['artists'] as List).join(', ')
        : '';
    final collections = _maps(track['collections']);
    final coverageStatus = (track['coverageStatus'] ?? '').toString();
    final matchingStatus = (matching?['status'] ?? '').toString();

    return AlertDialog(
      key: const Key('coverage-detail'),
      title: Text('${provider['title'] ?? ''}'),
      content: SizedBox(
        width: 680,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                l10n.accountProvider,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text('${l10n.coverageDetailsArtists}: $artists'),
              Text(
                '${l10n.coverageDetailsAlbum}: ${provider['album_title'] ?? provider['album'] ?? '—'}',
              ),
              Text(
                '${l10n.coverageDetailsDuration}: ${provider['duration_seconds'] ?? '—'}',
              ),
              Text('External ID: ${track['externalId'] ?? ''}'),
              Text(
                '${l10n.coverageDetailsCollections}: ${collections.map((item) => item['title']).join(', ')}',
              ),
              const Divider(),
              Text(
                l10n.navMatching,
                key: const Key('coverage-detail-matching'),
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text(
                '${l10n.coverageDetailsCoverage}: ${_coverageStatusLabel(context, coverageStatus)}',
              ),
              Text(
                '${l10n.coverageDetailsStatus}: ${_matchingStatusLabel(context, matchingStatus)}',
              ),
              Text(
                '${l10n.coverageDetailsReason}: ${matching?['reason'] ?? track['reason'] ?? '—'}',
              ),
              if (matching?['confidence'] != null)
                Text(
                  '${l10n.coverageDetailsConfidence}: ${matching!['confidence']}',
                ),
              const Divider(),
              Text(
                l10n.coverageVariantTitle,
                key: const Key('coverage-detail-variant'),
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text(
                variant['applicable'] == true
                    ? '${l10n.coverageDetailsStatus}: ${_variantStatusLabel(context, (variant['status'] ?? 'not_checked').toString())}'
                    : l10n.coverageNoAcceptedIdentity,
              ),
            ],
          ),
        ),
      ),
      actions: [
        if ((coverageStatus == 'needs_review' ||
                coverageStatus == 'not_analyzed') &&
            onOpenMatching != null)
          TextButton(
            key: const Key('coverage-detail-open-matching'),
            onPressed: () {
              Navigator.of(context).pop();
              onOpenMatching!();
            },
            child: Text(l10n.coverageOpenMatching),
          ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(l10n.close),
        ),
      ],
    );
  }
}

String _coverageStatusLabel(BuildContext context, String status) => switch (status) {
      'covered' => context.l10n.coverageStatusCovered,
      'missing' => context.l10n.coverageStatusMissing,
      'needs_review' => context.l10n.coverageStatusReview,
      'not_analyzed' => context.l10n.coverageStatusNotAnalyzed,
      _ => context.l10n.coverageStatusUnknown,
    };

String _variantStatusLabel(BuildContext context, String status) => switch (status) {
      'same' => context.l10n.matchingVariantSame,
      'altered' => context.l10n.matchingVariantAltered,
      'different_version' => context.l10n.matchingVariantDifferent,
      'uncertain' => context.l10n.matchingVariantUncertain,
      'not_checked' => context.l10n.matchingVariantNotChecked,
      _ => context.l10n.coverageStatusUnknown,
    };

String _matchingStatusLabel(BuildContext context, String status) => switch (status) {
      'matched' => context.l10n.matchingStatusMatched,
      'conflict' => context.l10n.matchingStatusConflict,
      'unmatched' => context.l10n.matchingStatusUnmatched,
      _ => context.l10n.matchingStatusUnknown,
    };

List<Map<String, dynamic>> _maps(Object? value) {
  if (value is! List) return <Map<String, dynamic>>[];
  return value
      .whereType<Map>()
      .map((item) => Map<String, dynamic>.from(item))
      .toList();
}

int _asInt(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

double _asDouble(Object? value) {
  if (value is double) return value;
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? 0;
}
