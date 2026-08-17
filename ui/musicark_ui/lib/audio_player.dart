import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';

import 'app_localizations_ext.dart';
import 'app_ui_tokens.dart';

/// Application-wide local audio player.
///
/// MusicArk owns playback. Local files are never delegated to the operating
/// system's associated media player.
class MusicArkAudioPlayer extends ChangeNotifier {
  MusicArkAudioPlayer._();

  static final MusicArkAudioPlayer instance = MusicArkAudioPlayer._();

  Player? _player;
  final List<StreamSubscription<dynamic>> _subscriptions = [];

  String? _path;
  String? _title;
  bool _playing = false;
  bool _buffering = false;
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;
  String? _error;

  String? get path => _path;
  String? get title => _title;
  bool get playing => _playing;
  bool get buffering => _buffering;
  Duration get position => _position;
  Duration get duration => _duration;
  String? get error => _error;
  bool get hasTrack => _path != null;

  void _ensurePlayer() {
    if (_player != null) return;
    final player = Player();
    _player = player;
    _subscriptions.addAll([
      player.stream.playing.listen((value) {
        _playing = value;
        notifyListeners();
      }),
      player.stream.buffering.listen((value) {
        _buffering = value;
        notifyListeners();
      }),
      player.stream.position.listen((value) {
        _position = value;
        notifyListeners();
      }),
      player.stream.duration.listen((value) {
        _duration = value;
        notifyListeners();
      }),
      player.stream.error.listen((value) {
        _error = value;
        notifyListeners();
      }),
      player.stream.completed.listen((value) {
        if (value) {
          _playing = false;
          notifyListeners();
        }
      }),
    ]);
  }

  Future<void> open(String rawPath, {String? title}) async {
    final path = rawPath.trim();
    if (path.isEmpty) {
      throw FileSystemException('Музыкальный файл не указан.', path);
    }
    final file = File(path).absolute;
    if (!file.existsSync()) {
      throw FileSystemException('Музыкальный файл не найден.', path);
    }

    _ensurePlayer();
    _path = file.path;
    final displayTitle = title?.trim() ?? '';
    _title = displayTitle.isNotEmpty
        ? displayTitle
        : (file.uri.pathSegments.isEmpty
            ? file.path
            : Uri.decodeComponent(file.uri.pathSegments.last));
    _position = Duration.zero;
    _duration = Duration.zero;
    _error = null;
    notifyListeners();

    await _player!.open(Media(file.uri.toString()), play: true);
  }

  Future<void> playOrPause() async {
    final player = _player;
    if (player == null || _path == null) return;
    await player.playOrPause();
  }

  Future<void> seek(Duration position) async {
    final player = _player;
    if (player == null || _duration <= Duration.zero) return;
    var target = position;
    if (target < Duration.zero) target = Duration.zero;
    if (target > _duration) target = _duration;
    await player.seek(target);
  }

  Future<void> stop() async {
    final player = _player;
    if (player != null) await player.stop();
    _path = null;
    _title = null;
    _playing = false;
    _buffering = false;
    _position = Duration.zero;
    _duration = Duration.zero;
    _error = null;
    notifyListeners();
  }
}

class MusicArkNowPlayingBar extends StatelessWidget {
  const MusicArkNowPlayingBar({super.key});

  String _time(Duration value) {
    final seconds = value.inSeconds < 0 ? 0 : value.inSeconds;
    final minutes = seconds ~/ 60;
    final remainder = seconds % 60;
    return '$minutes:${remainder.toString().padLeft(2, '0')}';
  }

  ({String title, String? artist}) _displayParts(String? raw, String fallback) {
    final text = raw?.trim() ?? '';
    if (text.isEmpty) return (title: fallback, artist: null);
    final separator = text.indexOf(' — ');
    if (separator <= 0 || separator >= text.length - 3) {
      return (title: text, artist: null);
    }
    return (
      title: text.substring(separator + 3).trim(),
      artist: text.substring(0, separator).trim(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final controller = MusicArkAudioPlayer.instance;
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        if (!controller.hasTrack) return const SizedBox.shrink();

        final l10n = context.l10n;
        final durationMs = controller.duration.inMilliseconds;
        final positionMs = controller.position.inMilliseconds.clamp(
          0,
          durationMs > 0 ? durationMs : 0,
        );
        final max = durationMs > 0 ? durationMs.toDouble() : 1.0;
        final value = durationMs > 0 ? positionMs.toDouble() : 0.0;
        final parts = _displayParts(controller.title, l10n.yandexTrackFallback);

        Widget artwork() => Container(
              width: AppUiTokens.artworkSize,
              height: AppUiTokens.artworkSize,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.secondaryContainer,
                borderRadius: AppUiTokens.smallRadius,
              ),
              child: Icon(
                Icons.album_outlined,
                color: Theme.of(context).colorScheme.onSecondaryContainer,
              ),
            );

        Widget titleBlock() => Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  parts.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                if (parts.artist != null && parts.artist!.isNotEmpty)
                  Text(
                    parts.artist!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  )
                else if (controller.error != null)
                  Text(
                    controller.error!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                      fontSize: 11,
                    ),
                  )
                else if (controller.buffering)
                  Text(l10n.yandexBuffering, style: const TextStyle(fontSize: 11)),
              ],
            );

        Widget playButton() => IconButton.filled(
              key: const Key('player-play-pause'),
              tooltip: controller.playing ? l10n.yandexPause : l10n.play,
              onPressed: controller.playOrPause,
              icon: Icon(controller.playing ? Icons.pause : Icons.play_arrow),
            );

        Widget stopButton() => IconButton(
              key: const Key('player-stop'),
              tooltip: l10n.yandexStopPlayer,
              onPressed: controller.stop,
              icon: const Icon(Icons.close),
            );

        Widget slider() => Slider(
              key: const Key('player-seek'),
              min: 0,
              max: max,
              value: value.clamp(0.0, max).toDouble(),
              onChanged: durationMs <= 0
                  ? null
                  : (next) => controller.seek(
                        Duration(milliseconds: next.round()),
                      ),
            );

        return Material(
          key: const Key('now-playing-bar'),
          elevation: 3,
          color: Theme.of(context).colorScheme.surfaceContainerHigh,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final compact = constraints.maxWidth < 760;
              if (compact) {
                return Padding(
                  padding: const EdgeInsets.fromLTRB(12, 8, 8, 6),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        children: [
                          artwork(),
                          const SizedBox(width: 10),
                          Expanded(child: titleBlock()),
                          const SizedBox(width: 8),
                          playButton(),
                          stopButton(),
                        ],
                      ),
                      Row(
                        children: [
                          Text(_time(controller.position), style: Theme.of(context).textTheme.labelSmall),
                          Expanded(child: slider()),
                          Text(_time(controller.duration), style: Theme.of(context).textTheme.labelSmall),
                        ],
                      ),
                    ],
                  ),
                );
              }

              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
                child: Row(
                  children: [
                    artwork(),
                    const SizedBox(width: 12),
                    SizedBox(width: 260, child: titleBlock()),
                    const SizedBox(width: 20),
                    playButton(),
                    const SizedBox(width: 16),
                    Text(_time(controller.position)),
                    Expanded(child: slider()),
                    Text(_time(controller.duration)),
                    const SizedBox(width: 8),
                    stopButton(),
                  ],
                ),
              );
            },
          ),
        );
      },
    );
  }
}
