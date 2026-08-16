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
    final folder = file.parent.absolute;
    if (!folder.existsSync()) {
      throw FileSystemException('Папка музыкального файла не найдена.', folder.path);
    }
    if (Platform.isWindows) {
      // Opening the containing directory is more reliable than Explorer /select
      // for Unicode/space-heavy paths. /select may silently fall back to the
      // default Documents folder when Explorer rejects the argument.
      await Process.start(
        'explorer.exe',
        [folder.path],
        runInShell: false,
        mode: ProcessStartMode.detached,
      );
      return;
    }
    if (Platform.isMacOS) {
      await Process.start('open', ['-R', file.path], mode: ProcessStartMode.detached);
      return;
    }
    await Process.start('xdg-open', [folder.path], mode: ProcessStartMode.detached);
  }
}
