import 'package:flutter/material.dart';

import 'matching_bridge.dart';

class MatchingPage extends StatefulWidget {
  const MatchingPage({super.key, required this.bridge});

  final MatchingBridgeClient bridge;

  @override
  State<MatchingPage> createState() => _MatchingPageState();
}

class _MatchingPageState extends State<MatchingPage> {
  static const _pageSize = 50;
  Map<String, dynamic> _summary = const {};
  List<Map<String, dynamic>> _items = const [];
  int _total = 0;
  bool _loading = true;
  bool _running = false;
  bool _loadingMore = false;
  String _status = '';
  String _search = '';
  String _sort = 'confidence';
  String? _message;
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
      if (!mounted) return;
      setState(() {
        _summary = summary;
        _items = _mapItems(results['items']);
        _total = _asInt(results['count']);
      });
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
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
            'проверить: ${_asInt(result['conflicts'])}; '
            'не найдено: ${_asInt(result['unmatched'])}';
      });
      await _reload();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _running = false);
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
        _items = [..._items, ..._mapItems(result['items'])];
        _total = _asInt(result['count']);
      });
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
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
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => _MatchingDetailDialog(
          detail: detail,
          onAccept: (localFileId) async {
            await widget.bridge.matchingAccept(externalId, localFileId);
            if (context.mounted) Navigator.of(context).pop();
            await _reload();
          },
          onReject: (localFileId) async {
            await widget.bridge.matchingReject(externalId, localFileId);
            if (context.mounted) Navigator.of(context).pop();
            await _reload();
          },
        ),
      );
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
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
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('matching-search'),
                    decoration: const InputDecoration(
                      labelText: 'Поиск по Yandex / Local / пути',
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
        child: Text('Результатов пока нет. Запустите сопоставление после загрузки Yandex и Local Library.'),
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
  Widget build(BuildContext context) {
    return Card(
      key: const Key('matching-summary'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Wrap(
          spacing: 24,
          runSpacing: 8,
          children: [
            Text('Yandex tracks: ${_asInt(summary['yandexTracks'])}'),
            Text('Local tracks: ${_asInt(summary['localTracks'])}'),
            Text('Matched: ${_asInt(summary['matched'])}'),
            Text('Conflicts: ${_asInt(summary['conflicts'])}'),
            Text('Unmatched: ${_asInt(summary['unmatched'])}'),
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
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onSelected(),
    );
  }
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
    final confidence = ((_asDouble(row['confidence']) * 100).round());
    final artists = _artistText(provider['artists']);
    final localArtists = _artistText(local['artists']);
    final statusLabel = switch (status) {
      'matched' => 'MATCHED',
      'conflict' => 'CONFLICT',
      _ => 'UNMATCHED',
    };
    return ListTile(
      key: Key('matching-row-${row['externalId']}'),
      onTap: onTap,
      leading: CircleAvatar(child: Text('$confidence%')),
      title: Text('$artists — ${provider['title'] ?? 'Без названия'}'),
      subtitle: Text(
        local.isEmpty
            ? '${provider['album_title'] ?? ''}\nЛокальное совпадение не найдено'
            : '${provider['album_title'] ?? ''}\n↓ $confidence%\n$localArtists — ${local['title'] ?? ''}\n${local['path'] ?? ''}',
      ),
      isThreeLine: true,
      trailing: Chip(label: Text(statusLabel)),
    );
  }
}

class _MatchingDetailDialog extends StatefulWidget {
  const _MatchingDetailDialog({
    required this.detail,
    required this.onAccept,
    required this.onReject,
  });
  final Map<String, dynamic> detail;
  final Future<void> Function(int localFileId) onAccept;
  final Future<void> Function(int localFileId) onReject;

  @override
  State<_MatchingDetailDialog> createState() => _MatchingDetailDialogState();
}

class _MatchingDetailDialogState extends State<_MatchingDetailDialog> {
  bool _busy = false;

  Future<void> _perform(Future<void> Function() action) async {
    setState(() => _busy = true);
    try {
      await action();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = _asMap(widget.detail['provider']);
    final candidates = _mapItems(widget.detail['candidates']);
    final local = widget.detail['local'] is Map
        ? _asMap(widget.detail['local'])
        : const <String, dynamic>{};
    return AlertDialog(
      key: const Key('matching-detail'),
      title: Text('${_artistText(provider['artists'])} — ${provider['title'] ?? ''}'),
      content: SizedBox(
        width: 760,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Yandex album: ${provider['album_title'] ?? '—'}'),
              Text('Yandex duration: ${provider['duration_seconds'] ?? '—'} s'),
              if (local.isNotEmpty) ...[
                const Divider(),
                Text('Local: ${_artistText(local['artists'])} — ${local['title'] ?? ''}'),
                Text('Album: ${local['album'] ?? '—'}'),
                Text('Duration: ${local['durationSeconds'] ?? '—'} s'),
                Text('Path: ${local['path'] ?? '—'}'),
              ],
              if (candidates.isNotEmpty) ...[
                const Divider(),
                const Text('Кандидаты', style: TextStyle(fontWeight: FontWeight.bold)),
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
        TextButton(onPressed: _busy ? null : () => Navigator.of(context).pop(), child: const Text('Закрыть')),
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
                  Text('#${candidate['rank']} · $confidence% · ${_artistText(local['artists'])} — ${local['title'] ?? ''}'),
                  Text('${local['album'] ?? '—'} · ${local['durationSeconds'] ?? '—'} s'),
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
  if (value is List && value.isNotEmpty) return value.join(', ');
  return 'Unknown Artist';
}
