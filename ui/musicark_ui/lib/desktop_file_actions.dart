import 'dart:io';

abstract interface class LocalFileActions {
  Future<void> play(String path);
  Future<void> reveal(String path);
}

class SystemLocalFileActions implements LocalFileActions {
  const SystemLocalFileActions();

  File _requireFile(String path) {
    final file = File(path.trim()).absolute;
    if (path.trim().isEmpty || !file.existsSync()) {
      throw FileSystemException('Музыкальный файл не найден.', path);
    }
    return file;
  }

  @override
  Future<void> play(String path) async {
    final file = _requireFile(path);
    if (Platform.isWindows) {
      final result = await Process.run(
        'powershell.exe',
        [
          '-NoProfile',
          '-NonInteractive',
          '-Command',
          r'Invoke-Item -LiteralPath $args[0]',
          file.path,
        ],
        runInShell: false,
      );
      if (result.exitCode != 0) {
        throw ProcessException(
          'powershell.exe',
          const [],
          (result.stderr ?? '').toString(),
          result.exitCode,
        );
      }
      return;
    }
    if (Platform.isMacOS) {
      await Process.start('open', [file.path], mode: ProcessStartMode.detached);
      return;
    }
    await Process.start('xdg-open', [file.path], mode: ProcessStartMode.detached);
  }

  @override
  Future<void> reveal(String path) async {
    final file = _requireFile(path);
    if (Platform.isWindows) {
      await Process.start(
        'explorer.exe',
        ['/select,', file.path],
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
