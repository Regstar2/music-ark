import 'dart:io';

import 'audio_player.dart';

abstract interface class LocalFileActions {
  Future<void> play(String path);
  Future<void> reveal(String path);
}

class SystemLocalFileActions implements LocalFileActions {
  const SystemLocalFileActions();

  File _requireFile(String path) {
    final clean = path.trim();
    final file = File(clean).absolute;
    if (clean.isEmpty || !file.existsSync()) {
      throw FileSystemException('Музыкальный файл не найден.', path);
    }
    return file;
  }

  @override
  Future<void> play(String path) async {
    final file = _requireFile(path);
    await MusicArkAudioPlayer.instance.open(file.path);
  }

  @override
  Future<void> reveal(String path) async {
    final file = _requireFile(path);
    if (Platform.isWindows) {
      await Process.start(
        'explorer.exe',
        ['/select,${file.path}'],
        runInShell: false,
        mode: ProcessStartMode.detached,
      );
      return;
    }
    if (Platform.isMacOS) {
      await Process.start('open', ['-R', file.path], mode: ProcessStartMode.detached);
      return;
    }
    await Process.start('xdg-open', [file.parent.path], mode: ProcessStartMode.detached);
  }
}
