import 'package:flutter/material.dart';

import 'app_localizations_ext.dart';
import 'app_strings.dart';
import 'content_label_bridge.dart';
import 'l10n/app_localizations.dart';
import 'matching_bridge.dart';
import 'variant_acceptance_bridge.dart';

part 'matching_detail_widgets.dart';
part 'matching_detail_support.dart';

class MatchingDetailDialog extends StatefulWidget {
  const MatchingDetailDialog({
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
  State<MatchingDetailDialog> createState() => _MatchingDetailDialogState();
}

class _MatchingDetailDialogState extends State<MatchingDetailDialog> {
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
          final decision = await widget.variantAcceptanceBridge.get(
            _externalId,
            localId,
          );
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
    final l10n = context.l10n;
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
      title: Text(
        '${_artistText(provider['artists'], l10n.yandexUnknownArtist)} — '
        '${provider['title'] ?? l10n.yandexUnknownTitle}',
      ),
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
                    'Статус сопоставления: ${_matchingStatusLabel(l10n, identityStatus)}',
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
                                  onPressed:
                                      _busy ? null : _toggleVariantAcceptance,
                                  child: const Text('Отменить принятие'),
                                )
                              : FilledButton(
                                  key: const Key('variant-accept-current'),
                                  onPressed:
                                      _busy ? null : _toggleVariantAcceptance,
                                  child:
                                      const Text('Эта версия меня устраивает'),
                                ),
                        ],
                      ),
                    ),
                  ),
                if ('${widget.variantCapabilities['unavailableMessage'] ?? ''}'
                    .trim()
                    .isNotEmpty)
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
                    label: Text(
                      _busy ? 'Проверка…' : 'Проверить версию заново',
                    ),
                  ),
                ),
                if (_variantError != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      _variantError!,
                      key: const Key('variant-detail-error'),
                      style:
                          TextStyle(color: Theme.of(context).colorScheme.error),
                    ),
                  ),
              ],
              if (candidates.isNotEmpty) ...[
                const Divider(height: 28),
                Text(
                  'Кандидаты',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
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
          child: Text(l10n.close),
        ),
      ],
    );
  }
}
