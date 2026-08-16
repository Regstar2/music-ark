import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';

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

  Future<void> open(String rawPath) async {
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
    _title = file.uri.pathSegments.isEmpty
        ? file.path
        : Uri.decodeComponent(file.uri.pathSegments.last);
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

  @override
  Widget build(BuildContext context) {
    final controller = MusicArkAudioPlayer.instance;
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        if (!controller.hasTrack) return const SizedBox.shrink();

        final durationMs = controller.duration.inMilliseconds;
        final positionMs = controller.position.inMilliseconds.clamp(
          0,
          durationMs > 0 ? durationMs : 0,
        );
        final max = durationMs > 0 ? durationMs.toDouble() : 1.0;
        final value = durationMs > 0 ? positionMs.toDouble() : 0.0;

        return Material(
          key: const Key('now-playing-bar'),
          elevation: 8,
          color: Theme.of(context).colorScheme.surfaceContainerHigh,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                IconButton.filledTonal(
                  key: const Key('player-play-pause'),
                  tooltip: controller.playing ? 'Пауза' : 'Воспроизвести',
                  onPressed: controller.playOrPause,
                  icon: Icon(controller.playing ? Icons.pause : Icons.play_arrow),
                ),
                const SizedBox(width: 12),
                SizedBox(
                  width: 230,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        controller.title ?? 'Трек',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      if (controller.error != null)
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
                        const Text('Буферизация…', style: TextStyle(fontSize: 11)),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Text(_time(controller.position)),
                Expanded(
                  child: Slider(
                    key: const Key('player-seek'),
                    min: 0,
                    max: max,
                    value: value.clamp(0.0, max).toDouble(),
                    onChanged: durationMs <= 0
                        ? null
                        : (next) => controller.seek(
                              Duration(milliseconds: next.round()),
                            ),
                  ),
                ),
                Text(_time(controller.duration)),
                const SizedBox(width: 8),
                IconButton(
                  key: const Key('player-stop'),
                  tooltip: 'Остановить и закрыть плеер',
                  onPressed: controller.stop,
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
