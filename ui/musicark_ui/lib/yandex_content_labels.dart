import 'package:flutter/material.dart';

import 'app_localizations_ext.dart';
import 'content_label_bridge.dart';

class YandexContentLabelsButton extends StatelessWidget {
  const YandexContentLabelsButton({
    super.key,
    required this.bridge,
    ContentLabelBridgeClient? labelBridge,
  }) : labelBridge = labelBridge ?? const ContentLabelBridge();

  final MusicArkBridgeClient bridge;
  final ContentLabelBridgeClient labelBridge;

  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
        key: const Key('yandex-content-labels-open'),
        onPressed: () => showDialog<void>(
          context: context,
          builder: (_) => _YandexContentLabelsDialog(
            bridge: bridge,
            labelBridge: labelBridge,
          ),
        ),
        icon: const Icon(Icons.sell_outlined),
        label: Text(context.l10n.yandexVersionLabels),
      );
}

class _YandexContentLabelsDialog extends StatefulWidget {
  const _YandexContentLabelsDialog({
    required this.bridge,
    required this.labelBridge,
  });

  final MusicArkBridgeClient bridge;
  final ContentLabelBridgeClient labelBridge;

  @override
  State<_YandexContentLabelsDialog> createState() =>
      _YandexContentLabelsDialogState();
}

class _YandexContentLabelsDialogState
    extends State<_YandexContentLabelsDialog> {
  final _search = TextEditingController();
  List<Map<String, dynamic>> _tracks = const [];
  Map<String, String> _labels = const {};
  bool _busy = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
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
          .toList()
      : <Map<String, dynamic>>[];

  String _id(Map<String, dynamic> track) =>
      '${track['external_id'] ?? track['externalId'] ?? ''}'.trim();

  String _title(Map<String, dynamic> track) =>
      '${track['title'] ?? '—'}'.trim();

  String _artists(Map<String, dynamic> track) {
    final raw = track['artists'];
    if (raw is List) {
      return raw
          .map((item) => '$item')
          .where((item) => item.isNotEmpty)
          .join(', ');
    }
    return '${raw ?? ''}'.trim();
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final library = await widget.bridge.bootstrap();
      final unique = <String, Map<String, dynamic>>{};
      final liked = library['liked'] ?? library['library'];
      if (liked is Map) {
        for (final track in _maps(liked['tracks'])) {
          final id = _id(track);
          if (id.isNotEmpty) unique[id] = track;
        }
      }
      final playlists = library['playlists'];
      if (playlists is Map) {
        for (final playlist in _maps(playlists['items'])) {
          final playlistId = '${playlist['externalId'] ?? ''}'.trim();
          if (playlistId.isEmpty) continue;
          try {
            final payload = await widget.bridge.playlist(playlistId);
            final collection = payload['collection'];
            if (collection is Map) {
              for (final track in _maps(collection['tracks'])) {
                final id = _id(track);
                if (id.isNotEmpty) unique[id] = track;
              }
            }
          } on MusicArkBridgeException {
            // One unavailable cached playlist must not hide all other Yandex tracks.
          }
        }
      }
      final ids = unique.keys.toList(growable: false);
      final labelPayload = await widget.labelBridge.batch(externalIds: ids);
      final rawLabels = labelPayload['provider'];
      final labels = rawLabels is Map
          ? rawLabels.map((key, value) => MapEntry('$key', '$value'))
          : <String, String>{};
      if (!mounted) return;
      setState(() {
        _tracks = unique.values.toList(growable: false);
        _labels = labels;
      });
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _setLabel(Map<String, dynamic> track, String label) async {
    final id = _id(track);
    if (id.isEmpty) return;
    try {
      await widget.labelBridge.setProvider(id, label);
      if (!mounted) return;
      setState(() {
        final updated = Map<String, String>.from(_labels);
        if (label.isEmpty) {
          updated.remove(id);
        } else {
          updated[id] = label;
        }
        _labels = updated;
      });
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _error = error.message);
    }
  }

  List<Map<String, dynamic>> get _visible {
    final q = _search.text.trim().toLowerCase();
    if (q.isEmpty) return _tracks;
    return _tracks.where((track) {
      final haystack =
          '${_title(track)} ${_artists(track)} ${_id(track)}'.toLowerCase();
      return haystack.contains(q);
    }).toList(growable: false);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final visible = _visible;
    return AlertDialog(
      key: const Key('yandex-content-labels-dialog'),
      title: Text(l10n.yandexContentLabelsDialogTitle),
      content: SizedBox(
        width: 820,
        height: 640,
        child: Column(
          children: [
            Text(l10n.yandexContentLabelsDescription),
            const SizedBox(height: 8),
            TextField(
              key: const Key('yandex-content-labels-search'),
              controller: _search,
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                labelText: l10n.yandexContentLabelsSearch,
                prefixIcon: const Icon(Icons.search),
              ),
            ),
            if (_busy) const LinearProgressIndicator(),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  _error!,
                  key: const Key('yandex-content-labels-error'),
                ),
              ),
            const SizedBox(height: 8),
            Expanded(
              child: visible.isEmpty && !_busy
                  ? Center(child: Text(l10n.yandexContentLabelsEmpty))
                  : ListView.separated(
                      key: const Key('yandex-content-labels-list'),
                      itemCount: visible.length,
                      separatorBuilder: (_, _) => const Divider(height: 1),
                      itemBuilder: (context, index) {
                        final track = visible[index];
                        final id = _id(track);
                        final label = _labels[id];
                        return ListTile(
                          key: Key('yandex-content-label-track-$id'),
                          leading: const Icon(Icons.music_note),
                          title: Text(_title(track)),
                          subtitle: Text(
                            '${_artists(track)} · ${l10n.yandexIdPrefix}: $id',
                          ),
                          trailing: Wrap(
                            spacing: 6,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              if (label != null && label.isNotEmpty)
                                Chip(
                                  key: Key('yandex-content-label-$id'),
                                  visualDensity: VisualDensity.compact,
                                  label: Text(
                                    label == 'censored'
                                        ? l10n.censored
                                        : l10n.original,
                                  ),
                                ),
                              PopupMenuButton<String>(
                                key: Key('yandex-content-label-menu-$id'),
                                tooltip: l10n.yandexMarkTrack,
                                initialValue: label,
                                onSelected: (value) => _setLabel(track, value),
                                itemBuilder: (_) => [
                                  PopupMenuItem(
                                    value: 'original',
                                    child: Text(l10n.original),
                                  ),
                                  PopupMenuItem(
                                    value: 'censored',
                                    child: Text(l10n.censored),
                                  ),
                                  const PopupMenuDivider(),
                                  PopupMenuItem(
                                    value: '',
                                    child: Text(l10n.yandexClearLabel),
                                  ),
                                ],
                                icon: const Icon(Icons.sell_outlined),
                              ),
                            ],
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
          onPressed: _busy ? null : _load,
          child: Text(l10n.refresh),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context),
          child: Text(l10n.close),
        ),
      ],
    );
  }
}
