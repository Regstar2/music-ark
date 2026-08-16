import 'dart:io';

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
    if (Platform.isWindows) {
      // Do not append the file path after `-Command`: Windows PowerShell does not
      // reliably expose that value through `$args` in this launch shape. Passing
      // it through an environment variable also avoids quoting problems with
      // spaces, Cyrillic and PowerShell metacharacters in real music paths.
      final result = await Process.run(
        'powershell.exe',
        [
          '-NoProfile',
          '-NonInteractive',
          '-Command',
          r'Invoke-Item -LiteralPath $env:MUSICARK_OPEN_FILE',
        ],
        runInShell: false,
        environment: {
          'MUSICARK_OPEN_FILE': file.path,
        },
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
