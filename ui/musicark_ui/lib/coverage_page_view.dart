part of 'coverage_page.dart';

extension _CoveragePageView on _CoveragePageState {
  Widget _buildView(BuildContext context) {
    final l10n = context.l10n;
    final summary = _summary ?? const <String, dynamic>{};
    final allSelected = _status == 'missing' &&
        _total > 0 &&
        _selected.length >= _total;
    final partiallySelected =
        _status == 'missing' && _selected.isNotEmpty && !allSelected;

    return Column(
      key: const Key('coverage-page'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 20, 24, 12),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l10n.coverageTitle,
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      l10n.coverageSubtitle,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                    ),
                  ],
                ),
              ),
              IconButton(
                key: const Key('coverage-refresh'),
                tooltip: l10n.coverageRefresh,
                onPressed: _loading || _bulkBusy ? null : () => _load(),
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
        ),
        if (_summary != null)
          _Summary(
            summary: summary,
            expanded: _analysisExpanded,
            onToggleDetails: () => _updateView(
              () => _analysisExpanded = !_analysisExpanded,
            ),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 4),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _StatusTab(
                  key: const Key('coverage-filter-missing'),
                  selected: _status == 'missing',
                  label: l10n.coverageTabMissing,
                  count: _asInt(summary['missing']),
                  onTap: () => _setStatus('missing'),
                ),
                const SizedBox(width: 8),
                _StatusTab(
                  key: const Key('coverage-filter-review'),
                  selected: _status == 'needs_review',
                  label: l10n.coverageTabReview,
                  count: _asInt(summary['needsReview']),
                  onTap: () => _setStatus('needs_review'),
                ),
                const SizedBox(width: 8),
                _StatusTab(
                  key: const Key('coverage-filter-not-analyzed'),
                  selected: _status == 'not_analyzed',
                  label: l10n.coverageTabNotAnalyzed,
                  count: _asInt(summary['notAnalyzed']),
                  onTap: () => _setStatus('not_analyzed'),
                ),
                const SizedBox(width: 8),
                _StatusTab(
                  key: const Key('coverage-filter-covered'),
                  selected: _status == 'covered',
                  label: l10n.coverageTabCovered,
                  count: _asInt(summary['covered']),
                  onTap: () => _setStatus('covered'),
                ),
              ],
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 8),
          child: LayoutBuilder(
            builder: (context, constraints) {
              double fieldWidth(double preferred) =>
                  constraints.maxWidth < preferred
                      ? constraints.maxWidth
                      : preferred;
              final searchWidth = constraints.maxWidth >= 1200 ? 420.0 : 340.0;
              return Wrap(
                spacing: 12,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  SizedBox(
                    width: fieldWidth(280),
                    child: DropdownButtonFormField<String>(
                      key: const Key('coverage-collection'),
                      initialValue: _collectionId,
                      isExpanded: true,
                      decoration: InputDecoration(
                        labelText: l10n.coverageCollectionLabel,
                        border: const OutlineInputBorder(),
                        isDense: true,
                      ),
                      items: [
                        DropdownMenuItem(
                          value: '',
                          child: Text(
                            l10n.coverageAllLibrary,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        ..._collections.map(
                          (collection) => DropdownMenuItem(
                            value: (collection['id'] ?? '').toString(),
                            child: Text(
                              (collection['title'] ?? collection['id']).toString(),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                      ],
                      onChanged: _bulkBusy ? null : _setCollection,
                    ),
                  ),
                  SizedBox(
                    width: fieldWidth(searchWidth),
                    child: TextField(
                      key: const Key('coverage-search'),
                      controller: _searchController,
                      enabled: !_bulkBusy,
                      onChanged: _queueSearch,
                      decoration: InputDecoration(
                        labelText: l10n.coverageSearchLabel,
                        hintText: l10n.coverageSearchHint,
                        prefixIcon: const Icon(Icons.search),
                        border: const OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                  ),
                  if (_status == 'missing')
                    SizedBox(
                      width: fieldWidth(180),
                      child: DropdownButtonFormField<String>(
                        key: const Key('coverage-action-filter'),
                        initialValue: _userAction,
                        isExpanded: true,
                        decoration: InputDecoration(
                          labelText: l10n.coverageDecisionLabel,
                          border: const OutlineInputBorder(),
                          isDense: true,
                        ),
                        items: [
                          DropdownMenuItem(
                            value: '',
                            child: Text(l10n.coverageDecisionAll),
                          ),
                          DropdownMenuItem(
                            value: 'unreviewed',
                            child: Text(l10n.coverageDecisionUnreviewed),
                          ),
                          DropdownMenuItem(
                            value: 'wanted',
                            child: Text(l10n.coverageDecisionWanted),
                          ),
                          DropdownMenuItem(
                            value: 'ignored',
                            child: Text(l10n.coverageDecisionIgnored),
                          ),
                        ],
                        onChanged: _bulkBusy
                            ? null
                            : (value) {
                                _updateView(() {
                                  _userAction = value ?? '';
                                  _offset = 0;
                                  _selected.clear();
                                });
                                _reloadTracks(refreshSummary: false);
                              },
                      ),
                    ),
                  SizedBox(
                    width: fieldWidth(190),
                    child: DropdownButtonFormField<String>(
                      key: const Key('coverage-sort'),
                      initialValue: _sort,
                      isExpanded: true,
                      decoration: InputDecoration(
                        labelText: l10n.coverageSortLabel,
                        border: const OutlineInputBorder(),
                        isDense: true,
                      ),
                      items: [
                        if (_collectionId.startsWith('playlist:'))
                          DropdownMenuItem(
                            value: 'position',
                            child: Text(
                              l10n.coverageSortPlaylistPosition,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        DropdownMenuItem(
                          value: 'artist',
                          child: Text(l10n.coverageSortArtist),
                        ),
                        DropdownMenuItem(
                          value: 'title',
                          child: Text(l10n.coverageSortTitle),
                        ),
                        DropdownMenuItem(
                          value: 'album',
                          child: Text(l10n.coverageSortAlbum),
                        ),
                        DropdownMenuItem(
                          value: 'collection',
                          child: Text(l10n.coverageSortCollection),
                        ),
                        DropdownMenuItem(
                          value: 'status',
                          child: Text(l10n.coverageSortStatus),
                        ),
                      ],
                      onChanged: _bulkBusy
                          ? null
                          : (value) {
                              if (value == null) return;
                              _updateView(() {
                                _sort = value;
                                _offset = 0;
                                _selected.clear();
                              });
                              _reloadTracks(refreshSummary: false);
                            },
                    ),
                  ),
                  if (_status == 'covered')
                    SizedBox(
                      width: fieldWidth(210),
                      child: DropdownButtonFormField<String>(
                        key: const Key('coverage-variant-filter'),
                        initialValue: _variantStatus,
                        isExpanded: true,
                        decoration: InputDecoration(
                          labelText: l10n.coverageVariantFilterLabel,
                          border: const OutlineInputBorder(),
                          isDense: true,
                        ),
                        items: [
                          DropdownMenuItem(
                            value: '',
                            child: Text(l10n.coverageVariantAll),
                          ),
                          DropdownMenuItem(
                            value: 'same',
                            child: Text(l10n.matchingVariantSame),
                          ),
                          DropdownMenuItem(
                            value: 'altered',
                            child: Text(l10n.matchingVariantAltered),
                          ),
                          DropdownMenuItem(
                            value: 'different_version',
                            child: Text(l10n.matchingVariantDifferent),
                          ),
                          DropdownMenuItem(
                            value: 'uncertain',
                            child: Text(l10n.matchingVariantUncertain),
                          ),
                          DropdownMenuItem(
                            value: 'not_checked',
                            child: Text(l10n.matchingVariantNotChecked),
                          ),
                        ],
                        onChanged: _bulkBusy
                            ? null
                            : (value) {
                                _updateView(() {
                                  _variantStatus = value ?? '';
                                  _offset = 0;
                                  _selected.clear();
                                });
                                _reloadTracks(refreshSummary: false);
                              },
                      ),
                    ),
                ],
              );
            },
          ),
        ),
        if (_status == 'missing' && _total > 0)
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 0, 24, 8),
            child: Row(
              children: [
                Checkbox(
                  key: const Key('coverage-select-all'),
                  value: allSelected ? true : partiallySelected ? null : false,
                  tristate: true,
                  onChanged: _loading || _bulkBusy
                      ? null
                      : (_) {
                          if (_selected.isNotEmpty) {
                            _clearSelection();
                          } else {
                            _selectAllFiltered();
                          }
                        },
                ),
                Text(l10n.coverageTrackCount(_total)),
                if (_bulkSelectBusy) ...[
                  const SizedBox(width: 12),
                  SizedBox(
                    key: const Key('coverage-select-all-progress'),
                    width: 160,
                    child: LinearProgressIndicator(value: _bulkProgressValue),
                  ),
                  const SizedBox(width: 8),
                  Text('$_bulkProcessed / $_bulkTotal'),
                ],
                const Spacer(),
                if (_selected.isEmpty)
                  Text(
                    l10n.coverageSelectAll,
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                          color: Theme.of(context).colorScheme.primary,
                        ),
                  )
                else
                  Text(
                    l10n.coverageSelectedCount(_selected.length, _total),
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
              ],
            ),
          ),
        if (_selected.isNotEmpty)
          _BulkBar(
            count: _selected.length,
            busy: _bulkActionBusy,
            processed: _bulkProcessed,
            total: _bulkTotal,
            onWanted: () => _setBulkAction('wanted'),
            onIgnored: () => _setBulkAction('ignored'),
            onReset: () => _setBulkAction('unreviewed'),
          ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 4),
            child: Material(
              color: Theme.of(context).colorScheme.errorContainer,
              borderRadius: BorderRadius.circular(8),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  _error!,
                  key: const Key('coverage-error'),
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onErrorContainer,
                  ),
                ),
              ),
            ),
          ),
        Expanded(child: _body(summary)),
        if (_total > _pageLimit)
          _Pagination(
            offset: _offset,
            limit: _pageLimit,
            total: _total,
            onPrevious: _offset <= 0 || _loading || _bulkBusy
                ? null
                : () {
                    _updateView(
                      () => _offset = _offset > _pageLimit
                          ? _offset - _pageLimit
                          : 0,
                    );
                    _reloadTracks(refreshSummary: false);
                  },
            onNext: _offset + _pageLimit >= _total || _loading || _bulkBusy
                ? null
                : () {
                    _updateView(() => _offset += _pageLimit);
                    _reloadTracks(refreshSummary: false);
                  },
          ),
      ],
    );
  }

  Widget _body(Map<String, dynamic> summary) {
    final l10n = context.l10n;
    if (_loading && _items.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_items.isEmpty) {
      final total = _asInt(summary['total']);
      final notAnalyzed = _asInt(summary['notAnalyzed']);
      if (total > 0 && notAnalyzed == total) {
        return _EmptyState(
          title: l10n.coverageEmptyRunMatching,
          actionLabel: _matching
              ? l10n.coverageMatchingRunning
              : l10n.coverageRunMatching,
          onAction: _matching ? null : _runMatching,
          secondaryAction: widget.onOpenMatching,
        );
      }
      if (_status == 'missing' && _asInt(summary['missing']) == 0) {
        return _EmptyState(
          title: l10n.coverageEmptyMissingTitle,
          subtitle: l10n.coverageEmptyMissingBody,
        );
      }
      return _EmptyState(title: l10n.coverageEmptyFiltered);
    }
    return ListView.builder(
      key: const Key('coverage-list'),
      padding: const EdgeInsets.fromLTRB(24, 4, 24, 16),
      itemCount: _items.length,
      itemBuilder: (context, index) {
        final item = _items[index];
        final id = (item['externalId'] ?? '').toString();
        final isMissing = item['coverageStatus'] == 'missing';
        return _CoverageRow(
          key: ValueKey('coverage-row-$id'),
          item: item,
          selected: _selected.contains(id),
          onSelectionChanged: isMissing && !_bulkBusy
              ? (value) => _updateView(() {
                  if (value) {
                    _selected.add(id);
                  } else {
                    _selected.remove(id);
                  }
                })
              : null,
          onOpen: () => _openDetails(item),
          onWanted: isMissing && !_bulkBusy ? () => _setAction(id, 'wanted') : null,
          onIgnored: isMissing && !_bulkBusy ? () => _setAction(id, 'ignored') : null,
          onReset: isMissing && !_bulkBusy ? () => _setAction(id, 'unreviewed') : null,
          onDownload: isMissing && widget.downloadBridge != null
              ? () => _enqueueDownload(id)
              : null,
          onOpenMatching: item['coverageStatus'] == 'needs_review' ||
                  item['coverageStatus'] == 'not_analyzed'
              ? widget.onOpenMatching
              : null,
        );
      },
    );
  }
}
