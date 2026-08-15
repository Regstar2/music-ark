part of 'coverage_page.dart';

class _Summary extends StatelessWidget {
  const _Summary({required this.summary});

  final Map<String, dynamic> summary;

  @override
  Widget build(BuildContext context) {
    final total = _asInt(summary['total']);
    final covered = _asInt(summary['covered']);
    final missing = _asInt(summary['missing']);
    final review = _asInt(summary['needsReview']);
    final unknown = _asInt(summary['notAnalyzed']);
    final coverage = _asDouble(summary['coveragePercent']);
    final analyzed = _asDouble(summary['matchingAnalyzedPercent']);
    final variants = summary['variantVerification'] is Map
        ? Map<String, dynamic>.from(summary['variantVerification'] as Map)
        : const <String, dynamic>{};

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 4),
      child: Card(
        key: const Key('coverage-summary'),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Wrap(
            spacing: 24,
            runSpacing: 8,
            children: [
              Text('Yandex: $total'),
              Text('Локально найдено: $covered'),
              Text('Отсутствует: $missing'),
              Text('Требует проверки: $review'),
              Text('Не анализировалось: $unknown'),
              Text('Local coverage: ${coverage.toStringAsFixed(1)}%'),
              Text('Matching analyzed: ${analyzed.toStringAsFixed(1)}%'),
              Text(
                'Variant — Same ${_asInt(variants['same'])}, '
                'Altered ${_asInt(variants['altered'])}, '
                'Different ${_asInt(variants['differentVersion'])}, '
                'Uncertain ${_asInt(variants['uncertain'])}, '
                'Not checked ${_asInt(variants['notChecked'])}',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({
    super.key,
    required this.selected,
    required this.label,
    required this.onSelected,
  });

  final bool selected;
  final String label;
  final VoidCallback onSelected;

  @override
  Widget build(BuildContext context) => ChoiceChip(
    selected: selected,
    label: Text(label),
    onSelected: (_) => onSelected(),
  );
}

class _CoverageRow extends StatelessWidget {
  const _CoverageRow({
    super.key,
    required this.item,
    required this.selected,
    required this.onSelectionChanged,
    required this.onOpen,
    required this.onWanted,
    required this.onIgnored,
    required this.onReset,
    required this.onOpenMatching,
  });

  final Map<String, dynamic> item;
  final bool selected;
  final ValueChanged<bool>? onSelectionChanged;
  final VoidCallback onOpen;
  final VoidCallback? onWanted;
  final VoidCallback? onIgnored;
  final VoidCallback? onReset;
  final VoidCallback? onOpenMatching;

  @override
  Widget build(BuildContext context) {
    final provider = item['provider'] is Map
        ? Map<String, dynamic>.from(item['provider'] as Map)
        : const <String, dynamic>{};
    final artists = provider['artists'] is List
        ? (provider['artists'] as List).join(', ')
        : '';
    final title = (provider['title'] ?? '').toString();
    final album =
        (provider['album_title'] ?? provider['album'] ?? '').toString();
    final status = (item['coverageStatus'] ?? '').toString();
    final action = (item['userAction'] ?? 'unreviewed').toString();
    final variant = item['variantStatus']?.toString();
    final collections = _maps(item['collections']);

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: InkWell(
        onTap: onOpen,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (onSelectionChanged != null)
                Checkbox(
                  key: ValueKey('coverage-select-${item['externalId']}'),
                  value: selected,
                  onChanged: (value) => onSelectionChanged!(value ?? false),
                ),
              Expanded(
                flex: 5,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '$artists — $title',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    if (album.isNotEmpty) Text(album),
                    const SizedBox(height: 4),
                    Wrap(
                      spacing: 8,
                      runSpacing: 4,
                      children: collections
                          .map(
                            (collection) => Text(
                              collection['id'] == 'liked'
                                  ? '♥ Мне нравится'
                                  : '▤ ${collection['title']}',
                            ),
                          )
                          .toList(),
                    ),
                  ],
                ),
              ),
              SizedBox(
                width: 190,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _StatusLabel(status: status),
                    if (status == 'covered' && variant != null)
                      _VariantLabel(status: variant),
                    if ((status == 'needs_review' || status == 'not_analyzed') &&
                        onOpenMatching != null)
                      TextButton(
                        key: ValueKey(
                          'coverage-open-matching-${item['externalId']}',
                        ),
                        onPressed: onOpenMatching,
                        child: const Text('Открыть в сопоставлении'),
                      ),
                  ],
                ),
              ),
              if (onWanted != null)
                SizedBox(
                  width: 260,
                  child: Wrap(
                    alignment: WrapAlignment.end,
                    spacing: 4,
                    children: [
                      TextButton(
                        key: ValueKey('coverage-wanted-${item['externalId']}'),
                        onPressed: action == 'wanted' ? null : onWanted,
                        child: const Text('Нужен'),
                      ),
                      TextButton(
                        key: ValueKey('coverage-ignored-${item['externalId']}'),
                        onPressed: action == 'ignored' ? null : onIgnored,
                        child: const Text('Игнорировать'),
                      ),
                      if (action != 'unreviewed')
                        IconButton(
                          key: ValueKey('coverage-reset-${item['externalId']}'),
                          tooltip: 'Сбросить решение',
                          onPressed: onReset,
                          icon: const Icon(Icons.undo),
                        ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusLabel extends StatelessWidget {
  const _StatusLabel({required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final label = switch (status) {
      'covered' => 'Локально найдено',
      'missing' => 'Missing',
      'needs_review' => 'Требует проверки',
      'not_analyzed' => 'Не анализировалось',
      _ => status,
    };
    return Text(label, style: Theme.of(context).textTheme.labelLarge);
  }
}

class _VariantLabel extends StatelessWidget {
  const _VariantLabel({required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final label = switch (status) {
      'same' => 'Та же версия',
      'altered' => 'Изменённая запись',
      'different_version' => 'Другая версия локально',
      'uncertain' => 'Версия требует проверки',
      'not_checked' => 'Версия не проверена',
      _ => status,
    };
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Text(label),
    );
  }
}

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
      child: Row(
        children: [
          Text('$count выбрано'),
          const SizedBox(width: 16),
          TextButton(
            key: const Key('coverage-bulk-wanted'),
            onPressed: onWanted,
            child: const Text('Нужны'),
          ),
          TextButton(
            key: const Key('coverage-bulk-ignored'),
            onPressed: onIgnored,
            child: const Text('Игнорировать'),
          ),
          TextButton(
            key: const Key('coverage-bulk-reset'),
            onPressed: onReset,
            child: const Text('Сбросить'),
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
    if (total == 0) return const SizedBox(height: 8);
    final start = offset + 1;
    final end = (offset + limit).clamp(0, total);
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 4, 24, 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          Text('$start–$end из $total'),
          IconButton(
            key: const Key('coverage-page-previous'),
            onPressed: onPrevious,
            icon: const Icon(Icons.chevron_left),
          ),
          IconButton(
            key: const Key('coverage-page-next'),
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
              child: const Text('Открыть «Сопоставление»'),
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

    return AlertDialog(
      key: const Key('coverage-detail'),
      title: Text('${provider['title'] ?? ''}'),
      content: SizedBox(
        width: 680,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Yandex', style: Theme.of(context).textTheme.titleMedium),
              Text('Исполнители: $artists'),
              Text('Альбом: ${provider['album_title'] ?? provider['album'] ?? ''}'),
              Text('Длительность: ${provider['duration_seconds'] ?? '—'}'),
              Text('External ID: ${track['externalId'] ?? ''}'),
              Text(
                'Коллекции: ${collections.map((item) => item['title']).join(', ')}',
              ),
              const Divider(),
              Text('Matching', style: Theme.of(context).textTheme.titleMedium),
              Text('Coverage: $coverageStatus'),
              Text('Status: ${matching?['status'] ?? 'NOT ANALYZED'}'),
              Text('Reason: ${matching?['reason'] ?? track['reason'] ?? '—'}'),
              if (matching?['confidence'] != null)
                Text('Confidence: ${matching!['confidence']}'),
              const Divider(),
              Text('Variant', style: Theme.of(context).textTheme.titleMedium),
              Text(
                variant['applicable'] == true
                    ? 'Status: ${variant['status'] ?? 'not_checked'}'
                    : 'N/A — no accepted local identity',
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
            child: const Text('Открыть в сопоставлении'),
          ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Закрыть'),
        ),
      ],
    );
  }
}

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
