import 'dart:async';

import 'package:flutter/material.dart';

import 'coverage_bridge.dart';
import 'matching_bridge.dart';

part 'coverage_page_view.dart';
part 'coverage_widgets.dart';

class CoveragePage extends StatefulWidget {
  const CoveragePage({
    super.key,
    required this.bridge,
    required this.matchingBridge,
    this.onOpenMatching,
  });

  final CoverageBridgeClient bridge;
  final MatchingBridgeClient matchingBridge;
  final VoidCallback? onOpenMatching;

  @override
  State<CoveragePage> createState() => _CoveragePageState();
}

class _CoveragePageState extends State<CoveragePage> {
  static const _pageSize = 100;

  final _searchController = TextEditingController();
  Timer? _searchTimer;
  Map<String, dynamic>? _summary;
  List<Map<String, dynamic>> _collections = [];
  List<Map<String, dynamic>> _items = [];
  final Set<String> _selected = {};

  String _status = 'missing';
  String _collectionId = '';
  String _sort = 'artist';
  String _userAction = '';
  String _variantStatus = '';
  int _offset = 0;
  int _total = 0;
  bool _loading = true;
  bool _matching = false;
  String? _error;

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
        _selected.removeWhere(
          (id) => !_items.any((item) => item['externalId'] == id),
        );
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

  Future<void> _reloadTracks({bool refreshSummary = true}) async {
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
      final tracks = Map<String, dynamic>.from(results.last);
      setState(() {
        if (refreshSummary) _summary = Map<String, dynamic>.from(results.first);
        _items = _maps(tracks['items']);
        _total = _asInt(tracks['count']);
        _selected.clear();
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
      setState(() => _offset = 0);
      _reloadTracks(refreshSummary: false);
    });
  }

  Future<void> _setAction(String externalId, String action) async {
    try {
      await widget.bridge.coverageSetAction(externalId, action);
      await _reloadTracks();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _setBulkAction(String action) async {
    if (_selected.isEmpty) return;
    final ids = _selected.toList(growable: false);
    try {
      await widget.bridge.coverageSetActions(ids, action);
      await _reloadTracks();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
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
