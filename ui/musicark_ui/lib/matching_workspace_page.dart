import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'app_localizations_ext.dart';
import 'app_ui_tokens.dart';
import 'content_label_bridge.dart';
import 'l10n/app_localizations.dart';
import 'matching_bridge.dart';
import 'matching_detail_dialog.dart';
import 'variant_acceptance_bridge.dart';

part 'matching_workspace_widgets.dart';
part 'matching_workspace_support.dart';

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
  final TextEditingController _searchController = TextEditingController();
  Map<String, dynamic> _summary = const {};
  Map<String, dynamic> _variantCapabilities = const {};
  List<Map<String, dynamic>> _items = const [];
  Map<String, dynamic>? _matchingRunResult;
  Map<String, dynamic>? _variantRunResult;
  int _total = 0;
  bool _loading = true;
  bool _running = false;
  bool _runningVariants = false;
  bool _loadingMore = false;
  String _status = '';
  String _search = '';
  String _sort = 'confidence';
  String? _error;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
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
      _matchingRunResult = null;
      _error = null;
    });
    try {
      final result = await widget.bridge.matchingRun();
      if (!mounted) return;
      setState(() => _matchingRunResult = Map<String, dynamic>.from(result));
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
      _variantRunResult = null;
      _error = null;
    });
    try {
      final result = await widget.bridge.variantRunAllAvailable();
      if (!mounted) return;
      setState(() => _variantRunResult = Map<String, dynamic>.from(result));
      await _reload();
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _runningVariants = false);
    }
  }

  Future<void> _loadMore() async {
    if (_loadingMore || _items.length >= _total) return;
    setState(() {
      _loadingMore = true;
      _error = null;
    });
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

  Future<void> _submitSearch(String value) async {
    final normalized = value.trim();
    if (_search == normalized) return;
    setState(() => _search = normalized);
    await _reload();
  }

  Future<void> _clearSearch() async {
    if (_searchController.text.isEmpty && _search.isEmpty) return;
    _searchController.clear();
    setState(() => _search = '');
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
        builder: (dialogContext) => MatchingDetailDialog(
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
    final l10n = context.l10n;
    final unavailableMessage =
        '${_variantCapabilities['unavailableMessage'] ?? ''}'.trim();
    return Scaffold(
      key: const Key('matching-page'),
      body: Column(
        children: [
          if (_loading)
            const LinearProgressIndicator(key: Key('matching-progress')),
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
                  _MatchingSummary(
                    summary: _summary,
                    l10n: l10n,
                  ),
                  const SizedBox(height: AppUiTokens.sectionGap),
                  _buildActions(l10n),
                  if (_matchingRunResult != null) ...[
                    const SizedBox(height: AppUiTokens.compactGap),
                    _InfoBanner(
                      key: const Key('matching-run-result'),
                      icon: Icons.compare_arrows,
                      text: l10n.matchingRunResult(
                        _asInt(_matchingRunResult!['total']),
                        _asInt(_matchingRunResult!['matched']),
                        _asInt(_matchingRunResult!['conflicts']),
                        _asInt(_matchingRunResult!['unmatched']),
                      ),
                    ),
                  ],
                  if (_variantRunResult != null) ...[
                    const SizedBox(height: AppUiTokens.compactGap),
                    _InfoBanner(
                      key: const Key('variant-run-result'),
                      icon: Icons.graphic_eq,
                      text: l10n.matchingVariantRunResult(
                        _asInt(_variantRunResult!['processed']),
                        _asInt(_variantRunResult!['same']),
                        _asInt(_variantRunResult!['altered']),
                        _asInt(_variantRunResult!['differentVersion']),
                        _asInt(_variantRunResult!['uncertain']),
                      ),
                    ),
                  ],
                  if (unavailableMessage.isNotEmpty) ...[
                    const SizedBox(height: AppUiTokens.compactGap),
                    _InfoBanner(
                      key: const Key('variant-unavailable'),
                      icon: Icons.info_outline,
                      text: unavailableMessage,
                      tonal: true,
                    ),
                  ],
                  if (_error != null) ...[
                    const SizedBox(height: AppUiTokens.compactGap),
                    _ErrorBanner(
                      key: const Key('matching-error'),
                      text: _error!,
                    ),
                  ],
                  const SizedBox(height: AppUiTokens.sectionGap),
                  _buildFilters(l10n),
                  const SizedBox(height: AppUiTokens.compactGap),
                  _buildSearchAndSort(l10n),
                  const SizedBox(height: AppUiTokens.sectionGap),
                  Expanded(child: _buildResults(l10n)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(AppLocalizations l10n) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l10n.navMatching,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 4),
          Text(
            l10n.matchingSubtitle,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ],
      );

  Widget _buildActions(AppLocalizations l10n) => Wrap(
        spacing: AppUiTokens.compactGap,
        runSpacing: AppUiTokens.compactGap,
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
            label: SizedBox(
              width: 176,
              child: Text(
                _running ? l10n.matchingRunning : l10n.matchingRun,
                textAlign: TextAlign.center,
              ),
            ),
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
            label: SizedBox(
              width: 152,
              child: Text(
                _runningVariants
                    ? l10n.matchingCheckingVariants
                    : l10n.matchingCheckVariants,
                textAlign: TextAlign.center,
              ),
            ),
          ),
          Tooltip(
            message: l10n.refresh,
            child: IconButton(
              key: const Key('matching-refresh'),
              style: IconButton.styleFrom(
                side: BorderSide(
                  color: Theme.of(context).colorScheme.outlineVariant,
                ),
              ),
              onPressed: _loading ? null : _reload,
              icon: const Icon(Icons.refresh),
            ),
          ),
        ],
      );

  Widget _buildFilters(AppLocalizations l10n) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l10n.matchingFilterLabel,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: AppUiTokens.compactGap,
            runSpacing: AppUiTokens.compactGap,
            children: [
              _FilterChip(
                key: const Key('matching-filter-all'),
                label: l10n.matchingFilterAll(
                  _asInt(_summary['yandexTracks']),
                ),
                selected: _status.isEmpty,
                onSelected: () => _setStatus(''),
              ),
              _FilterChip(
                key: const Key('matching-filter-matched'),
                label: l10n.matchingFilterMatched(_asInt(_summary['matched'])),
                selected: _status == 'matched',
                onSelected: () => _setStatus('matched'),
              ),
              _FilterChip(
                key: const Key('matching-filter-conflict'),
                label: l10n.matchingFilterConflict(
                  _asInt(_summary['conflicts']),
                ),
                selected: _status == 'conflict',
                onSelected: () => _setStatus('conflict'),
              ),
              _FilterChip(
                key: const Key('matching-filter-unmatched'),
                label: l10n.matchingFilterUnmatched(
                  _asInt(_summary['unmatched']),
                ),
                selected: _status == 'unmatched',
                onSelected: () => _setStatus('unmatched'),
              ),
            ],
          ),
        ],
      );

  Widget _buildSearchAndSort(AppLocalizations l10n) => LayoutBuilder(
        builder: (context, constraints) {
          final search = TextField(
            key: const Key('matching-search'),
            controller: _searchController,
            decoration: InputDecoration(
              hintText: l10n.matchingSearchHint,
              prefixIcon: const Icon(Icons.search),
              suffixIcon: _searchController.text.isEmpty
                  ? null
                  : Tooltip(
                      message: l10n.localClearSearch,
                      child: IconButton(
                        key: const Key('matching-search-clear'),
                        onPressed: _clearSearch,
                        icon: const Icon(Icons.close),
                      ),
                    ),
            ),
            textInputAction: TextInputAction.search,
            onChanged: (_) => setState(() {}),
            onSubmitted: _submitSearch,
          );
          final sort = InputDecorator(
            decoration: InputDecoration(labelText: l10n.localSortLabel),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                key: const Key('matching-sort'),
                value: _sort,
                isExpanded: true,
                items: [
                  DropdownMenuItem(
                    value: 'confidence',
                    child: Text(l10n.matchingSortConfidence),
                  ),
                  DropdownMenuItem(
                    value: 'artist',
                    child: Text(l10n.localSortArtist),
                  ),
                  DropdownMenuItem(
                    value: 'title',
                    child: Text(l10n.localSortTitle),
                  ),
                  DropdownMenuItem(
                    value: 'status',
                    child: Text(l10n.matchingSortStatus),
                  ),
                ],
                onChanged: (value) {
                  if (value == null || value == _sort) return;
                  setState(() => _sort = value);
                  _reload();
                },
              ),
            ),
          );
          if (constraints.maxWidth >= 720) {
            return Row(
              children: [
                Expanded(child: search),
                const SizedBox(width: 12),
                SizedBox(width: 260, child: sort),
              ],
            );
          }
          return Column(
            children: [
              search,
              const SizedBox(height: AppUiTokens.compactGap),
              sort,
            ],
          );
        },
      );

  Widget _buildResults(AppLocalizations l10n) {
    if (_items.isEmpty) {
      if (_loading) return const Center(child: CircularProgressIndicator());
      return _EmptyMatchingState(
        key: const Key('matching-empty'),
        title: l10n.matchingEmptyTitle,
        body: l10n.matchingEmptyBody,
      );
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        final tableWidth = math.max(
          constraints.maxWidth,
          AppUiTokens.matchingTableMinimum,
        );
        return SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SizedBox(
            width: tableWidth,
            height: constraints.maxHeight,
            child: DecoratedBox(
              decoration: BoxDecoration(
                border: Border.all(
                  color: Theme.of(context).colorScheme.outlineVariant,
                ),
                borderRadius: AppUiTokens.mediumRadius,
              ),
              child: ClipRRect(
                borderRadius: AppUiTokens.mediumRadius,
                child: Column(
                  children: [
                    _MatchingTableHeader(l10n: l10n),
                    const Divider(height: 1),
                    Expanded(
                      child: ListView.separated(
                        key: const Key('matching-results'),
                        itemCount: _items.length,
                        separatorBuilder: (_, __) => const Divider(height: 1),
                        itemBuilder: (context, index) {
                          final row = _items[index];
                          return _MatchingResultRow(
                            row: row,
                            l10n: l10n,
                            onTap: () => _showDetail(row),
                          );
                        },
                      ),
                    ),
                    const Divider(height: 1),
                    _MatchingTableFooter(
                      shown: _items.length,
                      total: _total,
                      loadingMore: _loadingMore,
                      hasMore: _items.length < _total,
                      l10n: l10n,
                      onLoadMore: _loadMore,
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
