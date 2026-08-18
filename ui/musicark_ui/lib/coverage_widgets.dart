part of 'coverage_page.dart';

class _Summary extends StatelessWidget {
  const _Summary({
    required this.summary,
    required this.expanded,
    required this.onToggleDetails,
  });

  final Map<String, dynamic> summary;
  final bool expanded;
  final VoidCallback onToggleDetails;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final scheme = Theme.of(context).colorScheme;
    final coverage = _asDouble(summary['coveragePercent']).clamp(0, 100) / 100;
    final variants = summary['variantVerification'] is Map
        ? Map<String, dynamic>.from(summary['variantVerification'] as Map)
        : const <String, dynamic>{};

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 4),
      child: Card(
        key: const Key('coverage-summary'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final coverageWidth = constraints.maxWidth < 240
                  ? constraints.maxWidth
                  : 240.0;
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      SizedBox(
                        width: coverageWidth,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              l10n.coverageSummaryTitle,
                              style: Theme.of(context).textTheme.labelLarge,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${_asDouble(summary['coveragePercent']).toStringAsFixed(1)}%',
                              key: const Key('coverage-summary-percent'),
                              style: Theme.of(context).textTheme.headlineSmall,
                            ),
                            const SizedBox(height: 8),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: LinearProgressIndicator(
                                value: coverage,
                                minHeight: 7,
                              ),
                            ),
                          ],
                        ),
                      ),
                      _SummaryMetric(
                        label: l10n.coverageSummaryTotal,
                        value: _asInt(summary['total']),
                        background: scheme.surfaceContainerHighest,
                        foreground: scheme.onSurface,
                      ),
                      _SummaryMetric(
                        label: l10n.coverageSummaryCovered,
                        value: _asInt(summary['covered']),
                        background: scheme.secondaryContainer,
                        foreground: scheme.onSecondaryContainer,
                      ),
                      _SummaryMetric(
                        label: l10n.coverageSummaryMissing,
                        value: _asInt(summary['missing']),
                        background: scheme.errorContainer,
                        foreground: scheme.onErrorContainer,
                      ),
                      _SummaryMetric(
                        label: l10n.coverageSummaryNotAnalyzed,
                        value: _asInt(summary['notAnalyzed']),
                        background: scheme.tertiaryContainer,
                        foreground: scheme.onTertiaryContainer,
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      key: const Key('coverage-analysis-toggle'),
                      onPressed: onToggleDetails,
                      icon: Icon(
                        expanded ? Icons.expand_less : Icons.expand_more,
                        size: 18,
                      ),
                      label: Text(
                        expanded
                            ? l10n.coverageHideAnalysisDetails
                            : l10n.coverageShowAnalysisDetails,
                      ),
                    ),
                  ),
                  if (expanded) ...[
                    const Divider(),
                    Wrap(
                      key: const Key('coverage-analysis-details'),
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _AnalysisPill(
                          label:
                              '${l10n.coverageMatchingAnalyzed}: ${_asDouble(summary['matchingAnalyzedPercent']).toStringAsFixed(1)}%',
                        ),
                        _AnalysisPill(
                          label:
                              '${l10n.coverageNeedsReview}: ${_asInt(summary['needsReview'])}',
                        ),
                        _AnalysisPill(
                          label:
                              '${l10n.matchingVariantSame}: ${_asInt(variants['same'])}',
                        ),
                        _AnalysisPill(
                          label:
                              '${l10n.matchingVariantAltered}: ${_asInt(variants['altered'])}',
                        ),
                        _AnalysisPill(
                          label:
                              '${l10n.matchingVariantDifferent}: ${_asInt(variants['differentVersion'])}',
                        ),
                        _AnalysisPill(
                          label:
                              '${l10n.matchingVariantUncertain}: ${_asInt(variants['uncertain'])}',
                        ),
                        _AnalysisPill(
                          label:
                              '${l10n.matchingVariantNotChecked}: ${_asInt(variants['notChecked'])}',
                        ),
                      ],
                    ),
                  ],
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

class _SummaryMetric extends StatelessWidget {
  const _SummaryMetric({
    required this.label,
    required this.value,
    required this.background,
    required this.foreground,
  });

  final String label;
  final int value;
  final Color background;
  final Color foreground;

  @override
  Widget build(BuildContext context) => Container(
        width: 142,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '$value',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: foreground,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: foreground,
                  ),
            ),
          ],
        ),
      );
}

class _AnalysisPill extends StatelessWidget {
  const _AnalysisPill({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(label, style: Theme.of(context).textTheme.labelMedium),
    );
  }
}

class _StatusTab extends StatelessWidget {
  const _StatusTab({
    super.key,
    required this.selected,
    required this.label,
    required this.count,
    required this.onTap,
  });

  final bool selected;
  final String label;
  final int count;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final background = selected ? scheme.primaryContainer : scheme.surface;
    final foreground = selected ? scheme.onPrimaryContainer : scheme.onSurface;
    return Semantics(
      selected: selected,
      button: true,
      child: Material(
        color: background,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: BorderSide(
            color: selected ? scheme.primary : scheme.outlineVariant,
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  label,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: foreground,
                        fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                      ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                  decoration: BoxDecoration(
                    color: selected
                        ? scheme.surfaceContainerLow
                        : scheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    '$count',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: foreground,
                          fontWeight: FontWeight.w700,
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

