part of 'matching_detail_dialog.dart';

class _TrackComparisonTable extends StatelessWidget {
  const _TrackComparisonTable({
    required this.provider,
    required this.local,
    required this.providerLabel,
    required this.localLabel,
    required this.labelsBusy,
    required this.onProviderLabelChanged,
    required this.onLocalLabelChanged,
  });

  final Map<String, dynamic> provider;
  final Map<String, dynamic> local;
  final String providerLabel;
  final String localLabel;
  final bool labelsBusy;
  final ValueChanged<String> onProviderLabelChanged;
  final ValueChanged<String>? onLocalLabelChanged;

  @override
  Widget build(BuildContext context) {
    final rows = <TableRow>[
      _tableRow(
        context,
        'Параметр',
        const Text('Яндекс Музыка', style: TextStyle(fontWeight: FontWeight.bold)),
        const Text('Локальный файл', style: TextStyle(fontWeight: FontWeight.bold)),
        header: true,
      ),
      _tableRow(
        context,
        'Название',
        Text('${provider['title'] ?? '—'}'),
        Text('${local['title'] ?? '—'}'),
      ),
      _tableRow(
        context,
        'Исполнитель',
        Text(_artistText(provider['artists'], 'Неизвестный исполнитель')),
        Text(local.isEmpty
            ? '—'
            : _artistText(local['artists'], 'Неизвестный исполнитель')),
      ),
      _tableRow(
        context,
        'Альбом',
        Text('${provider['album_title'] ?? provider['album'] ?? '—'}'),
        Text('${local['album'] ?? '—'}'),
      ),
      _tableRow(
        context,
        'Длительность',
        Text(_duration(provider['duration_seconds'])),
        Text(_duration(local['durationSeconds'])),
      ),
      _tableRow(
        context,
        'Ярлык',
        _LabelSelector(
          key: const Key('matching-provider-label'),
          value: providerLabel,
          enabled: !labelsBusy,
          onChanged: onProviderLabelChanged,
        ),
        local.isEmpty
            ? const Text('—')
            : _LabelSelector(
                key: const Key('matching-local-label'),
                value: localLabel,
                enabled: !labelsBusy,
                onChanged: onLocalLabelChanged!,
              ),
      ),
      _tableRow(
        context,
        'Идентификатор',
        const Text('Трек Яндекс Музыки'),
        Text(local.isEmpty ? '—' : '#${local['id'] ?? '—'}'),
      ),
      _tableRow(
        context,
        'Расположение',
        const Text('—'),
        SelectableText('${local['path'] ?? '—'}'),
      ),
    ];
    return Table(
      key: const Key('matching-track-comparison-table'),
      border: TableBorder.all(color: Theme.of(context).dividerColor),
      columnWidths: const {
        0: FlexColumnWidth(1.05),
        1: FlexColumnWidth(2.2),
        2: FlexColumnWidth(2.2),
      },
      defaultVerticalAlignment: TableCellVerticalAlignment.middle,
      children: rows,
    );
  }

  static TableRow _tableRow(
    BuildContext context,
    String label,
    Widget provider,
    Widget local, {
    bool header = false,
  }) {
    Widget cell(Widget child) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
          child: child,
        );
    return TableRow(
      decoration: header
          ? BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
            )
          : null,
      children: [
        cell(
          Text(
            label,
            style: header ? const TextStyle(fontWeight: FontWeight.bold) : null,
          ),
        ),
        cell(provider),
        cell(local),
      ],
    );
  }
}

class _LabelSelector extends StatelessWidget {
  const _LabelSelector({
    super.key,
    required this.value,
    required this.enabled,
    required this.onChanged,
  });

  final String value;
  final bool enabled;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) => DropdownButton<String>(
        value: const {'', 'original', 'censored'}.contains(value) ? value : '',
        isExpanded: true,
        items: const [
          DropdownMenuItem(value: '', child: Text('Без ярлыка')),
          DropdownMenuItem(value: 'original', child: Text('ОРИГИНАЛ')),
          DropdownMenuItem(value: 'censored', child: Text('ЦЕНЗУРА')),
        ],
        onChanged: enabled
            ? (next) {
                if (next != null) onChanged(next);
              }
            : null,
      );
}

class _VariantDetail extends StatelessWidget {
  const _VariantDetail({required this.variant});
  final Map<String, dynamic> variant;

  @override
  Widget build(BuildContext context) {
    final status = '${variant['variantStatus'] ?? 'not_checked'}';
    final similarity = variant['audioSimilarity'];
    final reasons = variant['variantReasons'] is List
        ? List<dynamic>.from(variant['variantReasons'] as List)
        : const <dynamic>[];
    final segments = _mapItems(variant['alteredSegments']);
    return Column(
      key: const Key('variant-detail'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Результат: ${_variantLabel(context.l10n, status)}',
          key: const Key('variant-detail-status'),
        ),
        Text(
          similarity == null
              ? 'Сходство аудио: —'
              : 'Сходство аудио: ${(_asDouble(similarity) * 100).round()}%',
        ),
        if (reasons.isNotEmpty) ...[
          const SizedBox(height: 6),
          const Text('Признаки:'),
          for (final reason in reasons)
            Text('• ${AppStrings.variantReason(reason.toString())}'),
        ],
        if (segments.isNotEmpty) ...[
          const SizedBox(height: 6),
          const Text('Изменённые участки:'),
          for (var index = 0; index < segments.length; index++)
            Text(
              '${_formatSeconds(_asDouble(segments[index]['startSeconds']))}–'
              '${_formatSeconds(_asDouble(segments[index]['endSeconds']))} '
              '(${(_asDouble(segments[index]['meanSimilarity']) * 100).round()}%)',
              key: Key('variant-altered-region-$index'),
            ),
        ],
      ],
    );
  }
}

class _CandidateCard extends StatelessWidget {
  const _CandidateCard({
    required this.candidate,
    required this.busy,
    required this.onAccept,
    required this.onReject,
  });

  final Map<String, dynamic> candidate;
  final bool busy;
  final VoidCallback onAccept;
  final VoidCallback onReject;

  @override
  Widget build(BuildContext context) {
    final local = _asMap(candidate['local']);
    final confidence = (_asDouble(candidate['confidence']) * 100).round();
    final id = _asInt(candidate['localFileId']);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Кандидат ${candidate['rank']} · уверенность $confidence% · '
                    '${_artistText(local['artists'], 'Неизвестный исполнитель')} — '
                    '${local['title'] ?? ''}',
                  ),
                  Text(
                    '${local['album'] ?? '—'} · ${_duration(local['durationSeconds'])}',
                  ),
                  Text('${local['path'] ?? ''}'),
                ],
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(
              key: Key('matching-accept-$id'),
              onPressed: busy ? null : onAccept,
              child: const Text('Подтвердить'),
            ),
            const SizedBox(width: 8),
            OutlinedButton(
              key: Key('matching-reject-$id'),
              onPressed: busy ? null : onReject,
              child: const Text('Это не совпадение'),
            ),
          ],
        ),
      ),
    );
  }
}
