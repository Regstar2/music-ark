import 'dart:io';

import 'package:flutter/material.dart';

import 'app_localizations_ext.dart';
import 'app_ui_tokens.dart';
import 'musicark_bridge.dart';
import 'yandex_upload_bridge.dart';

Future<YandexUploadResult?> showYandexUploadDialog({
  required BuildContext context,
  required Map<String, dynamic> track,
  required YandexUploadBridgeClient bridge,
}) => showDialog<YandexUploadResult>(
  context: context,
  barrierDismissible: false,
  builder: (_) => YandexUploadDialog(track: track, bridge: bridge),
);

class YandexUploadDialog extends StatefulWidget {
  const YandexUploadDialog({
    super.key,
    required this.track,
    required this.bridge,
  });

  final Map<String, dynamic> track;
  final YandexUploadBridgeClient bridge;

  @override
  State<YandexUploadDialog> createState() => _YandexUploadDialogState();
}

class _YandexUploadDialogState extends State<YandexUploadDialog> {
  bool _loadingTargets = true;
  bool _submitting = false;
  bool _rightsConfirmed = false;
  bool _authenticated = false;
  String? _selectedPlaylistKind;
  String? _loadError;
  List<YandexUploadTarget> _playlists = const [];
  YandexUploadResult? _result;

  int? get _localFileId => int.tryParse('${widget.track['id']}');

  bool get _isMp3 {
    final extension = '${widget.track['extension'] ?? ''}'.trim().toLowerCase();
    final filename = '${widget.track['fileName'] ?? ''}'.trim().toLowerCase();
    return extension == '.mp3' || extension == 'mp3' || filename.endsWith('.mp3');
  }

  bool get _canSubmit =>
      !_loadingTargets &&
      !_submitting &&
      _result == null &&
      _authenticated &&
      _isMp3 &&
      _localFileId != null &&
      _selectedPlaylistKind != null &&
      _rightsConfirmed;

  @override
  void initState() {
    super.initState();
    _loadTargets();
  }

  Future<void> _loadTargets() async {
    try {
      final targets = await widget.bridge.targets();
      if (!mounted) return;
      setState(() {
        _authenticated = targets.authenticated;
        _playlists = targets.playlists;
        _loadingTargets = false;
      });
    } on MusicArkBridgeException {
      if (!mounted) return;
      setState(() {
        _loadError = 'bridge';
        _loadingTargets = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadError = 'bridge';
        _loadingTargets = false;
      });
    }
  }

  Future<void> _submit() async {
    if (!_canSubmit) return;
    final localFileId = _localFileId;
    final playlistKind = _selectedPlaylistKind;
    if (localFileId == null || playlistKind == null) return;
    setState(() => _submitting = true);
    try {
      final result = await widget.bridge.uploadTrack(
        localFileId: localFileId,
        playlistKind: playlistKind,
        confirm: true,
        rightsConfirmed: true,
      );
      if (!mounted) return;
      setState(() {
        _result = result;
        _submitting = false;
      });
    } on MusicArkBridgeException {
      if (!mounted) return;
      setState(() {
        _loadError = 'bridge';
        _submitting = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadError = 'bridge';
        _submitting = false;
      });
    }
  }

  String _artists() {
    final raw = widget.track['artists'];
    if (raw is List) {
      final text = raw.map((item) => '$item').where((item) => item.isNotEmpty).join(', ');
      if (text.isNotEmpty) return text;
    }
    return context.l10n.localUnknownArtist;
  }

  String _sizeLabel() {
    final raw = double.tryParse('${widget.track['fileSize'] ?? 0}') ?? 0;
    if (raw <= 0) return '—';
    final mb = raw / (1024 * 1024);
    return mb >= 0.1 ? '${mb.toStringAsFixed(1)} MB' : '${(raw / 1024).toStringAsFixed(0)} KB';
  }

  Widget _artwork() {
    final artwork = Map<String, dynamic>.from(
      widget.track['artwork'] as Map? ?? const {},
    );
    final path = '${artwork['cachePath'] ?? ''}';
    final file = path.isEmpty ? null : File(path);
    return ClipRRect(
      borderRadius: AppUiTokens.smallRadius,
      child: SizedBox(
        width: 72,
        height: 72,
        child: file != null && file.existsSync()
            ? Image.file(file, fit: BoxFit.cover, cacheWidth: 144, cacheHeight: 144)
            : ColoredBox(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                child: const Icon(Icons.album_outlined, size: 40),
              ),
      ),
    );
  }

  Widget _statusCard() {
    final l10n = context.l10n;
    final result = _result;
    if (_submitting) {
      return _UploadStateCard(
        key: const Key('yandex-upload-state-uploading'),
        icon: const SizedBox(
          width: 20,
          height: 20,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
        title: l10n.yandexUploadUploading,
        body: l10n.yandexUploadUploadingHint,
      );
    }
    if (result == null) return const SizedBox.shrink();
    return switch (result.status) {
      YandexUploadStatus.verified => _UploadStateCard(
        key: const Key('yandex-upload-state-completed'),
        icon: const Icon(Icons.check_circle_outline),
        title: l10n.yandexUploadCompleted,
        body: l10n.yandexUploadSuccess,
      ),
      YandexUploadStatus.processing => _UploadStateCard(
        key: const Key('yandex-upload-state-processing'),
        icon: const SizedBox(
          width: 20,
          height: 20,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
        title: l10n.yandexUploadProcessing,
        body: l10n.yandexUploadProcessingHint,
      ),
      YandexUploadStatus.deliveryUnknown => _UploadStateCard(
        key: const Key('yandex-upload-state-delivery-unknown'),
        icon: const Icon(Icons.help_outline),
        title: l10n.yandexUploadDeliveryUnknown,
        body: l10n.yandexUploadDeliveryUnknownHint,
      ),
      YandexUploadStatus.unsupportedFormat => _UploadStateCard(
        key: const Key('yandex-upload-state-unsupported'),
        icon: const Icon(Icons.warning_amber_outlined),
        title: l10n.yandexUploadError,
        body: l10n.yandexUploadMp3Only,
      ),
      YandexUploadStatus.ambiguous => _UploadStateCard(
        key: const Key('yandex-upload-state-ambiguous'),
        icon: const Icon(Icons.help_outline),
        title: l10n.yandexUploadError,
        body: l10n.yandexUploadAmbiguous,
      ),
      _ => _UploadStateCard(
        key: const Key('yandex-upload-state-error'),
        icon: const Icon(Icons.error_outline),
        title: l10n.yandexUploadError,
        body: l10n.yandexUploadNetworkError,
      ),
    };
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final title = (widget.track['title'] ?? widget.track['fileName'] ?? l10n.localUnknownTrack).toString();
    final fileName = '${widget.track['fileName'] ?? ''}';
    final format = '${widget.track['codec'] ?? widget.track['extension'] ?? '—'}'.toUpperCase();
    final hasTerminalResult = _result != null;

    return AlertDialog(
      key: const Key('yandex-upload-dialog'),
      title: Text(l10n.yandexUploadDialogTitle),
      content: SizedBox(
        width: 560,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _artwork(),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(title, style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 3),
                        Text(_artists()),
                        const SizedBox(height: 8),
                        Text('${l10n.yandexUploadFilename}: $fileName'),
                        Text('${l10n.yandexUploadFormat}: $format'),
                        Text('${l10n.yandexUploadSize}: ${_sizeLabel()}'),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              if (_loadingTargets)
                _UploadStateCard(
                  key: const Key('yandex-upload-state-preparing'),
                  icon: const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  title: l10n.yandexUploadPreparing,
                  body: l10n.yandexUploadPreparingHint,
                )
              else if (_loadError != null)
                _UploadStateCard(
                  key: const Key('yandex-upload-target-error'),
                  icon: const Icon(Icons.error_outline),
                  title: l10n.yandexUploadError,
                  body: l10n.yandexUploadNetworkError,
                )
              else if (!_authenticated)
                _UploadStateCard(
                  key: const Key('yandex-upload-auth-required'),
                  icon: const Icon(Icons.login_outlined),
                  title: l10n.yandexUploadError,
                  body: l10n.yandexUploadAuthRequired,
                )
              else if (_playlists.isEmpty)
                _UploadStateCard(
                  key: const Key('yandex-upload-no-playlists'),
                  icon: const Icon(Icons.playlist_remove_outlined),
                  title: l10n.yandexUploadError,
                  body: l10n.yandexUploadNoPlaylists,
                )
              else ...[
                DropdownButtonFormField<String>(
                  key: const Key('yandex-upload-playlist'),
                  initialValue: _selectedPlaylistKind,
                  decoration: InputDecoration(
                    labelText: l10n.yandexUploadTargetPlaylist,
                    border: const OutlineInputBorder(),
                  ),
                  items: _playlists
                      .map(
                        (playlist) => DropdownMenuItem(
                          value: playlist.playlistKind,
                          child: Text(playlist.title),
                        ),
                      )
                      .toList(growable: false),
                  onChanged: _submitting || hasTerminalResult
                      ? null
                      : (value) => setState(() => _selectedPlaylistKind = value),
                ),
                const SizedBox(height: 10),
                CheckboxListTile(
                  key: const Key('yandex-upload-rights'),
                  contentPadding: EdgeInsets.zero,
                  controlAffinity: ListTileControlAffinity.leading,
                  value: _rightsConfirmed,
                  onChanged: _submitting || hasTerminalResult
                      ? null
                      : (value) => setState(() => _rightsConfirmed = value == true),
                  title: Text(l10n.yandexUploadRightsConfirmation),
                ),
              ],
              if (!_isMp3) ...[
                const SizedBox(height: 10),
                _UploadStateCard(
                  key: const Key('yandex-upload-mp3-only'),
                  icon: const Icon(Icons.warning_amber_outlined),
                  title: l10n.yandexUploadError,
                  body: l10n.yandexUploadMp3Only,
                ),
              ],
              if (_submitting || _result != null) ...[
                const SizedBox(height: 12),
                _statusCard(),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          key: const Key('yandex-upload-close'),
          onPressed: _submitting
              ? null
              : () => Navigator.pop(context, _result),
          child: Text(hasTerminalResult ? l10n.close : l10n.cancel),
        ),
        if (!hasTerminalResult)
          FilledButton.icon(
            key: const Key('yandex-upload-submit'),
            onPressed: _canSubmit ? _submit : null,
            icon: const Icon(Icons.cloud_upload_outlined),
            label: Text(l10n.yandexUploadButton),
          ),
      ],
    );
  }
}

class _UploadStateCard extends StatelessWidget {
  const _UploadStateCard({
    super.key,
    required this.icon,
    required this.title,
    required this.body,
  });

  final Widget icon;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        borderRadius: AppUiTokens.smallRadius,
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            icon,
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 3),
                  Text(body),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
