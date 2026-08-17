import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'metadata_bridge.dart';
import 'musicark_bridge.dart';

class MetadataEditorPage extends StatefulWidget {
  const MetadataEditorPage({
    super.key,
    required this.localFileId,
    required this.bridge,
  });

  final int localFileId;
  final MetadataBridgeClient bridge;

  @override
  State<MetadataEditorPage> createState() => _MetadataEditorPageState();
}

class _MetadataEditorPageState extends State<MetadataEditorPage> {
  static const _scalarFields = <String>[
    'title', 'subtitle', 'version', 'album', 'trackNumber', 'totalTracks',
    'discNumber', 'totalDiscs', 'releaseDate', 'year', 'isrc', 'publisher',
    'label', 'copyright', 'composer', 'lyricist', 'bpm', 'comment', 'grouping',
    'lyrics',
  ];
  static const _integerFields = <String>{
    'trackNumber', 'totalTracks', 'discNumber', 'totalDiscs', 'year',
  };

  final Map<String, TextEditingController> _controllers = {};
  final Map<String, List<String>> _advancedTextFrames = {};
  final List<Map<String, dynamic>> _customTags = [];
  Map<String, dynamic>? _document;
  List<String> _artists = [];
  List<String> _albumArtists = [];
  List<String> _genres = [];
  bool? _explicit;
  bool _busy = true;
  bool _advancedDirty = false;
  bool _removeArtwork = false;
  String? _artworkImagePath;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  TextEditingController _controller(String name) =>
      _controllers.putIfAbsent(name, TextEditingController.new);

  List<String> _strings(dynamic value) => value is List
      ? value.map((item) => '$item'.trim()).where((item) => item.isNotEmpty).toList()
      : <String>[];

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        _busy = true;
        _error = null;
      });
    }
    try {
      final response = await widget.bridge.getMetadata(widget.localFileId);
      final document = Map<String, dynamic>.from(response['metadata'] as Map);
      final fields = Map<String, dynamic>.from(document['fields'] as Map? ?? const {});
      for (final name in _scalarFields) {
        _controller(name).text = fields[name] == null ? '' : '${fields[name]}';
      }
      _artists = _strings(fields['artists']);
      _albumArtists = _strings(fields['albumArtists']);
      _genres = _strings(fields['genres']);
      _explicit = fields['explicit'] is bool ? fields['explicit'] as bool : null;
      _advancedTextFrames.clear();
      _customTags.clear();
      for (final raw in (document['allTags'] as List? ?? const []).whereType<Map>()) {
        final tag = Map<String, dynamic>.from(raw);
        if ('${tag['frameId'] ?? ''}' == 'TXXX' &&
            tag['provenance'] != true &&
            '${tag['description'] ?? ''}'.trim().isNotEmpty) {
          _customTags.add({
            'description': '${tag['description']}'.trim(),
            'values': _strings(tag['values']),
          });
        }
      }
      if (!mounted) return;
      setState(() {
        _document = document;
        _advancedDirty = false;
        _removeArtwork = false;
        _artworkImagePath = null;
      });
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  dynamic _scalarValue(String name) {
    final raw = _controller(name).text;
    if (_integerFields.contains(name)) {
      final value = raw.trim();
      return value.isEmpty ? null : int.tryParse(value);
    }
    return name == 'comment' || name == 'lyrics' ? raw : raw.trim();
  }

  bool _same(dynamic left, dynamic right) {
    if ((left == null || left == '') && (right == null || right == '')) return true;
    if (left is List && right is List) {
      if (left.length != right.length) return false;
      for (var i = 0; i < left.length; i++) {
        if ('${left[i]}' != '${right[i]}') return false;
      }
      return true;
    }
    return '$left' == '$right';
  }

  Map<String, dynamic> _changes() {
    final original = Map<String, dynamic>.from(_document?['fields'] as Map? ?? const {});
    final current = <String, dynamic>{
      for (final name in _scalarFields) name: _scalarValue(name),
      'artists': _artists,
      'albumArtists': _albumArtists,
      'genres': _genres,
      'explicit': _explicit,
    };
    final result = <String, dynamic>{};
    for (final entry in current.entries) {
      if (!_same(entry.value, original[entry.key])) result[entry.key] = entry.value;
    }
    if (_artworkImagePath != null) result['artworkImagePath'] = _artworkImagePath;
    if (_removeArtwork) result['removeArtwork'] = true;
    if (_advancedTextFrames.isNotEmpty) result['textFrames'] = _advancedTextFrames;
    if (_advancedDirty) result['customTextTags'] = _customTags;
    return result;
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.bridge.updateMetadata(widget.localFileId, _changes());
      await _load();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Метаданные сохранены. Файл переиндексирован, Matching пересчитан.')),
      );
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pickArtwork() async {
    final file = await openFile(
      acceptedTypeGroups: const [
        XTypeGroup(label: 'Images', extensions: ['jpg', 'jpeg', 'png']),
      ],
    );
    if (file == null || !mounted) return;
    setState(() {
      _artworkImagePath = file.path;
      _removeArtwork = false;
    });
  }

  Future<void> _searchYandex() async {
    final query = TextEditingController();
    var items = <Map<String, dynamic>>[];
    var loading = false;
    var initialSearch = false;
    String? searchError;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) {
          Future<void> runSearch() async {
            if (loading) return;
            setDialogState(() {
              loading = true;
              searchError = null;
            });
            try {
              final response = await widget.bridge.searchYandex(
                widget.localFileId,
                query: query.text.trim(),
              );
              if (!dialogContext.mounted) return;
              items = (response['items'] as List? ?? const [])
                  .whereType<Map>()
                  .map((item) => Map<String, dynamic>.from(item))
                  .toList();
              if (query.text.trim().isEmpty) query.text = '${response['query'] ?? ''}';
            } on MusicArkBridgeException catch (error) {
              searchError = error.message;
            } finally {
              if (dialogContext.mounted) setDialogState(() => loading = false);
            }
          }

          if (!initialSearch) {
            initialSearch = true;
            WidgetsBinding.instance.addPostFrameCallback((_) => runSearch());
          }
          return AlertDialog(
            key: const Key('yandex-search-dialog'),
            title: const Text('Получить данные из Яндекс Музыки'),
            content: SizedBox(
              width: 760,
              height: 560,
              child: Column(
                children: [
                  TextField(
                    key: const Key('yandex-search-query'),
                    controller: query,
                    onSubmitted: (_) => runSearch(),
                    decoration: InputDecoration(
                      labelText: 'Поиск',
                      suffixIcon: IconButton(
                        onPressed: loading ? null : runSearch,
                        icon: const Icon(Icons.search),
                      ),
                    ),
                  ),
                  if (loading) const LinearProgressIndicator(key: Key('yandex-search-loading')),
                  if (searchError != null)
                    Text(searchError!, key: const Key('yandex-search-error')),
                  Expanded(
                    child: ListView.builder(
                      key: const Key('yandex-search-results'),
                      itemCount: items.length,
                      itemBuilder: (context, index) {
                        final item = items[index];
                        final fields = Map<String, dynamic>.from(item['fields'] as Map? ?? const {});
                        final identity = Map<String, dynamic>.from(item['identity'] as Map? ?? const {});
                        final artwork = Map<String, dynamic>.from(item['artwork'] as Map? ?? const {});
                        final externalId = '${identity['externalId'] ?? ''}';
                        final score = ((double.tryParse('${item['similarity'] ?? 0}') ?? 0) * 100).round();
                        return Card(
                          key: Key('yandex-result-$externalId'),
                          child: ListTile(
                            leading: _ArtworkThumb(path: '${artwork['cachePath'] ?? ''}', size: 52),
                            title: Text('${fields['title'] ?? '—'}'),
                            subtitle: Text('${_strings(fields['artists']).join(', ')}\n${fields['album'] ?? '—'} • ${fields['year'] ?? '—'} • $score%'),
                            isThreeLine: true,
                            trailing: Text('ID: $externalId'),
                            onTap: externalId.isEmpty
                                ? null
                                : () async {
                                    final applied = await _showCompare(externalId);
                                    if (applied && dialogContext.mounted) Navigator.pop(dialogContext);
                                  },
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Закрыть')),
            ],
          );
        },
      ),
    );
    query.dispose();
    if (mounted) await _load();
  }

  Future<bool> _showCompare(String externalId) async {
    try {
      final response = await widget.bridge.compareYandex(widget.localFileId, externalId);
      if (!mounted) return false;
      final rows = (response['rows'] as List? ?? const [])
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList();
      final selected = <String, bool>{
        for (final row in rows)
          '${row['field']}': row['available'] == true && row['selected'] == true,
      };
      return await showDialog<bool>(
            context: context,
            builder: (dialogContext) => StatefulBuilder(
              builder: (context, setDialogState) {
                var applying = false;
                String? applyError;
                Future<void> apply(bool bind) async {
                  if (applying) return;
                  setDialogState(() {
                    applying = true;
                    applyError = null;
                  });
                  try {
                    await widget.bridge.applyYandex(
                      widget.localFileId,
                      externalId,
                      selected.entries.where((entry) => entry.value).map((entry) => entry.key).toList(),
                      bindIdentity: bind,
                    );
                    if (dialogContext.mounted) Navigator.pop(dialogContext, true);
                  } on MusicArkBridgeException catch (error) {
                    applyError = error.message;
                    if (dialogContext.mounted) setDialogState(() => applying = false);
                  }
                }

                return AlertDialog(
                  key: const Key('metadata-compare-dialog'),
                  title: const Text('Сравнение Local ↔ Yandex'),
                  content: SizedBox(
                    width: 900,
                    height: 600,
                    child: Column(
                      children: [
                        Row(
                          children: [
                            TextButton(
                              key: const Key('compare-select-all'),
                              onPressed: applying
                                  ? null
                                  : () => setDialogState(() {
                                        for (final row in rows) {
                                          if (row['available'] == true) selected['${row['field']}'] = true;
                                        }
                                      }),
                              child: const Text('Выбрать всё'),
                            ),
                            TextButton(
                              key: const Key('compare-select-none'),
                              onPressed: applying
                                  ? null
                                  : () => setDialogState(() {
                                        for (final key in selected.keys) {
                                          selected[key] = false;
                                        }
                                      }),
                              child: const Text('Снять всё'),
                            ),
                          ],
                        ),
                        if (applyError != null) Text(applyError!, key: const Key('compare-error')),
                        if (applying) const LinearProgressIndicator(),
                        const Divider(),
                        Expanded(
                          child: ListView(
                            children: [
                              for (final row in rows)
                                CheckboxListTile(
                                  key: Key('compare-field-${row['field']}'),
                                  value: selected['${row['field']}'] == true,
                                  onChanged: row['available'] == true && !applying
                                      ? (value) => setDialogState(() => selected['${row['field']}'] = value == true)
                                      : null,
                                  title: Text('${row['field']}'),
                                  subtitle: Text('LOCAL: ${_display(row['local'])}\nYANDEX: ${_display(row['yandex'])}'),
                                  controlAffinity: ListTileControlAffinity.leading,
                                ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  actions: [
                    TextButton(onPressed: applying ? null : () => Navigator.pop(dialogContext, false), child: const Text('Отмена')),
                    FilledButton.tonal(
                      key: const Key('compare-apply-metadata'),
                      onPressed: applying ? null : () => apply(false),
                      child: const Text('Применить метаданные'),
                    ),
                    FilledButton(
                      key: const Key('compare-apply-bind'),
                      onPressed: applying ? null : () => apply(true),
                      child: const Text('Применить и связать'),
                    ),
                  ],
                );
              },
            ),
          ) ??
          false;
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _error = error.message);
      return false;
    }
  }

  String _display(dynamic value) {
    if (value == null) return '—';
    if (value is List) return value.isEmpty ? '—' : value.join(', ');
    return '$value'.trim().isEmpty ? '—' : '$value';
  }

  Future<void> _editRawTag(Map<String, dynamic> tag) async {
    if (tag['editable'] != true) return;
    final frameId = '${tag['frameId'] ?? ''}';
    final description = '${tag['description'] ?? ''}'.trim();
    final controller = TextEditingController(text: _strings(tag['values']).join('; '));
    final value = await showDialog<String?>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(description.isEmpty ? frameId : '$frameId:$description'),
        content: TextField(controller: controller, decoration: const InputDecoration(labelText: 'Значения через ;')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Отмена')),
          TextButton(onPressed: () => Navigator.pop(context, ''), child: const Text('Удалить')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text), child: const Text('Сохранить')),
        ],
      ),
    );
    controller.dispose();
    if (value == null || !mounted) return;
    final values = value.split(';').map((item) => item.trim()).where((item) => item.isNotEmpty).toList();
    setState(() {
      _advancedDirty = true;
      if (frameId == 'TXXX') {
        final index = _customTags.indexWhere((item) => '${item['description']}' == description);
        final replacement = {'description': description, 'values': values};
        if (index >= 0) {
          _customTags[index] = replacement;
        } else if (description.isNotEmpty) {
          _customTags.add(replacement);
        }
      } else {
        _advancedTextFrames[frameId] = values;
      }
    });
  }

  Future<void> _addCustomTag() async {
    final description = TextEditingController();
    final values = TextEditingController();
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Добавить TXXX'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: description, decoration: const InputDecoration(labelText: 'Description')),
            TextField(controller: values, decoration: const InputDecoration(labelText: 'Значения через ;')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Отмена')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Добавить')),
        ],
      ),
    );
    if (accepted == true && description.text.trim().isNotEmpty && mounted) {
      setState(() {
        _advancedDirty = true;
        _customTags.add({
          'description': description.text.trim(),
          'values': values.text.split(';').map((item) => item.trim()).where((item) => item.isNotEmpty).toList(),
        });
      });
    }
    description.dispose();
    values.dispose();
  }

  Widget _field(String name, String label, {int maxLines = 1}) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: TextField(
          key: Key('metadata-field-$name'),
          controller: _controller(name),
          enabled: _document?['writable'] == true,
          maxLines: maxLines,
          decoration: InputDecoration(labelText: label, border: const OutlineInputBorder()),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final document = _document;
    final writable = document?['writable'] == true;
    final artwork = Map<String, dynamic>.from(document?['artwork'] as Map? ?? const {});
    final identity = Map<String, dynamic>.from(document?['identity'] as Map? ?? const {});
    final tags = (document?['allTags'] as List? ?? const [])
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
    final artworkPath = _removeArtwork ? '' : (_artworkImagePath ?? '${artwork['cachePath'] ?? ''}');

    return Scaffold(
      key: const Key('metadata-editor-page'),
      appBar: AppBar(title: const Text('Редактор метаданных')),
      body: _busy && document == null
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (_busy) const LinearProgressIndicator(),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(_error!, key: const Key('metadata-error')),
                    ),
                  if (!writable)
                    const Card(
                      child: Padding(
                        padding: EdgeInsets.all(12),
                        child: Text('В этой версии безопасная запись реализована для MP3/ID3. Остальные форматы доступны только для просмотра.'),
                      ),
                    ),
                  Wrap(
                    spacing: 20,
                    runSpacing: 16,
                    crossAxisAlignment: WrapCrossAlignment.start,
                    children: [
                      SizedBox(
                        width: 230,
                        child: Column(
                          children: [
                            _ArtworkThumb(path: artworkPath, size: 210),
                            const SizedBox(height: 8),
                            Text('${artwork['width'] ?? '—'}×${artwork['height'] ?? '—'} • ${artwork['mime'] ?? '—'} • ${artwork['byteSize'] ?? '—'} B'),
                            Wrap(
                              children: [
                                TextButton.icon(
                                  onPressed: writable ? _pickArtwork : null,
                                  icon: const Icon(Icons.image_outlined),
                                  label: const Text('Заменить'),
                                ),
                                TextButton.icon(
                                  key: const Key('metadata-remove-artwork'),
                                  onPressed: writable
                                      ? () => setState(() {
                                            _removeArtwork = true;
                                            _artworkImagePath = null;
                                          })
                                      : null,
                                  icon: const Icon(Icons.delete_outline),
                                  label: const Text('Удалить'),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                      SizedBox(
                        width: 760,
                        child: Column(
                          children: [
                            _field('title', 'Название'),
                            Row(children: [Expanded(child: _field('subtitle', 'Subtitle')), const SizedBox(width: 12), Expanded(child: _field('version', 'Version'))]),
                            _ListEditor(key: const Key('metadata-artists'), label: 'Исполнители', values: _artists, enabled: writable, onChanged: (values) => setState(() => _artists = values)),
                            _field('album', 'Альбом'),
                            _ListEditor(key: const Key('metadata-album-artists'), label: 'Исполнители альбома', values: _albumArtists, enabled: writable, onChanged: (values) => setState(() => _albumArtists = values)),
                            Row(children: [Expanded(child: _field('trackNumber', 'Track')), const SizedBox(width: 12), Expanded(child: _field('totalTracks', 'Всего треков')), const SizedBox(width: 12), Expanded(child: _field('discNumber', 'Disc')), const SizedBox(width: 12), Expanded(child: _field('totalDiscs', 'Всего дисков'))]),
                            Row(children: [Expanded(child: _field('releaseDate', 'Дата')), const SizedBox(width: 12), Expanded(child: _field('year', 'Год'))]),
                            _ListEditor(key: const Key('metadata-genres'), label: 'Жанры', values: _genres, enabled: writable, onChanged: (values) => setState(() => _genres = values)),
                            Row(children: [Expanded(child: _field('isrc', 'ISRC')), const SizedBox(width: 12), Expanded(child: _field('bpm', 'BPM'))]),
                            Row(children: [Expanded(child: _field('publisher', 'Publisher')), const SizedBox(width: 12), Expanded(child: _field('label', 'Label'))]),
                            _field('copyright', 'Copyright'),
                            Row(children: [Expanded(child: _field('composer', 'Composer')), const SizedBox(width: 12), Expanded(child: _field('lyricist', 'Lyricist'))]),
                            _field('grouping', 'Grouping'),
                            _field('comment', 'Comment', maxLines: 3),
                            _field('lyrics', 'Lyrics', maxLines: 6),
                            DropdownButtonFormField<String>(
                              key: const Key('metadata-explicit'),
                              value: _explicit == null ? '' : (_explicit! ? 'yes' : 'no'),
                              decoration: const InputDecoration(labelText: 'Explicit'),
                              items: const [
                                DropdownMenuItem(value: '', child: Text('Не указано')),
                                DropdownMenuItem(value: 'no', child: Text('Нет')),
                                DropdownMenuItem(value: 'yes', child: Text('Да')),
                              ],
                              onChanged: writable
                                  ? (value) => setState(() => _explicit = value == '' ? null : value == 'yes')
                                  : null,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(
                        identity['status'] == 'exact'
                            ? 'Yandex identity: Exact\nTrack ID: ${identity['externalId']}\nConfidence: ${identity['confidence']}'
                            : 'Yandex identity: не установлена',
                        key: const Key('metadata-identity'),
                      ),
                    ),
                  ),
                  ExpansionTile(
                    key: const Key('metadata-all-tags'),
                    title: const Text('Все теги'),
                    subtitle: Text('${tags.length} ID3 frames'),
                    children: [
                      for (final tag in tags)
                        ListTile(
                          key: Key('metadata-tag-${tag['key']}'),
                          title: Text('${tag['key']}'),
                          subtitle: Text(_strings(tag['values']).join(' • ')),
                          trailing: tag['editable'] == true ? const Icon(Icons.edit_outlined) : null,
                          onTap: tag['editable'] == true && writable ? () => _editRawTag(tag) : null,
                        ),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: TextButton.icon(
                          key: const Key('metadata-add-custom-tag'),
                          onPressed: writable ? _addCustomTag : null,
                          icon: const Icon(Icons.add),
                          label: const Text('Добавить custom text tag (TXXX)'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 12,
                    runSpacing: 8,
                    alignment: WrapAlignment.end,
                    children: [
                      OutlinedButton.icon(
                        key: const Key('metadata-yandex-search'),
                        onPressed: _busy ? null : _searchYandex,
                        icon: const Icon(Icons.cloud_download_outlined),
                        label: const Text('Получить данные из Яндекс Музыки'),
                      ),
                      TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Отмена')),
                      FilledButton.icon(
                        key: const Key('metadata-save'),
                        onPressed: _busy || !writable ? null : _save,
                        icon: const Icon(Icons.save_outlined),
                        label: const Text('Сохранить'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
    );
  }
}

class _ArtworkThumb extends StatelessWidget {
  const _ArtworkThumb({required this.path, required this.size});

  final String path;
  final double size;

  @override
  Widget build(BuildContext context) {
    final file = path.isEmpty ? null : File(path);
    return ClipRRect(
      borderRadius: BorderRadius.circular(6),
      child: SizedBox(
        width: size,
        height: size,
        child: file != null && file.existsSync()
            ? Image.file(file, fit: BoxFit.cover, cacheWidth: size.round(), cacheHeight: size.round())
            : ColoredBox(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                child: Icon(Icons.album_outlined, size: size * .45),
              ),
      ),
    );
  }
}

class _ListEditor extends StatefulWidget {
  const _ListEditor({
    super.key,
    required this.label,
    required this.values,
    required this.enabled,
    required this.onChanged,
  });

  final String label;
  final List<String> values;
  final bool enabled;
  final ValueChanged<List<String>> onChanged;

  @override
  State<_ListEditor> createState() => _ListEditorState();
}

class _ListEditorState extends State<_ListEditor> {
  final TextEditingController _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _add() {
    final value = _controller.text.trim();
    if (value.isEmpty) return;
    widget.onChanged([...widget.values, value]);
    _controller.clear();
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: InputDecorator(
          decoration: InputDecoration(labelText: widget.label, border: const OutlineInputBorder()),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: [
                  for (var index = 0; index < widget.values.length; index++)
                    InputChip(
                      label: Text(widget.values[index]),
                      onDeleted: widget.enabled
                          ? () {
                              final values = [...widget.values]..removeAt(index);
                              widget.onChanged(values);
                            }
                          : null,
                    ),
                ],
              ),
              if (widget.enabled)
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        onSubmitted: (_) => _add(),
                        decoration: const InputDecoration(hintText: 'Добавить'),
                      ),
                    ),
                    IconButton(onPressed: _add, icon: const Icon(Icons.add)),
                  ],
                ),
            ],
          ),
        ),
      );
}
