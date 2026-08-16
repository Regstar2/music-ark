part of 'coverage_page.dart';

extension _CoveragePageView on _CoveragePageState {
  Widget _buildView(BuildContext context) {
    final summary = _summary ?? const <String, dynamic>{};
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
                    Text('Недостающие треки', style: Theme.of(context).textTheme.headlineSmall),
                    const SizedBox(height: 4),
                    const Text('Покрытие Yandex-библиотеки локальной коллекцией'),
                  ],
                ),
              ),
              IconButton(
                key: const Key('coverage-refresh'),
                tooltip: 'Обновить статус',
                onPressed: _loading ? null : () => _load(),
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
        ),
        if (_summary != null)
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: _Summary(summary: summary),
          ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _StatusChip(
                  key: const Key('coverage-filter-missing'),
                  selected: _status == 'missing',
                  label: 'Missing ${_asInt(summary['missing'])}',
                  onSelected: () => _setStatus('missing'),
                ),
                const SizedBox(width: 8),
                _StatusChip(
                  key: const Key('coverage-filter-review'),
                  selected: _status == 'needs_review',
                  label: 'Review ${_asInt(summary['needsReview'])}',
                  onSelected: () => _setStatus('needs_review'),
                ),
                const SizedBox(width: 8),
                _StatusChip(
                  key: const Key('coverage-filter-not-analyzed'),
                  selected: _status == 'not_analyzed',
                  label: 'Not analyzed ${_asInt(summary['notAnalyzed'])}',
                  onSelected: () => _setStatus('not_analyzed'),
                ),
                const SizedBox(width: 8),
                _StatusChip(
                  key: const Key('coverage-filter-covered'),
                  selected: _status == 'covered',
                  label: 'Covered ${_asInt(summary['covered'])}',
                  onSelected: () => _setStatus('covered'),
                ),
              ],
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 4, 24, 8),
          child: LayoutBuilder(
            builder: (context, constraints) {
              double fieldWidth(double preferred) =>
                  constraints.maxWidth < preferred ? constraints.maxWidth : preferred;
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
                      decoration: const InputDecoration(
                        labelText: 'Коллекция',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      items: [
                        const DropdownMenuItem(
                          value: '',
                          child: Text('Вся Yandex-библиотека', overflow: TextOverflow.ellipsis),
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
                      onChanged: _setCollection,
                    ),
                  ),
                  SizedBox(
                    width: fieldWidth(320),
                    child: TextField(
                      key: const Key('coverage-search'),
                      controller: _searchController,
                      onChanged: _queueSearch,
                      decoration: const InputDecoration(
                        labelText: 'Поиск',
                        hintText: 'Название, исполнитель, альбом, плейлист',
                        prefixIcon: Icon(Icons.search),
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                  ),
                  SizedBox(
                    width: fieldWidth(190),
                    child: DropdownButtonFormField<String>(
                      key: const Key('coverage-sort'),
                      initialValue: _sort,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Сортировка',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      items: [
                        if (_collectionId.startsWith('playlist:'))
                          const DropdownMenuItem(value: 'position', child: Text('Порядок плейлиста', overflow: TextOverflow.ellipsis)),
                        const DropdownMenuItem(value: 'artist', child: Text('Исполнитель')),
                        const DropdownMenuItem(value: 'title', child: Text('Название')),
                        const DropdownMenuItem(value: 'album', child: Text('Альбом')),
                        const DropdownMenuItem(value: 'collection', child: Text('Коллекция')),
                        const DropdownMenuItem(value: 'status', child: Text('Статус')),
                      ],
                      onChanged: (value) {
                        if (value == null) return;
                        _updateView(() {
                          _sort = value;
                          _offset = 0;
                        });
                        _reloadTracks(refreshSummary: false);
                      },
                    ),
                  ),
                  SizedBox(
                    width: fieldWidth(180),
                    child: DropdownButtonFormField<String>(
                      key: const Key('coverage-action-filter'),
                      initialValue: _userAction,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Решение',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      items: const [
                        DropdownMenuItem(value: '', child: Text('Все')),
                        DropdownMenuItem(value: 'unreviewed', child: Text('Не решено')),
                        DropdownMenuItem(value: 'wanted', child: Text('Нужен')),
                        DropdownMenuItem(value: 'ignored', child: Text('Игнорировать')),
                      ],
                      onChanged: (value) {
                        _updateView(() {
                          _userAction = value ?? '';
                          _offset = 0;
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
                        decoration: const InputDecoration(
                          labelText: 'Variant',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                        items: const [
                          DropdownMenuItem(value: '', child: Text('Все версии')),
                          DropdownMenuItem(value: 'same', child: Text('Same')),
                          DropdownMenuItem(value: 'altered', child: Text('Altered')),
                          DropdownMenuItem(value: 'different_version', child: Text('Другая версия')),
                          DropdownMenuItem(value: 'uncertain', child: Text('Uncertain')),
                          DropdownMenuItem(value: 'not_checked', child: Text('Not checked')),
                        ],
                        onChanged: (value) {
                          _updateView(() {
                            _variantStatus = value ?? '';
                            _offset = 0;
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
        if (_selected.isNotEmpty)
          _BulkBar(
            count: _selected.length,
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
                  style: TextStyle(color: Theme.of(context).colorScheme.onErrorContainer),
                ),
              ),
            ),
          ),
        Expanded(child: _body(summary)),
        _Pagination(
          offset: _offset,
          limit: _pageLimit,
          total: _total,
          onPrevious: _offset <= 0 || _loading
              ? null
              : () {
                  _updateView(() => _offset = _offset > _pageLimit ? _offset - _pageLimit : 0);
                  _reloadTracks(refreshSummary: false);
                },
          onNext: _offset + _pageLimit >= _total || _loading
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
    if (_loading && _items.isEmpty) return const Center(child: CircularProgressIndicator());
    if (_items.isEmpty) {
      final total = _asInt(summary['total']);
      final notAnalyzed = _asInt(summary['notAnalyzed']);
      if (total > 0 && notAnalyzed == total) {
        return _EmptyState(
          title: 'Сначала выполните сопоставление библиотеки.',
          actionLabel: _matching ? 'Сопоставление…' : 'Запустить сопоставление',
          onAction: _matching ? null : _runMatching,
          secondaryAction: widget.onOpenMatching,
        );
      }
      if (_status == 'missing' && _asInt(summary['missing']) == 0) {
        return const _EmptyState(
          title: 'Нет треков, доказанно отсутствующих локально.',
          subtitle: 'Конфликты и неанализированные треки остаются отдельными состояниями.',
        );
      }
      return const _EmptyState(title: 'Нет треков для выбранных фильтров.');
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
          onSelectionChanged: isMissing
              ? (value) => _updateView(() {
                  if (value) {
                    _selected.add(id);
                  } else {
                    _selected.remove(id);
                  }
                })
              : null,
          onOpen: () => _openDetails(item),
          onWanted: isMissing ? () => _setAction(id, 'wanted') : null,
          onIgnored: isMissing ? () => _setAction(id, 'ignored') : null,
          onReset: isMissing ? () => _setAction(id, 'unreviewed') : null,
          onDownload: isMissing && widget.downloadBridge != null
              ? () => _enqueueDownload(id)
              : null,
          onOpenMatching: item['coverageStatus'] == 'needs_review' || item['coverageStatus'] == 'not_analyzed'
              ? widget.onOpenMatching
              : null,
        );
      },
    );
  }
}
