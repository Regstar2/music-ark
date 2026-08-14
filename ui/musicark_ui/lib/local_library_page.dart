import 'package:flutter/material.dart';

import 'folder_picker.dart';
import 'musicark_bridge.dart';

class LocalLibraryPage extends StatefulWidget {
  const LocalLibraryPage({
    super.key,
    required this.bridge,
    LocalFolderPicker? folderPicker,
  }) : folderPicker = folderPicker ?? const SystemLocalFolderPicker();

  final MusicArkBridgeClient bridge;
  final LocalFolderPicker folderPicker;

  @override
  State<LocalLibraryPage> createState() => _LocalLibraryPageState();
}

class _LocalLibraryPageState extends State<LocalLibraryPage> {
  static const _pageSize = 1000;
  final _search = TextEditingController();
  List<Map<String, dynamic>> _roots = const [];
  List<Map<String, dynamic>> _tracks = const [];
  int _total = 0;
  bool _busy = true;
  String _sort = 'artist';
  String? _status;
  String? _error;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  List<Map<String, dynamic>> _maps(dynamic value) => value is List
      ? value.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList(growable: false)
      : <Map<String, dynamic>>[];

  Future<void> _reload({bool preserveStatus = false}) async {
    setState(() {
      _busy = true;
      _error = null;
      if (!preserveStatus) _status = null;
    });
    try {
      final rootsPayload = await widget.bridge.localRoots();
      final tracksPayload = await widget.bridge.localTracks(
        limit: _pageSize,
        offset: 0,
        search: _search.text.trim(),
        sort: _sort,
      );
      if (!mounted) return;
      setState(() {
        _roots = _maps(rootsPayload['items']);
        _tracks = _maps(tracksPayload['items']);
        _total = int.tryParse('${tracksPayload['count'] ?? 0}') ?? 0;
      });
    } on MusicArkBridgeException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _loadMore() async {
    if (_tracks.length >= _total || _busy) return;
    setState(() => _busy = true);
    try {
      final payload = await widget.bridge.localTracks(
        limit: _pageSize,
        offset: _tracks.length,
        search: _search.text.trim(),
        sort: _sort,
      );
      if (!mounted) return;
      setState(() {
        _tracks = [..._tracks, ..._maps(payload['items'])];
        _total = int.tryParse('${payload['count'] ?? _total}') ?? _total;
      });
    } on MusicArkBridgeException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _addFolder() async {
    final path = await widget.folderPicker.pickDirectory();
    if (path == null || path.trim().isEmpty) return;
    setState(() => _busy = true);
    try {
      await widget.bridge.localRootAdd(path);
      if (!mounted) return;
      setState(() => _status = 'Папка добавлена. Запустите сканирование.');
      await _reload(preserveStatus: true);
    } on MusicArkBridgeException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _removeFolder(Map<String, dynamic> root) async {
    final id = int.tryParse('${root['id']}');
    if (id == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Убрать папку из MusicArk?'),
        content: Text(
          '${root['path']}\n\nБудут удалены только записи из индекса MusicArk. Музыкальные файлы на диске не изменяются и не удаляются.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Отмена')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Убрать')),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _busy = true);
    try {
      await widget.bridge.localRootRemove(id);
      if (!mounted) return;
      setState(() => _status = 'Папка удалена из индекса MusicArk. Файлы на диске не затронуты.');
      await _reload(preserveStatus: true);
    } on MusicArkBridgeException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _scan({int? rootId}) async {
    setState(() {
      _busy = true;
      _error = null;
      _status = 'Сканирование...';
    });
    try {
      final result = await widget.bridge.localScan(rootId: rootId);
      if (!mounted) return;
      final added = result['added'] ?? 0;
      final updated = result['updated'] ?? 0;
      final removed = result['removed'] ?? 0;
      final unchanged = result['unchanged'] ?? 0;
      final errors = result['errors'] ?? 0;
      final errorItems = _maps(result['errorItems']);
      final firstError = errorItems.isEmpty
          ? ''
          : ' Первая ошибка: ${errorItems.first['path'] ?? 'unknown'} — ${errorItems.first['error'] ?? 'unknown error'}';
      setState(() {
        _status = 'Сканирование завершено — добавлено: $added, обновлено: $updated, удалено: $removed, без изменений: $unchanged, ошибок: $errors.$firstError';
      });
      await _reload(preserveStatus: true);
    } on MusicArkBridgeException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _artists(Map<String, dynamic> track) {
    final raw = track['artists'];
    if (raw is List) {
      final text = raw.map((e) => e.toString()).where((e) => e.isNotEmpty).join(', ');
      if (text.isNotEmpty) return text;
    }
    return 'Unknown Artist';
  }

  String _duration(dynamic raw) {
    final seconds = double.tryParse('$raw');
    if (seconds == null || seconds <= 0) return '—';
    final whole = seconds.round();
    final minutes = whole ~/ 60;
    final remainder = whole % 60;
    return '$minutes:${remainder.toString().padLeft(2, '0')}';
  }

  void _showDetails(Map<String, dynamic> track) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text((track['title'] ?? track['fileName'] ?? 'Track').toString()),
        content: SizedBox(
          width: 620,
          child: SelectableText(
            'Исполнитель: ${_artists(track)}\n'
            'Альбом: ${track['album'] ?? '—'}\n'
            'Длительность: ${_duration(track['durationSeconds'])}\n'
            'Формат: ${track['codec'] ?? track['extension'] ?? '—'}\n'
            'Битрейт: ${track['bitrate'] ?? '—'}\n'
            'Sample rate: ${track['sampleRate'] ?? '—'}\n\n'
            'Путь: ${track['path'] ?? '—'}',
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Закрыть'))],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('local-library-page'),
      appBar: AppBar(
        title: const Text('Локальная библиотека'),
        actions: [
          FilledButton.icon(
            key: const Key('local-add-folder'),
            onPressed: _busy ? null : _addFolder,
            icon: const Icon(Icons.create_new_folder_outlined),
            label: const Text('Добавить папку'),
          ),
          const SizedBox(width: 8),
          FilledButton.tonalIcon(
            key: const Key('local-scan-all'),
            onPressed: _busy || _roots.isEmpty ? null : () => _scan(),
            icon: const Icon(Icons.sync),
            label: const Text('Сканировать'),
          ),
          const SizedBox(width: 16),
        ],
      ),
      body: Column(
        children: [
          if (_busy) const LinearProgressIndicator(key: Key('local-progress')),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('$_total треков', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  children: [
                    SizedBox(
                      width: 440,
                      child: TextField(
                        key: const Key('local-search'),
                        controller: _search,
                        onSubmitted: (_) => _reload(),
                        decoration: InputDecoration(
                          prefixIcon: const Icon(Icons.search),
                          hintText: 'Поиск: название, исполнитель, альбом, файл',
                          border: const OutlineInputBorder(),
                          suffixIcon: IconButton(
                            onPressed: () { _search.clear(); _reload(); },
                            icon: const Icon(Icons.clear),
                          ),
                        ),
                      ),
                    ),
                    DropdownButton<String>(
                      key: const Key('local-sort'),
                      value: _sort,
                      items: const [
                        DropdownMenuItem(value: 'artist', child: Text('Исполнитель')),
                        DropdownMenuItem(value: 'title', child: Text('Название')),
                        DropdownMenuItem(value: 'album', child: Text('Альбом')),
                        DropdownMenuItem(value: 'duration', child: Text('Длительность')),
                        DropdownMenuItem(value: 'path', child: Text('Путь')),
                      ],
                      onChanged: _busy ? null : (value) { if (value != null) { setState(() => _sort = value); _reload(); } },
                    ),
                  ],
                ),
                if (_status != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_status!, key: const Key('local-status'))),
                if (_error != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_error!, key: const Key('local-error'), style: TextStyle(color: Theme.of(context).colorScheme.error))),
              ],
            ),
          ),
          SizedBox(
            height: _roots.isEmpty ? 0 : 92,
            child: ListView.separated(
              key: const Key('local-roots'),
              padding: const EdgeInsets.symmetric(horizontal: 16),
              scrollDirection: Axis.horizontal,
              itemCount: _roots.length,
              separatorBuilder: (_, _) => const SizedBox(width: 8),
              itemBuilder: (context, index) {
                final root = _roots[index];
                final id = int.tryParse('${root['id']}');
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        ConstrainedBox(constraints: const BoxConstraints(maxWidth: 360), child: Text('${root['path']}', overflow: TextOverflow.ellipsis)),
                        IconButton(key: Key('local-scan-root-${root['id']}'), tooltip: 'Сканировать эту папку', onPressed: _busy || id == null ? null : () => _scan(rootId: id), icon: const Icon(Icons.sync)),
                        IconButton(key: Key('local-remove-root-${root['id']}'), tooltip: 'Убрать из MusicArk', onPressed: _busy ? null : () => _removeFolder(root), icon: const Icon(Icons.close)),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: _roots.isEmpty && !_busy
                ? Center(
                    key: const Key('local-empty'),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.library_music_outlined, size: 56),
                        const SizedBox(height: 12),
                        const Text('Добавьте папку с музыкой, чтобы создать локальный индекс.'),
                        const SizedBox(height: 12),
                        FilledButton(onPressed: _addFolder, child: const Text('Добавить папку')),
                      ],
                    ),
                  )
                : ListView.builder(
                    key: const Key('local-track-list'),
                    itemCount: _tracks.length + (_tracks.length < _total ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index >= _tracks.length) {
                        return Center(child: Padding(padding: const EdgeInsets.all(16), child: OutlinedButton(key: const Key('local-load-more'), onPressed: _busy ? null : _loadMore, child: const Text('Показать ещё'))));
                      }
                      final track = _tracks[index];
                      return ListTile(
                        key: Key('local-track-${track['id']}'),
                        leading: const Icon(Icons.audiotrack),
                        title: Text((track['title'] ?? track['fileName'] ?? 'Unknown').toString()),
                        subtitle: Text('${_artists(track)} • ${track['album'] ?? '—'} • ${track['codec'] ?? track['extension'] ?? '—'}'),
                        trailing: Text(_duration(track['durationSeconds'])),
                        onTap: () => _showDetails(track),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
