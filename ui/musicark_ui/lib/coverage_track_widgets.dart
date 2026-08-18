part of 'coverage_page.dart';

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
    required this.onDownload,
    required this.onOpenMatching,
  });

  final Map<String, dynamic> item;
  final bool selected;
  final ValueChanged<bool>? onSelectionChanged;
  final VoidCallback onOpen;
  final VoidCallback? onWanted;
  final VoidCallback? onIgnored;
  final VoidCallback? onReset;
  final VoidCallback? onDownload;
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
    final album = (provider['album_title'] ?? provider['album'] ?? '').toString();
    final artworkUrl = (provider['artwork_url'] ?? '').toString().trim();
    final status = (item['coverageStatus'] ?? '').toString();
    final action = (item['userAction'] ?? 'unreviewed').toString();
    final variant = item['variantStatus']?.toString();
    final collections = _maps(item['collections']);
    final externalId = (item['externalId'] ?? '').toString();

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      clipBehavior: Clip.antiAlias,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 720;
          final identity = _TrackIdentity(
            externalId: externalId,
            title: title,
            artists: artists,
            album: album,
            artworkUrl: artworkUrl,
            collections: collections,
            onOpen: onOpen,
          );
          final statusArea = Wrap(
            alignment: compact ? WrapAlignment.start : WrapAlignment.end,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 8,
            runSpacing: 6,
            children: [
              _StatusBadge(status: status),
              if (status == 'covered' && variant != null)
                _VariantBadge(status: variant),
              if ((status == 'needs_review' || status == 'not_analyzed') &&
                  onOpenMatching != null)
                TextButton(
                  key: ValueKey('coverage-open-matching-$externalId'),
                  onPressed: onOpenMatching,
                  child: Text(context.l10n.coverageOpenMatching),
                ),
            ],
          );
          final Widget? actions = onWanted == null
              ? null
              : _TrackActions(
                  externalId: externalId,
                  action: action,
                  onDownload: onDownload,
                  onWanted: onWanted,
                  onIgnored: onIgnored,
                  onReset: onReset,
                );

          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: compact
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          if (onSelectionChanged != null)
                            Checkbox(
                              key: ValueKey('coverage-select-$externalId'),
                              value: selected,
                              onChanged: (value) =>
                                  onSelectionChanged!(value ?? false),
                            ),
                          Expanded(child: identity),
                        ],
                      ),
                      const SizedBox(height: 8),
                      statusArea,
                      if (actions != null) ...[
                        const SizedBox(height: 6),
                        actions,
                      ],
                    ],
                  )
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      if (onSelectionChanged != null)
                        Checkbox(
                          key: ValueKey('coverage-select-$externalId'),
                          value: selected,
                          onChanged: (value) =>
                              onSelectionChanged!(value ?? false),
                        ),
                      Expanded(child: identity),
                      const SizedBox(width: 16),
                      Flexible(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            statusArea,
                            if (actions != null) ...[
                              const SizedBox(height: 6),
                              actions,
                            ],
                          ],
                        ),
                      ),
                    ],
                  ),
          );
        },
      ),
    );
  }
}

class _TrackIdentity extends StatelessWidget {
  const _TrackIdentity({
    required this.externalId,
    required this.title,
    required this.artists,
    required this.album,
    required this.artworkUrl,
    required this.collections,
    required this.onOpen,
  });

  final String externalId;
  final String title;
  final String artists;
  final String album;
  final String artworkUrl;
  final List<Map<String, dynamic>> collections;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final secondary = [artists, album]
        .where((value) => value.trim().isNotEmpty)
        .join(' • ');
    return InkWell(
      onTap: onOpen,
      borderRadius: BorderRadius.circular(10),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            _TrackArtwork(externalId: externalId, artworkUrl: artworkUrl),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title.isEmpty ? context.l10n.yandexUnknownTitle : title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  if (secondary.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(
                      secondary,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                    ),
                  ],
                  if (collections.isNotEmpty) ...[
                    const SizedBox(height: 7),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: collections
                          .map(
                            (collection) => _CollectionBadge(
                              label: collection['id'] == 'liked'
                                  ? context.l10n.coverageLikedCollection
                                  : (collection['title'] ?? collection['id'])
                                      .toString(),
                              liked: collection['id'] == 'liked',
                            ),
                          )
                          .toList(),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TrackArtwork extends StatelessWidget {
  const _TrackArtwork({
    required this.externalId,
    required this.artworkUrl,
  });

  final String externalId;
  final String artworkUrl;

  @override
  Widget build(BuildContext context) {
    final fallback = Container(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      alignment: Alignment.center,
      child: Icon(
        Icons.music_note_rounded,
        color: Theme.of(context).colorScheme.onSurfaceVariant,
      ),
    );
    return ClipRRect(
      key: ValueKey('coverage-artwork-$externalId'),
      borderRadius: BorderRadius.circular(10),
      child: SizedBox(
        width: 68,
        height: 68,
        child: artworkUrl.isEmpty
            ? fallback
            : Image.network(
                artworkUrl,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => fallback,
                loadingBuilder: (context, child, progress) =>
                    progress == null ? child : fallback,
              ),
      ),
    );
  }
}

class _CollectionBadge extends StatelessWidget {
  const _CollectionBadge({required this.label, required this.liked});

  final String label;
  final bool liked;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            liked ? Icons.favorite_rounded : Icons.queue_music_rounded,
            size: 13,
            color: scheme.onSurfaceVariant,
          ),
          const SizedBox(width: 4),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 180),
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TrackActions extends StatelessWidget {
  const _TrackActions({
    required this.externalId,
    required this.action,
    required this.onDownload,
    required this.onWanted,
    required this.onIgnored,
    required this.onReset,
  });

  final String externalId;
  final String action;
  final VoidCallback? onDownload;
  final VoidCallback? onWanted;
  final VoidCallback? onIgnored;
  final VoidCallback? onReset;

  @override
  Widget build(BuildContext context) {
    if (onWanted == null) return const SizedBox.shrink();
    final l10n = context.l10n;
    return Wrap(
      alignment: WrapAlignment.end,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 6,
      runSpacing: 6,
      children: [
        if (onDownload != null)
          FilledButton.icon(
            key: ValueKey('coverage-download-$externalId'),
            onPressed: onDownload,
            icon: const Icon(Icons.download, size: 18),
            label: Text(l10n.coverageDownload),
          ),
        OutlinedButton(
          key: ValueKey('coverage-wanted-$externalId'),
          onPressed: action == 'wanted' ? null : onWanted,
          child: Text(l10n.coverageWanted),
        ),
        TextButton(
          key: ValueKey('coverage-ignored-$externalId'),
          onPressed: action == 'ignored' ? null : onIgnored,
          child: Text(l10n.coverageIgnore),
        ),
        if (action != 'unreviewed')
          IconButton(
            key: ValueKey('coverage-reset-$externalId'),
            tooltip: l10n.coverageResetDecision,
            onPressed: onReset,
            icon: const Icon(Icons.undo),
          ),
      ],
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (background, foreground) = switch (status) {
      'missing' => (scheme.errorContainer, scheme.onErrorContainer),
      'covered' => (scheme.secondaryContainer, scheme.onSecondaryContainer),
      'not_analyzed' =>
        (scheme.tertiaryContainer, scheme.onTertiaryContainer),
      'needs_review' => (scheme.primaryContainer, scheme.onPrimaryContainer),
      _ => (scheme.surfaceContainerHighest, scheme.onSurfaceVariant),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        _coverageStatusLabel(context, status),
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: foreground,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}

class _VariantBadge extends StatelessWidget {
  const _VariantBadge({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        _variantStatusLabel(context, status),
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: scheme.onSurfaceVariant,
            ),
      ),
    );
  }
}

