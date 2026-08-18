import 'dart:async';

import 'package:flutter/material.dart';

import 'app_localizations_ext.dart';
import 'coverage_bridge.dart';
import 'download_bridge.dart';
import 'matching_bridge.dart';

part 'coverage_page_view.dart';
part 'coverage_widgets.dart';
part 'coverage_track_widgets.dart';
part 'coverage_support_widgets.dart';

class CoveragePage extends StatefulWidget {
  const CoveragePage({
    super.key,
    required this.bridge,
    required this.matchingBridge,
    this.downloadBridge,
    this.onOpenMatching,
    this.onOpenDownloads,
  });

  final CoverageBridgeClient bridge;
  final MatchingBridgeClient matchingBridge;
  final DownloadBridgeClient? downloadBridge;
  final VoidCallback? onOpenMatching;
  final VoidCallback? onOpenDownloads;

  @override
  State<CoveragePage> createState() => _CoveragePageState();
}

class _CoveragePageState extends State<CoveragePage> {
  static const _pageSize = 100;
  static const _bulkPageSize = 500;

  final _searchController = TextEditingController();
  Timer? _searchTimer;
  Map<String, dynamic>? _summary;
  List<Map<String, dynamic>> _collections = [];
  List<Map<String, dynamic>> _items = [];
  final Set<String> _selected = {};
  final Set<String> _downloading = {};

  String _status = 'missing';
  String _collectionId = '';
  String _sort = 'artist';
  String _userAction = '';
  String _variantStatus = '';
  int _offset = 0;
  int _total = 0;
  bool _loading = true;
  bool _matching = false;
  bool _analysisExpanded = false;
  String? _error;

  int get _pageLimit => _pageSize;

  void _updateView(VoidCallback update) {
    if (!mounted) return;
    setState(update);
  }

  @override
  void initState() {
    super.initState();
    _load(initial: true);
  }

  @override
  void dispose() {
    _searchTimer?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _load({bool initial = false}) async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final results = await Future.wait([
        widget.bridge.coverageSummary(collectionId: _collectionId),
        if (initial) widget.bridge.coverageCollections(),
        widget.bridge.coverageTracks(
          limit: _pageSize,
          offset: _offset,
          status: _status,
          collectionId: _collectionId,
          search: _searchController.text.trim(),
          sort: _sort,
          userAction: _userAction,
          variantStatus: _variantStatus,
        ),
      ]);
      if (!mounted) return;
      final summary = Map<String, dynamic>.from(results[0]);
      final tracks = Map<String, dynamic>.from(results.last);
      setState(() {
        _summary = summary;
        if (initial) {
          _collections = _maps(results[1]['items']);
        }
        _items = _maps(tracks['items']);
        _total = _asInt(tracks['count']);
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error.toString();
      });
    }
  }

  Future<void> _reloadTracks({
    bool refreshSummary = true,
    bool clearSelection = false,
  }) async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final futures = <Future<Map<String, dynamic>>>[
        if (refreshSummary)
          widget.bridge.coverageSummary(collectionId: _collectionId),
        widget.bridge.coverageTracks(
          limit: _pageSize,
          offset: _offset,
          status: _status,
          collectionId: _collectionId,
          search: _searchController.text.trim(),
          sort: _sort,
          userAction: _userAction,
          variantStatus: _variantStatus,
        ),
      ];
      final results = await Future.wait(futures);
      if (!mounted) return;
      var tracks = Map<String, dynamic>.from(results.last);
      var items = _maps(tracks['items']);
      var total = _asInt(tracks['count']);

      if (items.isEmpty && total > 0 && _offset >= total) {
        final nextOffset = ((total - 1) ~/ _pageSize) * _pageSize;
        tracks = await widget.bridge.coverageTracks(
          limit: _pageSize,
          offset: nextOffset,
          status: _status,
          collectionId: _collectionId,
          search: _searchController.text.trim(),
          sort: _sort,
          userAction: _userAction,
          variantStatus: _variantStatus,
        );
        if (!mounted) return;
        items = _maps(tracks['items']);
        total = _asInt(tracks['count']);
        _offset = nextOffset;
      }

      setState(() {
        if (refreshSummary) {
          _summary = Map<String, dynamic>.from(results.first);
        }
        _items = items;
        _total = total;
        if (clearSelection) _selected.clear();
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error.toString();
      });
    }
  }

  void _setStatus(String status) {
    if (_status == status) return;
    setState(() {
      _status = status;
      _offset = 0;
      _selected.clear();
      if (status != 'covered') _variantStatus = '';
      if (status != 'missing') _userAction = '';
    });
    _reloadTracks(refreshSummary: false);
  }

  void _setCollection(String? value) {
    final next = value ?? '';
    setState(() {
      _collectionId = next;
      _offset = 0;
      _sort = next.startsWith('playlist:') ? 'position' : 'artist';
      _selected.clear();
    });
    _load();
  }

  void _queueSearch(String _) {
    _searchTimer?.cancel();
    _searchTimer = Timer(const Duration(milliseconds: 250), () {
      if (!mounted) return;
      setState(() {
        _offset = 0;
        _selected.clear();
      });
      _reloadTracks(refreshSummary: false);
    });
  }

  Future<void> _setAction(String externalId, String action) async {
    try {
      await widget.bridge.coverageSetAction(externalId, action);
      await _reloadTracks(clearSelection: true);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _setBulkAction(String action) async {
    if (_selected.isEmpty) return;
    final ids = _selected.toList(growable: false);
    try {
      await widget.bridge.coverageSetActions(ids, action);
      await _reloadTracks(clearSelection: true);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _selectAllFiltered() async {
    if (_status != 'missing' || _loading || _total <= 0) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final ids = <String>{};
      var offset = 0;
      while (true) {
        final payload = await widget.bridge.coverageTracks(
          limit: _bulkPageSize,
          offset: offset,
          status: _status,
          collectionId: _collectionId,
          search: _searchController.text.trim(),
          sort: _sort,
          userAction: _userAction,
          variantStatus: _variantStatus,
        );
        final items = _maps(payload['items']);
        final total = _asInt(payload['count']);
        for (final item in items) {
          final id = (item['externalId'] ?? '').toString().trim();
          if (id.isNotEmpty && item['coverageStatus'] == 'missing') {
            ids.add(id);
          }
        }
        offset += items.length;
        if (items.isEmpty || offset >= total) break;
      }
      if (!mounted) return;
      setState(() {
        _selected
          ..clear()
          ..addAll(ids);
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error.toString();
      });
    }
  }

  void _clearSelection() {
    _updateView(_selected.clear);
  }

  Future<void> _enqueueDownload(String externalId) async {
    final bridge = widget.downloadBridge;
    if (bridge == null || _downloading.contains(externalId)) return;
    _updateView(() {
      _downloading.add(externalId);
      _error = null;
    });
    try {
      final queued = await bridge.enqueue(externalId);
      final rawTask = queued['task'];
      final task = rawTask is Map
          ? Map<String, dynamic>.from(rawTask)
          : const <String, dynamic>{};
      final taskId = (task['id'] ?? '').toString();
      var finalStatus = (task['status'] ?? '').toString();
      if (finalStatus == 'queued' && taskId.isNotEmpty) {
        try {
          final run = await bridge.runTask(taskId);
          final rawResultTask = run['task'];
          if (rawResultTask is Map) {
            final resultTask = Map<String, dynamic>.from(rawResultTask);
            finalStatus = (resultTask['status'] ?? finalStatus).toString();
          }
        } on DownloadBridgeException catch (error) {
          if (error.code != 'worker_busy') rethrow;
        }
      }
      await _reloadTracks(clearSelection: true);
      if (!mounted) return;
      final l10n = context.l10n;
      final message = finalStatus == 'completed'
          ? l10n.coverageDownloadCompleted
          : finalStatus == 'failed' || finalStatus == 'needs_review'
              ? l10n.coverageDownloadFailed
              : l10n.coverageDownloadQueued;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message)),
      );
    } on DownloadBridgeException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message);
      if (error.code == 'target_required' && widget.onOpenDownloads != null) {
        final l10n = context.l10n;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(l10n.coverageDownloadTargetRequired),
            action: SnackBarAction(
              label: l10n.coverageChooseFolder,
              onPressed: widget.onOpenDownloads!,
            ),
          ),
        );
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      _updateView(() => _downloading.remove(externalId));
    }
  }

  Future<void> _runMatching() async {
    if (_matching) return;
    setState(() {
      _matching = true;
      _error = null;
    });
    try {
      await widget.matchingBridge.matchingRun();
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _matching = false);
    }
  }

  Future<void> _openDetails(Map<String, dynamic> item) async {
    final externalId = (item['externalId'] ?? '').toString();
    if (externalId.isEmpty) return;
    try {
      final payload = await widget.bridge.coverageTrack(externalId);
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => _CoverageDetailsDialog(
          payload: payload,
          onOpenMatching: widget.onOpenMatching,
        ),
      );
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) => _buildView(context);
}
