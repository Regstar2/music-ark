import 'dart:io';

import 'package:flutter/material.dart';

import 'app_localizations_ext.dart';
import 'app_ui_tokens.dart';
import 'content_label_bridge.dart';
import 'desktop_file_actions.dart';
import 'folder_picker.dart';
import 'metadata_bridge.dart';
import 'metadata_editor_page.dart';
import 'musicark_bridge.dart';
import 'v0111_localizations_ext.dart';
import 'yandex_batch_upload_bridge.dart';
import 'yandex_batch_upload_dialog.dart';
import 'yandex_upload_bridge.dart';
import 'yandex_upload_dialog.dart';

enum _TrackMenuAction { details, reveal }

enum _RootMenuAction { remove }

class LocalLibraryPage extends StatefulWidget {
  LocalLibraryPage({
    super.key,
    required this.bridge,
    LocalFolderPicker? folderPicker,
    this.fileActions = const SystemLocalFileActions(),
    MetadataBridgeClient? metadataBridge,
    ContentLabelBridgeClient? contentLabelBridge,
    YandexUploadBridgeClient? yandexUploadBridge,
    YandexBatchUploadBridgeClient? yandexBatchUploadBridge,
  }) : folderPicker = folderPicker ?? const SystemLocalFolderPicker(),
       metadataBridge = metadataBridge ??
           (bridge is MusicArkBridge ? const MetadataBridge() : null),
       contentLabelBridge = contentLabelBridge ??
           (bridge is MusicArkBridge ? const ContentLabelBridge() : null),
       yandexUploadBridge = yandexUploadBridge ??
           (bridge is MusicArkBridge ? const YandexUploadBridge() : null),
       yandexBatchUploadBridge = yandexBatchUploadBridge ??
           (bridge is MusicArkBridge ? const YandexBatchUploadBridge() : null);

  final MusicArkBridgeClient bridge;
  final LocalFolderPicker folderPicker;
  final LocalFileActions fileActions;
  final MetadataBridgeClient? metadataBridge;
  final ContentLabelBridgeClient? contentLabelBridge;
  final YandexUploadBridgeClient? yandexUploadBridge;
  final YandexBatchUploadBridgeClient? yandexBatchUploadBridge;

  @override
  State<LocalLibraryPage> createState() => _LocalLibraryPageState();
}

class _LocalLibraryPageState extends State<LocalLibraryPage> {
  static const _pageSize = 500;
  static const _wideTrackTable = 980.0;

  final _search = TextEditingController();
  List<Map<String, dynamic>> _roots = const [];
  List<Map<String, dynamic>> _tracks = const [];
  Set<int> _selectedRootIds = <int>{};
  Set<int> _selectedTrackIds = <int>{};
  bool _selectionInitialized = false;
  int _total = 0;
  bool _busy = true;
  String _sort = 'artist';
  String? _status;
  bool _statusIsError = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _activate();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  List<Map<String, dynamic>> _maps(dynamic value) => value is List
      ? value
            .whereType<Map>()
            .map((item) => Map<String, dynamic>.from(item))
            .toList(growable: false)
      : <Map<String, dynamic>>[];

  Set<int> _rootIds(Iterable<Map<String, dynamic>> roots) => roots
      .map((root) => int.tryParse('${root['id']}'))
      .whereType<int>()
      .toSet();

  Set<int> _reconciledSelection(List<Map<String, dynamic>> newRoots) {
    final oldIds = _rootIds(_roots);
    final newIds = _rootIds(newRoots);
    if (!_selectionInitialized) return newIds;

    final wasAllSelected =
        _selectedRootIds.length == oldIds.length &&
        _selectedRootIds.containsAll(oldIds);
    final next = _selectedRootIds.where(newIds.contains).toSet();
    if (wasAllSelected) next.addAll(newIds);
    return next;
  }

  bool _allSelected({
    List<Map<String, dynamic>>? roots,
    Set<int>? selected,
  }) {
    final ids = _rootIds(roots ?? _roots);
    final selection = selected ?? _selectedRootIds;
    return ids.isNotEmpty &&
        selection.length == ids.length &&
        selection.containsAll(ids);
  }

  List<int>? _queryRootIds({
    List<Map<String, dynamic>>? roots,
    Set<int>? selected,
  }) {
    final actualRoots = roots ?? _roots;
    final selection = selected ?? _selectedRootIds;
    if (_allSelected(roots: actualRoots, selected: selection)) return null;
    final values = selection.toList()..sort();
    return values;
  }

  String _rootName(Map<String, dynamic> root) {
    final path = '${root['path'] ?? ''}'.trim();
    if (path.isEmpty) return '';
    final parts = path.split(RegExp(r'[\\/]')).where((item) => item.isNotEmpty);
    return parts.isEmpty ? path : parts.last;
  }

  Future<void> _activate() async {
    await _reload();
    if (!mounted || _roots.isEmpty) return;
    await _scan();
  }

  Future<List<Map<String, dynamic>>> _withContentLabels(
    List<Map<String, dynamic>> tracks,
  ) async {
    final labels = widget.contentLabelBridge;
    if (labels == null || tracks.isEmpty) return tracks;
    final ids = tracks
        .map((track) => int.tryParse('${track['id']}'))
        .whereType<int>()
        .toList(growable: false);
    try {
      final payload = await labels.batch(localFileIds: ids);
      final raw = payload['local'];
      final byId = raw is Map
          ? Map<String, dynamic>.from(raw)
          : <String, dynamic>{};
      return tracks.map((track) {
        final copy = Map<String, dynamic>.from(track);
        final label = byId['${track['id']}'];
        if (label != null) copy['contentLabel'] = '$label';
        return copy;
      }).toList(growable: false);
    } on MusicArkBridgeException {
      return tracks;
    }
  }

  Future<void> _setContentLabel(
    Map<String, dynamic> track,
    String label,
  ) async {
    final labels = widget.contentLabelBridge;
    final id = int.tryParse('${track['id']}');
    if (labels == null || id == null) return;
    try {
      await labels.setLocal(id, label);
      if (!mounted) return;
      setState(() {
        _tracks = _tracks.map((item) {
          if ('${item['id']}' != '$id') return item;
          final copy = Map<String, dynamic>.from(item);
          if (label.isEmpty) {
            copy.remove('contentLabel');
          } else {
            copy['contentLabel'] = label;
          }
          return copy;
        }).toList(growable: false);
      });
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _error = error.message);
    }
  }

  Future<List<Map<String, dynamic>>> _withArtwork(
    List<Map<String, dynamic>> tracks,
  ) async {
    final metadata = widget.metadataBridge;
    if (metadata == null || tracks.isEmpty) return tracks;
    final ids = tracks
        .map((track) => int.tryParse('${track['id']}'))
        .whereType<int>()
        .toList();
    try {
      final payload = await metadata.artworkBatch(ids);
      final raw = payload['items'];
      final items = raw is Map
          ? Map<String, dynamic>.from(raw)
          : <String, dynamic>{};
      return tracks.map((track) {
        final copy = Map<String, dynamic>.from(track);
        final artwork = items['${track['id']}'];
        if (artwork is Map) {
          copy['artwork'] = Map<String, dynamic>.from(artwork);
        }
        return copy;
      }).toList(growable: false);
    } on MusicArkBridgeException {
      return tracks;
    }
  }

  Future<void> _reload({bool preserveStatus = false}) async {
    setState(() {
      _busy = true;
      _error = null;
      if (!preserveStatus) {
        _status = null;
        _statusIsError = false;
      }
    });
    try {
      final rootsPayload = await widget.bridge.localRoots();
      final roots = _maps(rootsPayload['items']);
      final selected = _reconciledSelection(roots);
      final tracksPayload = await widget.bridge.localTracks(
        limit: _pageSize,
        offset: 0,
        search: _search.text.trim(),
        sort: _sort,
        rootIds: _queryRootIds(roots: roots, selected: selected),
      );
      var tracks = await _withArtwork(_maps(tracksPayload['items']));
      tracks = await _withContentLabels(tracks);
      if (!mounted) return;
      setState(() {
        _roots = roots;
        _selectedRootIds = selected;
        _selectionInitialized = true;
        _tracks = tracks;
        final visibleIds = tracks
            .map((item) => int.tryParse('${item['id']}'))
            .whereType<int>()
            .toSet();
        _selectedTrackIds = _selectedTrackIds.where(visibleIds.contains).toSet();
        _total = int.tryParse('${tracksPayload['count'] ?? 0}') ?? 0;
      });
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _error = error.message);
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
        rootIds: _queryRootIds(),
      );
      var items = await _withArtwork(_maps(payload['items']));
      items = await _withContentLabels(items);
      if (!mounted) return;
      setState(() {
        _tracks = [..._tracks, ...items];
        _total = int.tryParse('${payload['count'] ?? _total}') ?? _total;
      });
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _error = error.message);
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
      setState(() {
        _status = context.l10n.localFolderAdded;
        _statusIsError = false;
      });
      await _reload(preserveStatus: true);
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _removeFolder(Map<String, dynamic> root) async {
    final id = int.tryParse('${root['id']}');
    if (id == null) return;
    final l10n = context.l10n;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.localRemoveFolderTitle),
        content: Text(l10n.localRemoveFolderBody('${root['path']}')),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(l10n.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(l10n.localRemoveFolder),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _busy = true);
    try {
      await widget.bridge.localRootRemove(id);
      if (!mounted) return;
      setState(() {
        _status = context.l10n.localFolderRemoved;
        _statusIsError = false;
      });
      await _reload(preserveStatus: true);
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _scan({int? rootId}) async {
    setState(() {
      _busy = true;
      _error = null;
      _status = context.l10n.localScanning;
      _statusIsError = false;
    });
    try {
      final result = await widget.bridge.localScan(rootId: rootId);
      if (!mounted) return;
      final added = int.tryParse('${result['added'] ?? 0}') ?? 0;
      final updated = int.tryParse('${result['updated'] ?? 0}') ?? 0;
      final removed = int.tryParse('${result['removed'] ?? 0}') ?? 0;
      final errors = int.tryParse('${result['errors'] ?? 0}') ?? 0;
      final errorItems = _maps(result['errorItems']);
      final firstError = errorItems.isEmpty
          ? ''
          : '${errorItems.first['path'] ?? ''} — ${errorItems.first['error'] ?? ''}';
      setState(() {
        if (errors > 0) {
          _status = context.l10n.localScanErrors(errors, firstError);
          _statusIsError = true;
        } else if (added == 0 && updated == 0 && removed == 0) {
          _status = context.l10n.localScanSuccess;
          _statusIsError = false;
        } else {
          _status = context.l10n.localScanChanged(added, updated, removed);
          _statusIsError = false;
        }
      });
      await _reload(preserveStatus: true);
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _artists(Map<String, dynamic> track) {
    final raw = track['artists'];
    if (raw is List) {
      final text = raw
          .map((item) => item.toString())
          .where((item) => item.isNotEmpty)
          .join(', ');
      if (text.isNotEmpty) return text;
    }
    return context.l10n.localUnknownArtist;
  }

  String _duration(dynamic raw) {
    final seconds = double.tryParse('$raw');
    if (seconds == null || seconds <= 0) return '—';
    final whole = seconds.round();
    return '${whole ~/ 60}:${(whole % 60).toString().padLeft(2, '0')}';
  }

  String _lastScanned(Map<String, dynamic> root) {
    final raw = '${root['lastScannedAt'] ?? ''}'.trim();
    if (raw.isEmpty) return context.l10n.localNeverScanned;
    final parsed = DateTime.tryParse(raw)?.toLocal();
    if (parsed == null) return raw;
    final date =
        '${parsed.day.toString().padLeft(2, '0')}.${parsed.month.toString().padLeft(2, '0')}.${parsed.year}';
    final time =
        '${parsed.hour.toString().padLeft(2, '0')}:${parsed.minute.toString().padLeft(2, '0')}';
    return '$date $time';
  }

  Future<void> _play(Map<String, dynamic> track) async {
    final path = (track['path'] ?? '').toString();
    try {
      await widget.fileActions.play(path);
    } catch (error) {
      if (mounted) {
        setState(() => _error = context.l10n.localPlayFailed('$error'));
      }
    }
  }

  Future<void> _reveal(Map<String, dynamic> track) async {
    final path = (track['path'] ?? '').toString();
    try {
      await widget.fileActions.reveal(path);
    } catch (error) {
      if (mounted) {
        setState(() => _error = context.l10n.localRevealFailed('$error'));
      }
    }
  }

  Future<void> _uploadToYandex(Map<String, dynamic> track) async {
    final bridge = widget.yandexUploadBridge;
    if (bridge == null) return;
    String? preferredKind;
    final batchBridge = widget.yandexBatchUploadBridge;
    if (batchBridge != null) {
      try {
        final managed = await batchBridge.managedPlaylists();
        for (final raw in (managed['roles'] as List? ?? const [])) {
          if (raw is! Map) continue;
          final role = Map<String, dynamic>.from(raw);
          if (role['role'] == 'uploaded' && role['configured'] == true) {
            final candidate = '${role['playlistKind'] ?? ''}'.trim();
            if (candidate.isNotEmpty) preferredKind = candidate;
            break;
          }
        }
      } catch (_) {
        preferredKind = null;
      }
    }
    if (!mounted) return;
    final result = await showYandexUploadDialog(
      context: context,
      track: track,
      bridge: bridge,
      preferredPlaylistKind: preferredKind,
    );
    if (!mounted || result == null) return;
    if (result.status == YandexUploadStatus.verified) {
      setState(() {
        _status = context.l10n.yandexUploadSuccess;
        _statusIsError = false;
      });
    }
  }

  void _toggleTrackSelection(Map<String, dynamic> track, bool selected) {
    final id = int.tryParse('${track['id']}');
    if (id == null) return;
    setState(() {
      if (selected) {
        _selectedTrackIds.add(id);
      } else {
        _selectedTrackIds.remove(id);
      }
    });
  }

  void _selectAllVisibleTracks() {
    setState(() {
      _selectedTrackIds.addAll(
        _tracks.map((track) => int.tryParse('${track['id']}')).whereType<int>(),
      );
    });
  }

  void _clearTrackSelection() => setState(() => _selectedTrackIds.clear());

  List<Map<String, dynamic>> _selectedTracks() => _tracks
      .where((track) => _selectedTrackIds.contains(int.tryParse('${track['id']}')))
      .toList(growable: false);

  Future<void> _bulkUploadToYandex() async {
    final uploadBridge = widget.yandexUploadBridge;
    final batchBridge = widget.yandexBatchUploadBridge;
    final selected = _selectedTracks();
    if (uploadBridge == null || batchBridge == null || selected.isEmpty) return;
    final allRoots = _allSelected();
    final localContext = allRoots
        ? context.l10n.v0111AllFolders
        : _selectedRootIds.length == 1
        ? _singleSelectedRootPath()
        : _folderFilterLabel();
    final result = await showYandexBatchUploadDialog(
      context: context,
      tracks: selected,
      targetBridge: uploadBridge,
      batchBridge: batchBridge,
      localContext: localContext,
      localContextTooltip: _selectedRootIds.length == 1
          ? _singleSelectedRootPath()
          : null,
    );
    if (!mounted || result == null) return;
    setState(() {
      _status = context.l10n.v0111BatchFinished;
      _statusIsError = false;
      _selectedTrackIds.clear();
    });
  }

  Future<void> _edit(Map<String, dynamic> track) async {
    final metadata = widget.metadataBridge;
    final id = int.tryParse('${track['id']}');
    if (metadata == null || id == null) return;
    await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => MetadataEditorPage(localFileId: id, bridge: metadata),
      ),
    );
    if (mounted) await _reload(preserveStatus: true);
  }

  Future<void> _showDetails(Map<String, dynamic> track) async {
    final path = (track['path'] ?? '').toString();
    Map<String, dynamic>? document;
    final id = int.tryParse('${track['id']}');
    if (widget.metadataBridge != null && id != null) {
      try {
        final payload = await widget.metadataBridge!.getMetadata(id);
        document = Map<String, dynamic>.from(
          payload['metadata'] as Map? ?? const {},
        );
      } on MusicArkBridgeException {
        document = null;
      }
    }
    if (!mounted) return;
    final l10n = context.l10n;
    final fields = Map<String, dynamic>.from(
      document?['fields'] as Map? ?? const {},
    );
    final identity = Map<String, dynamic>.from(
      document?['identity'] as Map? ?? const {},
    );
    final artwork = Map<String, dynamic>.from(
      document?['artwork'] as Map? ?? track['artwork'] as Map? ?? const {},
    );
    final albumArtists = fields['albumArtists'] is List
        ? (fields['albumArtists'] as List).join(', ')
        : '—';
    final genres = fields['genres'] is List
        ? (fields['genres'] as List).join(', ')
        : (track['genre'] ?? '—').toString();
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          (track['title'] ?? track['fileName'] ?? l10n.localUnknownTrack)
              .toString(),
        ),
        content: SizedBox(
          width: 720,
          child: SingleChildScrollView(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _LocalArtwork(artwork: artwork, size: 150),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SelectableText(
                        'Title: ${fields['title'] ?? track['title'] ?? '—'}\n'
                        'Artists: ${fields['artists'] is List ? (fields['artists'] as List).join(', ') : _artists(track)}\n'
                        'Album: ${fields['album'] ?? track['album'] ?? '—'}\n'
                        'Album Artist: $albumArtists\n'
                        'Track: ${fields['trackNumber'] ?? track['trackNumber'] ?? '—'} / ${fields['totalTracks'] ?? '—'}\n'
                        'Disc: ${fields['discNumber'] ?? track['discNumber'] ?? '—'} / ${fields['totalDiscs'] ?? '—'}\n'
                        'Date: ${fields['releaseDate'] ?? fields['year'] ?? track['year'] ?? '—'}\n'
                        'Genre: $genres\n'
                        'ISRC: ${fields['isrc'] ?? '—'}\n'
                        'Publisher: ${fields['publisher'] ?? '—'}\n'
                        'Copyright: ${fields['copyright'] ?? '—'}\n'
                        'Duration: ${_duration(track['durationSeconds'])}\n'
                        'Format: ${track['codec'] ?? track['extension'] ?? '—'}\n'
                        'Bitrate: ${track['bitrate'] ?? '—'}\n'
                        'Sample rate: ${track['sampleRate'] ?? '—'}\n\n'
                        '${identity['status'] == 'exact' ? 'Yandex identity: Exact\nTrack ID: ${identity['externalId']}' : 'Yandex identity: —'}',
                      ),
                      if (path.isNotEmpty)
                        ExpansionTile(
                          key: Key('local-detail-path-${track['id']}'),
                          tilePadding: EdgeInsets.zero,
                          childrenPadding: const EdgeInsets.only(bottom: 8),
                          title: Text(l10n.localShowPath),
                          children: [
                            Align(
                              alignment: Alignment.centerLeft,
                              child: SelectableText(path),
                            ),
                          ],
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        actions: [
          if (widget.metadataBridge != null)
            TextButton.icon(
              key: Key('local-detail-edit-${track['id']}'),
              onPressed: () {
                Navigator.pop(context);
                _edit(track);
              },
              icon: const Icon(Icons.edit_outlined),
              label: Text(l10n.localEditMetadata),
            ),
          if (path.isNotEmpty)
            TextButton.icon(
              key: Key('local-detail-play-${track['id']}'),
              onPressed: () => _play(track),
              icon: const Icon(Icons.play_arrow),
              label: Text(l10n.play),
            ),
          if (path.isNotEmpty)
            TextButton.icon(
              key: Key('local-detail-reveal-${track['id']}'),
              onPressed: () => _reveal(track),
              icon: const Icon(Icons.folder_open_outlined),
              label: Text(l10n.localRevealFile),
            ),
          FilledButton(
            onPressed: () => Navigator.pop(context),
            child: Text(l10n.close),
          ),
        ],
      ),
    );
  }

  Future<void> _showFolderFilter() async {
    if (_roots.isEmpty || _busy) return;
    final l10n = context.l10n;
    final allIds = _rootIds(_roots);
    final initial = Set<int>.from(_selectedRootIds);
    final selected = await showDialog<Set<int>>(
      context: context,
      builder: (dialogContext) {
        var draft = Set<int>.from(initial);
        return StatefulBuilder(
          builder: (context, setDialogState) {
            final allChecked =
                draft.length == allIds.length && draft.containsAll(allIds);
            final allValue = allChecked
                ? true
                : draft.isEmpty
                ? false
                : null;
            return AlertDialog(
              title: Text(l10n.localFolderFilterTitle),
              content: SizedBox(
                width: 620,
                height: (_roots.length * 58 + 68).clamp(180, 440).toDouble(),
                child: Column(
                  children: [
                    CheckboxListTile(
                      key: const Key('local-filter-all'),
                      tristate: true,
                      value: allValue,
                      dense: true,
                      controlAffinity: ListTileControlAffinity.leading,
                      title: Text(l10n.localFoldersAll),
                      onChanged: (_) {
                        setDialogState(() {
                          draft = allChecked ? <int>{} : Set<int>.from(allIds);
                        });
                      },
                    ),
                    const Divider(height: 1),
                    Expanded(
                      child: ListView.builder(
                        itemCount: _roots.length,
                        itemBuilder: (context, index) {
                          final root = _roots[index];
                          final id = int.tryParse('${root['id']}');
                          if (id == null) return const SizedBox.shrink();
                          final path = '${root['path']}';
                          return Tooltip(
                            message: path,
                            waitDuration: const Duration(milliseconds: 350),
                            child: CheckboxListTile(
                              key: Key('local-filter-root-$id'),
                              value: draft.contains(id),
                              dense: true,
                              controlAffinity: ListTileControlAffinity.leading,
                              title: Text(
                                path,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              onChanged: (checked) {
                                setDialogState(() {
                                  if (checked == true) {
                                    draft.add(id);
                                  } else {
                                    draft.remove(id);
                                  }
                                });
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
                  onPressed: () => Navigator.pop(dialogContext),
                  child: Text(l10n.cancel),
                ),
                FilledButton(
                  key: const Key('local-filter-apply'),
                  onPressed: () => Navigator.pop(dialogContext, draft),
                  child: Text(l10n.localApply),
                ),
              ],
            );
          },
        );
      },
    );
    if (selected == null || !mounted) return;
    setState(() {
      _selectedRootIds = selected;
      _selectionInitialized = true;
    });
    await _reload();
  }

  String _folderFilterLabel() {
    final l10n = context.l10n;
    if (_roots.isEmpty) return l10n.localFoldersAll;
    if (_selectedRootIds.isEmpty) return l10n.localFoldersNone;
    if (_allSelected()) return l10n.localFoldersAll;
    if (_selectedRootIds.length == 1) {
      final id = _selectedRootIds.first;
      for (final root in _roots) {
        if ('${root['id']}' == '$id') return _rootName(root);
      }
    }
    return l10n.localFoldersSelected(
      _selectedRootIds.length,
      _roots.length,
    );
  }

  String _singleSelectedRootPath() {
    if (_selectedRootIds.length != 1) return '';
    final id = _selectedRootIds.first;
    for (final root in _roots) {
      if ('${root['id']}' == '$id') return '${root['path'] ?? ''}';
    }
    return '';
  }

  String _summaryText() {
    final l10n = context.l10n;
    if (_roots.isEmpty) return l10n.localSummaryAll(_total, 0);
    if (_allSelected()) return l10n.localSummaryAll(_total, _roots.length);
    return l10n.localSummarySelected(
      _total,
      _selectedRootIds.length,
      _roots.length,
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      key: const Key('local-library-page'),
      body: Column(
        children: [
          if (_busy) const LinearProgressIndicator(key: Key('local-progress')),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppUiTokens.pagePadding,
                20,
                AppUiTokens.pagePadding,
                0,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _buildHeader(l10n),
                  const SizedBox(height: AppUiTokens.sectionGap),
                  _buildToolbar(l10n),
                  if (_selectedTrackIds.isNotEmpty) ...[
                    const SizedBox(height: AppUiTokens.compactGap),
                    _buildBulkToolbar(),
                  ],
                  if (_status != null || _error != null) ...[
                    const SizedBox(height: AppUiTokens.compactGap),
                    _buildMessageLine(),
                  ],
                  if (_roots.isNotEmpty) ...[
                    const SizedBox(height: AppUiTokens.compactGap),
                    _buildRootManagement(l10n),
                  ],
                  const SizedBox(height: AppUiTokens.sectionGap),
                  Expanded(child: _buildTrackArea(l10n)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(dynamic l10n) {
    final title = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          l10n.localLibraryTitle,
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 4),
        Text(
          _summaryText(),
          key: const Key('local-summary'),
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
    final actions = Wrap(
      spacing: AppUiTokens.compactGap,
      runSpacing: AppUiTokens.compactGap,
      children: [
        FilledButton.icon(
          key: const Key('local-add-folder'),
          onPressed: _busy ? null : _addFolder,
          icon: const Icon(Icons.create_new_folder_outlined),
          label: Text(l10n.localAddFolder),
        ),
        FilledButton.tonalIcon(
          key: const Key('local-scan-all'),
          onPressed: _busy || _roots.isEmpty ? null : () => _scan(),
          icon: const Icon(Icons.sync),
          label: Text(l10n.localScanAll),
        ),
      ],
    );
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 760) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              title,
              const SizedBox(height: 12),
              Align(alignment: Alignment.centerLeft, child: actions),
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(child: title),
            const SizedBox(width: AppUiTokens.compactGap),
            actions,
          ],
        );
      },
    );
  }

  Widget _buildToolbar(dynamic l10n) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final searchWidth = constraints.maxWidth >= 900
                ? (constraints.maxWidth - 450).clamp(320, 620).toDouble()
                : constraints.maxWidth;
            return Wrap(
              spacing: 12,
              runSpacing: 10,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                SizedBox(
                  width: searchWidth,
                  height: AppUiTokens.controlHeight,
                  child: TextField(
                    key: const Key('local-search'),
                    controller: _search,
                    onSubmitted: (_) => _reload(),
                    decoration: InputDecoration(
                      prefixIcon: const Icon(Icons.search),
                      hintText: l10n.localSearchHint,
                      border: const OutlineInputBorder(),
                      suffixIcon: IconButton(
                        tooltip: l10n.localClearSearch,
                        onPressed: () {
                          if (_search.text.isEmpty) return;
                          _search.clear();
                          _reload();
                        },
                        icon: const Icon(Icons.clear),
                      ),
                    ),
                  ),
                ),
                Tooltip(
                  message: _selectedRootIds.length == 1
                      ? _singleSelectedRootPath()
                      : '',
                  child: OutlinedButton.icon(
                    key: const Key('local-folder-filter'),
                    onPressed: _busy || _roots.isEmpty
                        ? null
                        : _showFolderFilter,
                    icon: const Icon(Icons.folder_copy_outlined),
                    label: Text(_folderFilterLabel()),
                  ),
                ),
                SizedBox(
                  width: 190,
                  child: DropdownButtonFormField<String>(
                    key: const Key('local-sort'),
                    initialValue: _sort,
                    decoration: InputDecoration(
                      labelText: l10n.localSortLabel,
                      border: const OutlineInputBorder(),
                      isDense: true,
                    ),
                    items: [
                      DropdownMenuItem(
                        value: 'artist',
                        child: Text(l10n.localSortArtist),
                      ),
                      DropdownMenuItem(
                        value: 'title',
                        child: Text(l10n.localSortTitle),
                      ),
                      DropdownMenuItem(
                        value: 'album',
                        child: Text(l10n.localSortAlbum),
                      ),
                      DropdownMenuItem(
                        value: 'duration',
                        child: Text(l10n.localSortDuration),
                      ),
                      DropdownMenuItem(
                        value: 'path',
                        child: Text(l10n.localSortPath),
                      ),
                    ],
                    onChanged: _busy
                        ? null
                        : (value) {
                            if (value != null && value != _sort) {
                              setState(() => _sort = value);
                              _reload();
                            }
                          },
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildBulkToolbar() {
    final l10n = context.l10n;
    final visibleIds = _tracks
        .map((track) => int.tryParse('${track['id']}'))
        .whereType<int>()
        .toSet();
    final allVisibleSelected =
        visibleIds.isNotEmpty && visibleIds.every(_selectedTrackIds.contains);
    return Card(
      key: const Key('local-bulk-toolbar'),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Wrap(
          spacing: 8,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              l10n.v0111Selected(_selectedTrackIds.length),
              key: const Key('local-selection-count'),
              style: Theme.of(context).textTheme.titleSmall,
            ),
            if (!allVisibleSelected)
              OutlinedButton(
                key: const Key('local-select-all-visible'),
                onPressed: _selectAllVisibleTracks,
                child: Text(l10n.v0111SelectAllVisible),
              ),
            FilledButton.icon(
              key: const Key('local-bulk-upload-yandex'),
              onPressed:
                  widget.yandexUploadBridge != null &&
                      widget.yandexBatchUploadBridge != null
                  ? _bulkUploadToYandex
                  : null,
              icon: const Icon(Icons.cloud_upload_outlined),
              label: Text(l10n.v0111UploadToYandex),
            ),
            TextButton(
              key: const Key('local-clear-selection'),
              onPressed: _clearTrackSelection,
              child: Text(l10n.v0111ClearSelection),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMessageLine() {
    final scheme = Theme.of(context).colorScheme;
    final message = _error ?? _status ?? '';
    final isError = _error != null || _statusIsError;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: isError ? scheme.errorContainer : scheme.surfaceContainerLow,
        borderRadius: AppUiTokens.smallRadius,
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: [
            Icon(
              isError ? Icons.error_outline : Icons.check_circle_outline,
              size: 18,
              color: isError ? scheme.onErrorContainer : scheme.primary,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                message,
                key: Key(isError ? 'local-error' : 'local-status'),
                maxLines: isError ? 3 : 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRootManagement(dynamic l10n) {
    return Card(
      margin: EdgeInsets.zero,
      child: ExpansionTile(
        key: const Key('local-roots'),
        initiallyExpanded: true,
        leading: const Icon(Icons.folder_copy_outlined),
        title: Text(l10n.localLibraryFoldersTitle),
        subtitle: Text(l10n.localLibraryFoldersHint),
        children: [
          const Divider(height: 1),
          ..._roots.map((root) {
            final id = int.tryParse('${root['id']}');
            final path = '${root['path']}';
            return ListTile(
              dense: true,
              leading: const Icon(Icons.folder_outlined),
              title: Tooltip(
                message: path,
                child: Text(
                  path,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              subtitle: Text(l10n.localLastScanned(_lastScanned(root))),
              trailing: Wrap(
                spacing: 2,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  IconButton(
                    key: Key('local-scan-root-${root['id']}'),
                    tooltip: l10n.localScanFolderTooltip,
                    onPressed: _busy || id == null
                        ? null
                        : () => _scan(rootId: id),
                    icon: const Icon(Icons.sync),
                  ),
                  PopupMenuButton<_RootMenuAction>(
                    key: Key('local-root-menu-${root['id']}'),
                    tooltip: l10n.localMoreActions,
                    onSelected: (action) {
                      if (action == _RootMenuAction.remove) {
                        _removeFolder(root);
                      }
                    },
                    itemBuilder: (context) => [
                      PopupMenuItem(
                        key: Key('local-remove-root-${root['id']}'),
                        value: _RootMenuAction.remove,
                        child: ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(Icons.remove_circle_outline),
                          title: Text(l10n.localRemoveFolder),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildTrackArea(dynamic l10n) {
    if (_roots.isEmpty && !_busy) {
      return _EmptyLocalState(
        key: const Key('local-empty'),
        icon: Icons.library_music_outlined,
        title: l10n.localEmptyNoRootsTitle,
        body: l10n.localEmptyNoRootsBody,
        action: FilledButton.icon(
          onPressed: _addFolder,
          icon: const Icon(Icons.create_new_folder_outlined),
          label: Text(l10n.localAddFolder),
        ),
      );
    }
    if (_roots.isNotEmpty && _selectedRootIds.isEmpty && !_busy) {
      return _EmptyLocalState(
        key: const Key('local-no-folders-selected'),
        icon: Icons.folder_off_outlined,
        title: l10n.localEmptyNoSelectionTitle,
        body: l10n.localEmptyNoSelectionBody,
      );
    }
    if (_tracks.isEmpty && !_busy) {
      final hasSearch = _search.text.trim().isNotEmpty;
      return _EmptyLocalState(
        key: Key(hasSearch ? 'local-no-results' : 'local-no-tracks'),
        icon: hasSearch ? Icons.search_off : Icons.music_off_outlined,
        title: hasSearch
            ? l10n.localEmptySearchTitle
            : l10n.localEmptyTracksTitle,
        body: hasSearch
            ? l10n.localEmptySearchBody
            : l10n.localEmptyTracksBody,
      );
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= _wideTrackTable;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Text(
                  l10n.localTracksTitle,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(width: 8),
                Text(
                  '$_total',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Expanded(
              child: Card(
                margin: EdgeInsets.zero,
                clipBehavior: Clip.antiAlias,
                child: Column(
                  children: [
                    if (wide) _buildTableHeader(l10n),
                    Expanded(
                      child: ListView.builder(
                        key: const Key('local-track-list'),
                        itemCount:
                            _tracks.length + (_tracks.length < _total ? 1 : 0),
                        itemBuilder: (context, index) {
                          if (index >= _tracks.length) {
                            return Center(
                              child: Padding(
                                padding: const EdgeInsets.all(16),
                                child: OutlinedButton(
                                  key: const Key('local-load-more'),
                                  onPressed: _busy ? null : _loadMore,
                                  child: Text(l10n.localLoadMore),
                                ),
                              ),
                            );
                          }
                          final track = _tracks[index];
                          return wide
                              ? _buildWideTrackRow(track, l10n)
                              : _buildCompactTrackRow(track, l10n);
                        },
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildTableHeader(dynamic l10n) {
    final style = Theme.of(context).textTheme.labelSmall?.copyWith(
      color: Theme.of(context).colorScheme.onSurfaceVariant,
      fontWeight: FontWeight.w700,
      letterSpacing: .6,
    );
    return Container(
      height: 38,
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Row(
        children: [
          const SizedBox(width: 48),
          Expanded(flex: 5, child: Text(l10n.localColumnTrack, style: style)),
          Expanded(flex: 3, child: Text(l10n.localColumnAlbum, style: style)),
          SizedBox(width: 64, child: Text(l10n.localColumnYear, style: style)),
          SizedBox(width: 74, child: Text(l10n.localColumnFormat, style: style)),
          SizedBox(
            width: 132,
            child: Text(l10n.localColumnVersion, style: style),
          ),
          SizedBox(
            width: 64,
            child: Text(l10n.localColumnDuration, style: style),
          ),
          const SizedBox(width: 176),
        ],
      ),
    );
  }

  Widget _buildWideTrackRow(Map<String, dynamic> track, dynamic l10n) {
    final artwork = Map<String, dynamic>.from(
      track['artwork'] as Map? ?? const {},
    );
    final album = '${track['album'] ?? '—'}';
    final codec = '${track['codec'] ?? track['extension'] ?? '—'}'.toUpperCase();
    return Material(
      key: Key('local-track-${track['id']}'),
      color: Colors.transparent,
      child: InkWell(
        onTap: () => _showDetails(track),
        child: SizedBox(
          height: AppUiTokens.trackRowHeight + 4,
          child: Row(
            children: [
              const SizedBox(width: 6),
              SizedBox(
                width: 42,
                child: Checkbox(
                  key: Key('local-select-${track['id']}'),
                  value: _selectedTrackIds.contains(
                    int.tryParse('${track['id']}'),
                  ),
                  onChanged: (value) =>
                      _toggleTrackSelection(track, value == true),
                ),
              ),
              Expanded(
                flex: 5,
                child: Row(
                  children: [
                    _LocalArtwork(
                      artwork: artwork,
                      size: AppUiTokens.artworkSize,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            (track['title'] ??
                                    track['fileName'] ??
                                    l10n.localUnknownTrack)
                                .toString(),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            _artists(track),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(
                flex: 3,
                child: Text(album, maxLines: 1, overflow: TextOverflow.ellipsis),
              ),
              SizedBox(width: 64, child: Text('${track['year'] ?? '—'}')),
              SizedBox(width: 74, child: Text(codec)),
              SizedBox(width: 132, child: _buildContentLabel(track, l10n)),
              SizedBox(
                width: 64,
                child: Text(_duration(track['durationSeconds'])),
              ),
              SizedBox(width: 176, child: _buildTrackActions(track, l10n)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCompactTrackRow(Map<String, dynamic> track, dynamic l10n) {
    final artwork = Map<String, dynamic>.from(
      track['artwork'] as Map? ?? const {},
    );
    final album = '${track['album'] ?? '—'}';
    final codec = '${track['codec'] ?? track['extension'] ?? '—'}'.toUpperCase();
    return Material(
      key: Key('local-track-${track['id']}'),
      color: Colors.transparent,
      child: InkWell(
        onTap: () => _showDetails(track),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Checkbox(
                key: Key('local-select-${track['id']}'),
                value: _selectedTrackIds.contains(int.tryParse('${track['id']}')),
                onChanged: (value) => _toggleTrackSelection(track, value == true),
              ),
              const SizedBox(width: 4),
              _LocalArtwork(
                artwork: artwork,
                size: AppUiTokens.artworkSize,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      (track['title'] ??
                              track['fileName'] ??
                              l10n.localUnknownTrack)
                          .toString(),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      _artists(track),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '$album · ${track['year'] ?? '—'} · $codec · ${_duration(track['durationSeconds'])}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              _buildContentLabel(track, l10n),
              const SizedBox(width: 4),
              _buildTrackActions(track, l10n),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildContentLabel(Map<String, dynamic> track, dynamic l10n) {
    final value = '${track['contentLabel'] ?? ''}';
    final text = value == 'censored'
        ? l10n.censored
        : value == 'original'
        ? l10n.original
        : '—';
    if (widget.contentLabelBridge == null) {
      return Align(alignment: Alignment.centerLeft, child: Text(text));
    }
    return Align(
      alignment: Alignment.centerLeft,
      child: PopupMenuButton<String>(
        key: Key('local-content-label-menu-${track['id']}'),
        tooltip: l10n.localMarkVersion,
        onSelected: (selected) => _setContentLabel(track, selected),
        itemBuilder: (context) => [
          PopupMenuItem(value: 'original', child: Text(l10n.original)),
          PopupMenuItem(value: 'censored', child: Text(l10n.censored)),
          const PopupMenuDivider(),
          PopupMenuItem(value: '', child: Text(l10n.localClearLabel)),
        ],
        child: Chip(
          key: Key('local-content-label-${track['id']}'),
          visualDensity: VisualDensity.compact,
          label: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(text),
              const SizedBox(width: 2),
              const Icon(Icons.arrow_drop_down, size: 16),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTrackActions(Map<String, dynamic> track, dynamic l10n) {
    final path = (track['path'] ?? '').toString();
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        if (path.isNotEmpty)
          IconButton(
            key: Key('local-play-${track['id']}'),
            tooltip: l10n.play,
            onPressed: () => _play(track),
            icon: const Icon(Icons.play_arrow),
          ),
        if (widget.metadataBridge != null)
          IconButton(
            key: Key('local-edit-${track['id']}'),
            tooltip: l10n.localEditMetadata,
            onPressed: () => _edit(track),
            icon: const Icon(Icons.edit_outlined),
          ),
        if (widget.yandexUploadBridge != null)
          IconButton(
            key: Key('local-upload-yandex-${track['id']}'),
            tooltip: context.l10n.v0111UploadToYandex,
            onPressed: () => _uploadToYandex(track),
            icon: const Icon(Icons.cloud_upload_outlined),
          ),
        PopupMenuButton<_TrackMenuAction>(
          key: Key('local-track-menu-${track['id']}'),
          tooltip: l10n.localMoreActions,
          onSelected: (action) {
            switch (action) {
              case _TrackMenuAction.details:
                _showDetails(track);
                break;
              case _TrackMenuAction.reveal:
                _reveal(track);
                break;
            }
          },
          itemBuilder: (context) => [
            PopupMenuItem(
              value: _TrackMenuAction.details,
              child: ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.info_outline),
                title: Text(l10n.localDetails),
              ),
            ),
            if (path.isNotEmpty)
              PopupMenuItem(
                key: Key('local-reveal-${track['id']}'),
                value: _TrackMenuAction.reveal,
                child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.folder_open_outlined),
                  title: Text(l10n.localRevealFile),
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _EmptyLocalState extends StatelessWidget {
  const _EmptyLocalState({
    super.key,
    required this.icon,
    required this.title,
    required this.body,
    this.action,
  });

  final IconData icon;
  final String title;
  final String body;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 52,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 14),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(
              body,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            if (action != null) ...[
              const SizedBox(height: 16),
              action!,
            ],
          ],
        ),
      ),
    );
  }
}

class _LocalArtwork extends StatelessWidget {
  const _LocalArtwork({required this.artwork, required this.size});

  final Map<String, dynamic> artwork;
  final double size;

  @override
  Widget build(BuildContext context) {
    final path = '${artwork['cachePath'] ?? ''}';
    final file = path.isEmpty ? null : File(path);
    return ClipRRect(
      borderRadius: AppUiTokens.smallRadius,
      child: SizedBox(
        width: size,
        height: size,
        child: file != null && file.existsSync()
            ? Image.file(
                file,
                fit: BoxFit.cover,
                cacheWidth: size.round(),
                cacheHeight: size.round(),
              )
            : ColoredBox(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                child: Icon(Icons.album_outlined, size: size * .6),
              ),
      ),
    );
  }
}
