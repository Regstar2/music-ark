import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'external_metadata_bridge.dart';
import 'metadata_bridge.dart';
import 'musicark_bridge.dart';
import 'v012_strings.dart';

class MetadataEditorPage extends StatefulWidget {
  const MetadataEditorPage({
    super.key,
    required this.localFileId,
    required this.bridge,
    this.externalBridge = const ExternalMetadataBridge(),
  });

  final int localFileId;
  final MetadataBridgeClient bridge;
  final ExternalMetadataBridgeClient externalBridge;

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
  String? _success;

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
      _controller('fileName').text = '${document['fileName'] ?? ''}';
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
    final currentFileName = _controller('fileName').text.trim();
    final originalFileName = '${_document?['fileName'] ?? ''}'.trim();
    if (currentFileName != originalFileName) result['fileName'] = currentFileName;
    if (_artworkImagePath != null) result['artworkImagePath'] = _artworkImagePath;
    if (_removeArtwork) result['removeArtwork'] = true;
    if (_advancedTextFrames.isNotEmpty) result['textFrames'] = _advancedTextFrames;
    if (_advancedDirty) result['customTextTags'] = _customTags;
    return result;
  }

  String _resultMessage(
    Map<String, dynamic> response, {
    required bool bindIdentity,
    required bool fromYandex,
  }) {
    final yandex = Map<String, dynamic>.from(response['yandex'] as Map? ?? const {});
    final fields = (yandex['appliedFields'] as List? ?? const []).map((value) => '$value').toList();
    final rename = Map<String, dynamic>.from(response['fileRename'] as Map? ?? const {});
    final parts = <String>[];
    if (fromYandex) {
      parts.add(fields.isEmpty
          ? 'Данные Яндекс Музыки применены.'
          : 'Применены поля: ${fields.map(_fieldLabel).join(', ')}.');
    } else {
      parts.add('Изменения сохранены в аудиофайл.');
    }
    if (rename['changed'] == true) {
      parts.add('Файл переименован: ${rename['fileName'] ?? '—'}.');
    }
    parts.add('Локальный индекс обновлён, Matching пересчитан.');
    if (bindIdentity) {
      parts.add('Exact-связь с выбранным треком Яндекс Музыки сохранена.');
    }
    return parts.join(' ');
  }

  void _setSuccess(String message) {
    if (!mounted) return;
    setState(() => _success = message);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
      _success = null;
    });
    try {
      final response = await widget.bridge.updateMetadata(widget.localFileId, _changes());
      await _load();
      if (!mounted) return;
      _setSuccess(_resultMessage(response, bindIdentity: false, fromYandex: false));
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

  String _searchArtistHint() {
    for (final value in _artists) {
      final clean = value.trim();
      if (clean.isNotEmpty && clean.toLowerCase() != 'drivemusic.me') return clean;
    }
    return '';
  }

  Future<void> _searchYandex() async {
    final title = TextEditingController(text: _controller('title').text.trim());
    final artist = TextEditingController(text: _searchArtistHint());
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
                title: title.text.trim(),
                artist: artist.text.trim(),
              );
              if (!dialogContext.mounted) return;
              items = (response['items'] as List? ?? const [])
                  .whereType<Map>()
                  .map((item) => Map<String, dynamic>.from(item))
                  .toList();
              if (title.text.trim().isEmpty) title.text = '${response['titleQuery'] ?? ''}';
              if (artist.text.trim().isEmpty) artist.text = '${response['artistQuery'] ?? ''}';
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
              width: 820,
              height: 600,
              child: Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          key: const Key('yandex-search-title'),
                          controller: title,
                          onSubmitted: (_) => runSearch(),
                          decoration: const InputDecoration(
                            labelText: 'Название песни',
                            prefixIcon: Icon(Icons.music_note_outlined),
                            border: OutlineInputBorder(),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextField(
                          key: const Key('yandex-search-artist'),
                          controller: artist,
                          onSubmitted: (_) => runSearch(),
                          decoration: const InputDecoration(
                            labelText: 'Исполнитель',
                            prefixIcon: Icon(Icons.person_outline),
                            border: OutlineInputBorder(),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        key: const Key('yandex-search-run'),
                        tooltip: 'Искать',
                        onPressed: loading ? null : runSearch,
                        icon: const Icon(Icons.search),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
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
    title.dispose();
    artist.dispose();
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
                    final response = await widget.bridge.applyYandex(
                      widget.localFileId,
                      externalId,
                      selected.entries.where((entry) => entry.value).map((entry) => entry.key).toList(),
                      bindIdentity: bind,
                    );
                    await _load();
                    if (mounted) {
                      _setSuccess(_resultMessage(response, bindIdentity: bind, fromYandex: true));
                    }
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
                                  title: Text(_fieldLabel('${row['field']}')),
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

  Future<void> _searchExternal() async {
    final strings = V012Strings.of(context);
    var items = <Map<String, dynamic>>[];
    var sourceStates = <Map<String, dynamic>>[];
    var loading = false;
    var initialSearch = false;
    String? searchError;

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) {
          Future<void> runSearch({bool alternatives = false}) async {
            if (loading) return;
            setDialogState(() {
              loading = true;
              searchError = null;
            });
            try {
              final response = await widget.externalBridge.identify(
                widget.localFileId,
                continueSearch: alternatives,
              );
              if (!dialogContext.mounted) return;
              items = (response['items'] as List? ?? const [])
                  .whereType<Map>()
                  .map((item) => Map<String, dynamic>.from(item))
                  .toList();
              sourceStates = (response['sources'] as List? ?? const [])
                  .whereType<Map>()
                  .map((item) => Map<String, dynamic>.from(item))
                  .toList();
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
            key: const Key('external-metadata-dialog'),
            title: Text(strings.externalMetadata),
            content: SizedBox(
              width: 860,
              height: 620,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (loading) const LinearProgressIndicator(key: Key('external-metadata-loading')),
                  if (searchError != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Text(searchError!, key: const Key('external-metadata-error')),
                    ),
                  if (sourceStates.isNotEmpty)
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        for (final state in sourceStates)
                          Chip(
                            label: Text('${state['source'] ?? 'source'}: ${state['state'] ?? 'unknown'}'),
                          ),
                      ],
                    ),
                  const SizedBox(height: 8),
                  Expanded(
                    child: items.isEmpty && !loading
                        ? const Center(child: Text('Подходящие внешние метаданные не найдены.'))
                        : ListView.builder(
                            key: const Key('external-metadata-results'),
                            itemCount: items.length,
                            itemBuilder: (context, index) {
                              final item = items[index];
                              final fields = Map<String, dynamic>.from(item['fields'] as Map? ?? const {});
                              final artwork = Map<String, dynamic>.from(item['artwork'] as Map? ?? const {});
                              final evidence = (item['evidence'] as List? ?? const [])
                                  .whereType<Map>()
                                  .map((value) => '${value['type'] ?? ''}')
                                  .where((value) => value.isNotEmpty)
                                  .take(2)
                                  .join(' + ');
                              final candidateId = '${item['candidateId'] ?? ''}';
                              final source = '${item['sourceDisplayName'] ?? item['source'] ?? 'External'}';
                              final artists = _strings(fields['artists']).join(', ');
                              final album = '${fields['album'] ?? '—'}';
                              final year = '${fields['year'] ?? '—'}';
                              final confidence = '${item['confidence'] ?? 'possible'}';
                              return Card(
                                key: Key('external-candidate-$candidateId'),
                                child: ListTile(
                                  leading: _ArtworkThumb(path: '${artwork['cachePath'] ?? ''}', size: 52),
                                  title: Text('${fields['title'] ?? '—'}'),
                                  subtitle: Text('$source • $confidence\n${artists.isEmpty ? '—' : artists}\n$album • $year${evidence.isEmpty ? '' : ' • $evidence'}'),
                                  isThreeLine: true,
                                  onTap: candidateId.isEmpty
                                      ? null
                                      : () async {
                                          final applied = await _showExternalCompare(candidateId);
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
              TextButton(
                key: const Key('external-more-alternatives'),
                onPressed: loading ? null : () => runSearch(alternatives: true),
                child: Text(strings.moreAlternatives),
              ),
              TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Закрыть')),
            ],
          );
        },
      ),
    );
  }

  Future<bool> _showExternalCompare(String candidateId) async {
    try {
      final response = await widget.externalBridge.compare(widget.localFileId, candidateId);
      if (!mounted) return false;
      final rows = (response['rows'] as List? ?? const [])
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList();
      final external = Map<String, dynamic>.from(response['external'] as Map? ?? const {});
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
                Future<void> apply() async {
                  if (applying) return;
                  setDialogState(() {
                    applying = true;
                    applyError = null;
                  });
                  try {
                    final fields = selected.entries
                        .where((entry) => entry.value)
                        .map((entry) => entry.key)
                        .toList();
                    final result = await widget.externalBridge.apply(
                      widget.localFileId,
                      candidateId,
                      fields,
                    );
                    await _load();
                    final applied = ((result['external'] as Map?)?['appliedFields'] as List? ?? const [])
                        .map((value) => _fieldLabel('$value'))
                        .toList();
                    if (mounted) {
                      _setSuccess(applied.isEmpty
                          ? 'Внешние метаданные применены.'
                          : 'Применены внешние поля: ${applied.join(', ')}. Yandex identity не изменена.');
                    }
                    if (dialogContext.mounted) Navigator.pop(dialogContext, true);
                  } on MusicArkBridgeException catch (error) {
                    applyError = error.message;
                    if (dialogContext.mounted) setDialogState(() => applying = false);
                  }
                }

                return AlertDialog(
                  key: const Key('external-compare-dialog'),
                  title: Text('Local ↔ ${external['sourceDisplayName'] ?? external['source'] ?? 'External'}'),
                  content: SizedBox(
                    width: 900,
                    height: 600,
                    child: Column(
                      children: [
                        if (applyError != null) Text(applyError!, key: const Key('external-compare-error')),
                        if (applying) const LinearProgressIndicator(),
                        Expanded(
                          child: ListView(
                            children: [
                              for (final row in rows)
                                CheckboxListTile(
                                  key: Key('external-compare-field-${row['field']}'),
                                  value: selected['${row['field']}'] == true,
                                  onChanged: row['available'] == true && !applying
                                      ? (value) => setDialogState(() => selected['${row['field']}'] = value == true)
                                      : null,
                                  title: Text(_fieldLabel('${row['field']}')),
                                  subtitle: Text('LOCAL: ${_display(row['local'])}\nEXTERNAL: ${_display(row['external'])}\nSOURCE: ${row['source'] ?? external['source'] ?? '—'}'),
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
                    FilledButton(
                      key: const Key('external-compare-apply'),
                      onPressed: applying || !selected.values.any((value) => value) ? null : apply,
                      child: Text(V012Strings.of(context).applySelected),
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

  String _fieldLabel(String field) => switch (field) {
        'title' => 'Название',
        'artists' => 'Исполнители',
        'album' => 'Альбом',
        'albumArtists' => 'Исполнители альбома',
        'releaseDate' => 'Дата',
        'year' => 'Год',
        'genres' => 'Жанры',
        'isrc' => 'ISRC',
        'publisher' => 'Publisher',
        'label' => 'Label',
        'copyright' => 'Copyright',
        'explicit' => 'Explicit',
        'artwork' => 'Обложка',
        'fileName' => 'Имя файла',
        _ => field,
      };

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

  void _suggestFileNameFromFields() {
    final title = _controller('title').text.trim();
    var artist = '';
    for (final value in _artists) {
      final clean = value.trim();
      if (clean.isNotEmpty && clean.toLowerCase() != 'drivemusic.me') {
        artist = clean;
        break;
      }
    }
    if (title.isEmpty) return;
    final suffix = '.mp3';
    final stem = artist.isEmpty ? title : '$artist - $title';
    setState(() => _controller('fileName').text = '$stem$suffix');
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
    final externalStrings = V012Strings.of(context);

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
                  if (_success != null)
                    Card(
                      key: const Key('metadata-success'),
                      child: ListTile(
                        leading: const Icon(Icons.check_circle_outline),
                        title: const Text('Изменения применены'),
                        subtitle: Text(_success!),
                      ),
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
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(child: _field('fileName', 'Имя файла')),
                                const SizedBox(width: 8),
                                Padding(
                                  padding: const EdgeInsets.only(top: 8),
                                  child: OutlinedButton.icon(
                                    key: const Key('metadata-suggest-filename'),
                                    onPressed: writable ? _suggestFileNameFromFields : null,
                                    icon: const Icon(Icons.auto_fix_high_outlined),
                                    label: const Text('Автор - название'),
                                  ),
                                ),
                              ],
                            ),
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
                        key: const Key('metadata-external-identify'),
                        onPressed: _busy ? null : _searchExternal,
                        icon: const Icon(Icons.auto_fix_high_outlined),
                        label: Text(externalStrings.automaticIdentify),
                      ),
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
