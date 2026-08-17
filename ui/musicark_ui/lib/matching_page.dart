import 'package:flutter/material.dart';

import 'app_strings.dart';
import 'content_label_bridge.dart';
import 'matching_bridge.dart';
import 'variant_acceptance_bridge.dart';

class MatchingPage extends StatefulWidget {
  MatchingPage({
    super.key,
    required this.bridge,
    ContentLabelBridgeClient? contentLabelBridge,
    VariantAcceptanceBridgeClient? variantAcceptanceBridge,
  })  : contentLabelBridge = contentLabelBridge ?? const ContentLabelBridge(),
        variantAcceptanceBridge =
            variantAcceptanceBridge ?? const VariantAcceptanceBridge();

  final MatchingBridgeClient bridge;
  final ContentLabelBridgeClient contentLabelBridge;
  final VariantAcceptanceBridgeClient variantAcceptanceBridge;

  @override
  State<MatchingPage> createState() => _MatchingPageState();
}

class _MatchingPageState extends State<MatchingPage> {
  static const _pageSize = 50;
  Map<String, dynamic> _summary = const {};
  Map<String, dynamic> _variantCapabilities = const {};
  List<Map<String, dynamic>> _items = const [];
  int _total = 0;
  bool _loading = true;
  bool _running = false;
  bool _runningVariants = false;
  bool _loadingMore = false;
  String _status = '';
  String _search = '';
  String _sort = 'confidence';
  String? _message;
  String? _variantMessage;
  String? _error;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final summary = await widget.bridge.matchingSummary();
      final results = await widget.bridge.matchingResults(
        limit: _pageSize,
        offset: 0,
        status: _status,
        search: _search,
        sort: _sort,
      );
      final capabilities = await widget.bridge.variantCapabilities();
      if (!mounted) return;
      setState(() {
        _summary = summary;
        _variantCapabilities = capabilities;
        _items = _ensureVariantRows(_mapItems(results['items']));
        _total = _asInt(results['count']);
      });
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _runMatching() async {
    setState(() {
      _running = true;
      _message = null;
      _error = null;
    });
    try {
      final result = await widget.bridge.matchingRun();
      if (!mounted) return;
      setState(() {
        _message = 'Обработано: ${_asInt(result['total'])}; '
            'совпало: ${_asInt(result['matched'])}; '
            'требует проверки: ${_asInt(result['conflicts'])}; '
            'не найдено: ${_asInt(result['unmatched'])}';
      });
      await _reload();
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  Future<void> _runAllVariants() async {
    setState(() {
      _runningVariants = true;
      _variantMessage = null;
      _error = null;
    });
    try {
      final result = await widget.bridge.variantRunAllAvailable();
      if (!mounted) return;
      setState(() {
        _variantMessage = 'Проверено версий: ${_asInt(result['processed'])}; '
            'та же версия: ${_asInt(result['same'])}; '
            'изменённая запись: ${_asInt(result['altered'])}; '
            'другая версия: ${_asInt(result['differentVersion'])}; '
            'неопределённо: ${_asInt(result['uncertain'])}';
      });
      await _reload();
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _runningVariants = false);
    }
  }

  Future<void> _loadMore() async {
    if (_loadingMore || _items.length >= _total) return;
    setState(() => _loadingMore = true);
    try {
      final result = await widget.bridge.matchingResults(
        limit: _pageSize,
        offset: _items.length,
        status: _status,
        search: _search,
        sort: _sort,
      );
      if (!mounted) return;
      setState(() {
        _items = [..._items, ..._ensureVariantRows(_mapItems(result['items']))];
        _total = _asInt(result['count']);
      });
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  Future<void> _setStatus(String status) async {
    if (_status == status) return;
    setState(() => _status = status);
    await _reload();
  }

  Future<void> _showDetail(Map<String, dynamic> row) async {
    final externalId = '${row['externalId'] ?? ''}';
    if (externalId.isEmpty) return;
    setState(() => _error = null);
    try {
      final payload = await widget.bridge.matchingResult(externalId);
      final detail = _asMap(payload['result']);
      if ('${detail['status'] ?? ''}' == 'matched') {
        final variantPayload = await widget.bridge.variantResult(externalId);
        detail['variant'] = _asMap(variantPayload['result']);
      }
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => _MatchingDetailDialog(
          detail: detail,
          variantCapabilities: _variantCapabilities,
          contentLabelBridge: widget.contentLabelBridge,
          variantAcceptanceBridge: widget.variantAcceptanceBridge,
          onVerifyVariant: '${detail['status'] ?? ''}' == 'matched'
              ? () async {
                  final result = await widget.bridge.variantRun(externalId);
                  final variant = _asMap(result['result']);
                  await _reload();
                  return variant;
                }
              : null,
          onAccept: (localFileId) async {
            await widget.bridge.matchingAccept(externalId, localFileId);
            if (dialogContext.mounted) Navigator.of(dialogContext).pop();
            await _reload();
          },
          onReject: (localFileId) async {
            await widget.bridge.matchingReject(externalId, localFileId);
            if (dialogContext.mounted) Navigator.of(dialogContext).pop();
            await _reload();
          },
        ),
      );
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    }
  }

  @override
  Widget build(BuildContext context) {
    final unavailableMessage = '${_variantCapabilities['unavailableMessage'] ?? ''}'.trim();
    return Scaffold(
      key: const Key('matching-page'),
      appBar: AppBar(title: const Text('Сопоставление')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _SummaryCard(summary: _summary),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                FilledButton.icon(
                  key: const Key('matching-run'),
                  onPressed: _running ? null : _runMatching,
                  icon: _running
                      ? const SizedBox.square(
                          dimension: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.compare_arrows),
                  label: Text(_running ? 'Сопоставление…' : 'Запустить сопоставление'),
                ),
                OutlinedButton.icon(
                  key: const Key('variant-run-all'),
                  onPressed: _runningVariants ? null : _runAllVariants,
                  icon: _runningVariants
                      ? const SizedBox.square(
                          key: Key('variant-progress'),
                          dimension: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.graphic_eq),
                  label: Text(_runningVariants ? 'Проверка версий…' : 'Проверить все доступные'),
                ),
                _FilterChip(
                  key: const Key('matching-filter-all'),
                  label: 'Все',
                  selected: _status.isEmpty,
                  onSelected: () => _setStatus(''),
                ),
                _FilterChip(
                  key: const Key('matching-filter-matched'),
                  label: 'Совпало',
                  selected: _status == 'matched',
                  onSelected: () => _setStatus('matched'),
                ),
                _FilterChip(
                  key: const Key('matching-filter-conflict'),
                  label: 'Требует проверки',
                  selected: _status == 'conflict',
                  onSelected: () => _setStatus('conflict'),
                ),
                _FilterChip(
                  key: const Key('matching-filter-unmatched'),
                  label: 'Не найдено',
                  selected: _status == 'unmatched',
                  onSelected: () => _setStatus('unmatched'),
                ),
              ],
            ),
            if (unavailableMessage.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                unavailableMessage,
                key: const Key('variant-unavailable'),
                style: TextStyle(color: Theme.of(context).colorScheme.secondary),
              ),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('matching-search'),
                    decoration: const InputDecoration(
                      labelText: 'Поиск по Яндекс Музыке, локальному треку или пути',
                      prefixIcon: Icon(Icons.search),
                      border: OutlineInputBorder(),
                    ),
                    textInputAction: TextInputAction.search,
                    onSubmitted: (value) {
                      _search = value.trim();
                      _reload();
                    },
                  ),
                ),
                const SizedBox(width: 12),
                DropdownButton<String>(
                  key: const Key('matching-sort'),
                  value: _sort,
                  items: const [
                    DropdownMenuItem(value: 'confidence', child: Text('Уверенность')),
                    DropdownMenuItem(value: 'artist', child: Text('Исполнитель')),
                    DropdownMenuItem(value: 'title', child: Text('Название')),
                    DropdownMenuItem(value: 'status', child: Text('Статус')),
                  ],
                  onChanged: (value) {
                    if (value == null) return;
                    setState(() => _sort = value);
                    _reload();
                  },
                ),
              ],
            ),
            if (_message != null) ...[
              const SizedBox(height: 10),
              Text(_message!, key: const Key('matching-run-result')),
            ],
            if (_variantMessage != null) ...[
              const SizedBox(height: 10),
              Text(_variantMessage!, key: const Key('variant-run-result')),
            ],
            if (_error != null) ...[
              const SizedBox(height: 10),
              Text(
                _error!,
                key: const Key('matching-error'),
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            const SizedBox(height: 12),
            Expanded(child: _buildResults()),
          ],
        ),
      ),
    );
  }

  Widget _buildResults() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_items.isEmpty) {
      return const Center(
        key: Key('matching-empty'),
        child: Text(
          'Результатов пока нет. Запустите сопоставление после загрузки Яндекс Музыки и локальной библиотеки.',
        ),
      );
    }
    return Column(
      children: [
        Expanded(
          child: ListView.separated(
            key: const Key('matching-results'),
            itemCount: _items.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final row = _items[index];
              return _ResultTile(row: row, onTap: () => _showDetail(row));
            },
          ),
        ),
        if (_items.length < _total)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: OutlinedButton(
              key: const Key('matching-load-more'),
              onPressed: _loadingMore ? null : _loadMore,
              child: Text(_loadingMore ? 'Загрузка…' : 'Показать ещё'),
            ),
          ),
      ],
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.summary});
  final Map<String, dynamic> summary;

  @override
  Widget build(BuildContext context) => Card(
        key: const Key('matching-summary'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Wrap(
            spacing: 24,
            runSpacing: 8,
            children: [
              Text('Треков Яндекс Музыки: ${_asInt(summary['yandexTracks'])}'),
              Text('Локальных треков: ${_asInt(summary['localTracks'])}'),
              Text('Совпало: ${_asInt(summary['matched'])}'),
              Text('Требует проверки: ${_asInt(summary['conflicts'])}'),
              Text('Не найдено: ${_asInt(summary['unmatched'])}'),
            ],
          ),
        ),
      );
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
        onSelected: (_) => onSelected(),
      );
}

class _ResultTile extends StatelessWidget {
  const _ResultTile({required this.row, required this.onTap});
  final Map<String, dynamic> row;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final provider = _asMap(row['provider']);
    final local = row['local'] is Map ? _asMap(row['local']) : const <String, dynamic>{};
    final status = '${row['status'] ?? ''}';
    final confidence = (_asDouble(row['confidence']) * 100).round();
    final artists = _artistText(provider['artists']);
    final localArtists = _artistText(local['artists']);
    final variant = row['variant'] is Map ? _asMap(row['variant']) : const <String, dynamic>{};
    return ListTile(
      key: Key('matching-row-${row['externalId']}'),
      onTap: onTap,
      leading: CircleAvatar(child: Text('$confidence%')),
      title: Text('$artists — ${provider['title'] ?? 'Без названия'}'),
      subtitle: Text(
        local.isEmpty
            ? '${provider['album_title'] ?? ''}\nЛокальное совпадение не найдено'
            : '${provider['album_title'] ?? ''}\nУверенность: $confidence%\n$localArtists — ${local['title'] ?? ''}\n${local['path'] ?? ''}',
      ),
      isThreeLine: true,
      trailing: SizedBox(
        width: 150,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            _CompactBadge(label: _matchingStatusLabel(status)),
            if (status == 'matched') ...[
              const SizedBox(height: 2),
              SizedBox(
                width: 150,
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerRight,
                  child: _VariantBadge(
                    key: Key('variant-badge-${row['externalId']}'),
                    status: '${variant['variantStatus'] ?? 'not_checked'}',
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _CompactBadge extends StatelessWidget {
  const _CompactBadge({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        child: Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.fade,
          softWrap: false,
          style: Theme.of(context).textTheme.labelSmall,
        ),
      ),
    );
  }
}

class _VariantBadge extends StatelessWidget {
  const _VariantBadge({super.key, required this.status});
  final String status;

  @override
  Widget build(BuildContext context) => _CompactBadge(label: _variantLabel(status));
}

class _MatchingDetailDialog extends StatefulWidget {
  const _MatchingDetailDialog({
    required this.detail,
    required this.variantCapabilities,
    required this.contentLabelBridge,
    required this.variantAcceptanceBridge,
    required this.onAccept,
    required this.onReject,
    this.onVerifyVariant,
  });

  final Map<String, dynamic> detail;
  final Map<String, dynamic> variantCapabilities;
  final ContentLabelBridgeClient contentLabelBridge;
  final VariantAcceptanceBridgeClient variantAcceptanceBridge;
  final Future<Map<String, dynamic>> Function()? onVerifyVariant;
  final Future<void> Function(int localFileId) onAccept;
  final Future<void> Function(int localFileId) onReject;

  @override
  State<_MatchingDetailDialog> createState() => _MatchingDetailDialogState();
}

class _MatchingDetailDialogState extends State<_MatchingDetailDialog> {
  bool _busy = false;
  bool _labelsBusy = false;
  bool _variantAccepted = false;
  String _providerLabel = '';
  String _localLabel = '';
  String? _variantError;
  String? _labelError;
  late Map<String, dynamic> _detail;

  String get _externalId => '${_detail['externalId'] ?? ''}';
  int? get _localFileId {
    final local = _detail['local'];
    if (local is Map) {
      final id = int.tryParse('${local['id'] ?? _detail['localFileId'] ?? ''}');
      if (id != null && id > 0) return id;
    }
    final id = int.tryParse('${_detail['localFileId'] ?? ''}');
    return id != null && id > 0 ? id : null;
  }

  @override
  void initState() {
    super.initState();
    _detail = Map<String, dynamic>.from(widget.detail);
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadUserState());
  }

  Future<void> _loadUserState() async {
    final localId = _localFileId;
    if (_externalId.isEmpty) return;
    setState(() {
      _labelsBusy = true;
      _labelError = null;
    });
    try {
      final labels = await widget.contentLabelBridge.batch(
        localFileIds: localId == null ? const [] : [localId],
        externalIds: [_externalId],
      );
      final provider = _asMap(labels['provider']);
      final local = _asMap(labels['local']);
      var accepted = false;
      if (localId != null && '${_detail['status'] ?? ''}' == 'matched') {
        try {
          final decision = await widget.variantAcceptanceBridge.get(_externalId, localId);
          accepted = decision['accepted'] == true;
        } catch (_) {}
      }
      if (!mounted) return;
      setState(() {
        _providerLabel = '${provider[_externalId] ?? ''}';
        _localLabel = localId == null ? '' : '${local['$localId'] ?? ''}';
        _variantAccepted = accepted;
      });
    } catch (error) {
      if (mounted) setState(() => _labelError = _errorText(error));
    } finally {
      if (mounted) setState(() => _labelsBusy = false);
    }
  }

  Future<void> _perform(Future<void> Function() action) async {
    setState(() => _busy = true);
    try {
      await action();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _verifyVariant() async {
    final callback = widget.onVerifyVariant;
    if (callback == null) return;
    setState(() {
      _busy = true;
      _variantError = null;
    });
    try {
      final variant = await callback();
      if (!mounted) return;
      setState(() {
        _detail['variant'] = variant;
        _variantAccepted = false;
      });
      await _loadUserState();
    } catch (error) {
      if (mounted) setState(() => _variantError = _errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _setProviderLabel(String label) async {
    setState(() {
      _labelsBusy = true;
      _labelError = null;
    });
    try {
      await widget.contentLabelBridge.setProvider(_externalId, label);
      if (mounted) setState(() => _providerLabel = label);
    } catch (error) {
      if (mounted) setState(() => _labelError = _errorText(error));
    } finally {
      if (mounted) setState(() => _labelsBusy = false);
    }
  }

  Future<void> _setLocalLabel(String label) async {
    final localId = _localFileId;
    if (localId == null) return;
    setState(() {
      _labelsBusy = true;
      _labelError = null;
    });
    try {
      await widget.contentLabelBridge.setLocal(localId, label);
      if (mounted) setState(() => _localLabel = label);
    } catch (error) {
      if (mounted) setState(() => _labelError = _errorText(error));
    } finally {
      if (mounted) setState(() => _labelsBusy = false);
    }
  }

  Future<void> _toggleVariantAcceptance() async {
    final localId = _localFileId;
    if (localId == null) return;
    setState(() {
      _busy = true;
      _variantError = null;
    });
    try {
      final result = _variantAccepted
          ? await widget.variantAcceptanceBridge.reset(_externalId, localId)
          : await widget.variantAcceptanceBridge.accept(_externalId, localId);
      if (!mounted) return;
      setState(() => _variantAccepted = result['accepted'] == true);
    } catch (error) {
      if (mounted) setState(() => _variantError = _errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = _asMap(_detail['provider']);
    final candidates = _mapItems(_detail['candidates']);
    final local = _detail['local'] is Map
        ? _asMap(_detail['local'])
        : const <String, dynamic>{};
    final identityStatus = '${_detail['status'] ?? ''}';
    final variant = _detail['variant'] is Map
        ? _asMap(_detail['variant'])
        : const <String, dynamic>{};
    final variantStatus = '${variant['variantStatus'] ?? 'not_checked'}';
    final reviewableVariant = const {
      'altered',
      'different_version',
      'uncertain',
    }.contains(variantStatus);

    return AlertDialog(
      key: const Key('matching-detail'),
      title: Text('${_artistText(provider['artists'])} — ${provider['title'] ?? ''}'),
      content: SizedBox(
        width: 980,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                spacing: 16,
                runSpacing: 8,
                children: [
                  Text(
                    'Статус сопоставления: ${_matchingStatusLabel(identityStatus)}',
                    key: const Key('matching-detail-status'),
                  ),
                  Text(
                    'Уверенность: ${(_asDouble(_detail['confidence']) * 100).round()}%',
                  ),
                ],
              ),
              const SizedBox(height: 12),
              _TrackComparisonTable(
                provider: provider,
                local: local,
                providerLabel: _providerLabel,
                localLabel: _localLabel,
                labelsBusy: _labelsBusy,
                onProviderLabelChanged: _setProviderLabel,
                onLocalLabelChanged: local.isEmpty ? null : _setLocalLabel,
              ),
              if (_labelError != null) ...[
                const SizedBox(height: 8),
                Text(
                  _labelError!,
                  key: const Key('matching-label-error'),
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              if (identityStatus == 'matched') ...[
                const Divider(height: 28),
                Text(
                  'Проверка версии',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                _VariantDetail(variant: variant),
                const SizedBox(height: 10),
                if (reviewableVariant)
                  Card(
                    key: const Key('variant-user-decision'),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              _variantAccepted
                                  ? 'Эта локальная версия принята. Она больше не требует проверки в покрытии и синхронизации.'
                                  : 'Анализ нашёл отличия. Если эта локальная версия вас устраивает, её можно принять без изменения результата анализа.',
                              key: const Key('variant-acceptance-status'),
                            ),
                          ),
                          const SizedBox(width: 12),
                          _variantAccepted
                              ? OutlinedButton(
                                  key: const Key('variant-reset-acceptance'),
                                  onPressed: _busy ? null : _toggleVariantAcceptance,
                                  child: const Text('Отменить принятие'),
                                )
                              : FilledButton(
                                  key: const Key('variant-accept-current'),
                                  onPressed: _busy ? null : _toggleVariantAcceptance,
                                  child: const Text('Эта версия меня устраивает'),
                                ),
                        ],
                      ),
                    ),
                  ),
                if ('${widget.variantCapabilities['unavailableMessage'] ?? ''}'.trim().isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      '${widget.variantCapabilities['unavailableMessage']}',
                      key: const Key('variant-detail-unavailable'),
                    ),
                  ),
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.centerLeft,
                  child: FilledButton.tonalIcon(
                    key: const Key('variant-verify'),
                    onPressed: _busy ? null : _verifyVariant,
                    icon: _busy
                        ? const SizedBox.square(
                            dimension: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.graphic_eq),
                    label: Text(_busy ? 'Проверка…' : 'Проверить версию заново'),
                  ),
                ),
                if (_variantError != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      _variantError!,
                      key: const Key('variant-detail-error'),
                      style: TextStyle(color: Theme.of(context).colorScheme.error),
                    ),
                  ),
              ],
              if (candidates.isNotEmpty) ...[
                const Divider(height: 28),
                Text('Кандидаты', style: Theme.of(context).textTheme.titleMedium),
                for (final candidate in candidates)
                  _CandidateCard(
                    candidate: candidate,
                    busy: _busy,
                    onAccept: () => _perform(
                      () => widget.onAccept(_asInt(candidate['localFileId'])),
                    ),
                    onReject: () => _perform(
                      () => widget.onReject(_asInt(candidate['localFileId'])),
                    ),
                  ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _busy ? null : () => Navigator.of(context).pop(),
          child: const Text('Закрыть'),
        ),
      ],
    );
  }
}

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
      _tableRow(context, 'Название', Text('${provider['title'] ?? '—'}'), Text('${local['title'] ?? '—'}')),
      _tableRow(context, 'Исполнитель', Text(_artistText(provider['artists'])), Text(local.isEmpty ? '—' : _artistText(local['artists']))),
      _tableRow(context, 'Альбом', Text('${provider['album_title'] ?? provider['album'] ?? '—'}'), Text('${local['album'] ?? '—'}')),
      _tableRow(context, 'Длительность', Text(_duration(provider['duration_seconds'])), Text(_duration(local['durationSeconds']))),
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
      _tableRow(context, 'Идентификатор', const Text('Трек Яндекс Музыки'), Text(local.isEmpty ? '—' : '#${local['id'] ?? '—'}')),
      _tableRow(context, 'Расположение', const Text('—'), SelectableText('${local['path'] ?? '—'}')),
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
          ? BoxDecoration(color: Theme.of(context).colorScheme.surfaceContainerHighest)
          : null,
      children: [
        cell(Text(label, style: header ? const TextStyle(fontWeight: FontWeight.bold) : null)),
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
        Text('Результат: ${_variantLabel(status)}', key: const Key('variant-detail-status')),
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
                  Text('Кандидат ${candidate['rank']} · уверенность $confidence% · ${_artistText(local['artists'])} — ${local['title'] ?? ''}'),
                  Text('${local['album'] ?? '—'} · ${_duration(local['durationSeconds'])}'),
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

List<Map<String, dynamic>> _ensureVariantRows(List<Map<String, dynamic>> rows) {
  return rows.map((row) {
    final copy = Map<String, dynamic>.from(row);
    if ('${copy['status'] ?? ''}' == 'matched' &&
        copy['localFileId'] != null &&
        copy['variant'] is! Map) {
      copy['variant'] = {
        'variantStatus': 'not_checked',
        'status': 'not_checked',
        'variantReasons': ['audio_not_checked'],
        'alteredSegments': <Map<String, dynamic>>[],
      };
    }
    return copy;
  }).toList();
}

List<Map<String, dynamic>> _mapItems(dynamic value) {
  if (value is! List) return <Map<String, dynamic>>[];
  return value.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList();
}

Map<String, dynamic> _asMap(dynamic value) {
  if (value is Map) return Map<String, dynamic>.from(value);
  return <String, dynamic>{};
}

int _asInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse('$value') ?? 0;
}

double _asDouble(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse('$value') ?? 0.0;
}

String _artistText(dynamic value) {
  if (value is List && value.isNotEmpty) {
    final result = value.map((item) => '$item'.trim()).where((item) => item.isNotEmpty).join(', ');
    if (result.isNotEmpty) return result;
  }
  final text = '$value'.trim();
  if (value is! List && text.isNotEmpty && text != 'null') return text;
  return 'Неизвестный исполнитель';
}

String _matchingStatusLabel(String status) => switch (status) {
      'matched' => 'Совпало',
      'conflict' => 'Требует проверки',
      'unmatched' => 'Не найдено',
      _ => 'Не определено',
    };

String _variantLabel(String status) => switch (status) {
      'same' => 'Та же версия',
      'altered' => 'Изменённая запись',
      'different_version' => 'Другая версия',
      'uncertain' => 'Неопределённо',
      _ => 'Не проверено',
    };

String _duration(dynamic value) {
  final seconds = double.tryParse('$value');
  if (seconds == null || seconds < 0) return '—';
  return '${seconds.toStringAsFixed(seconds == seconds.roundToDouble() ? 0 : 3)} с';
}

String _formatSeconds(double seconds) {
  final safe = seconds.isFinite && seconds >= 0 ? seconds.round() : 0;
  final minutes = safe ~/ 60;
  final remainder = safe % 60;
  return '$minutes:${remainder.toString().padLeft(2, '0')}';
}

String _errorText(Object error) {
  if (error is MatchingBridgeException) return error.message;
  if (error is MusicArkBridgeException) return error.message;
  return error.toString();
}
