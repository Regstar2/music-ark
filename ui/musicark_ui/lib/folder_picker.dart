import 'package:file_selector/file_selector.dart' as file_selector;

abstract interface class LocalFolderPicker {
  Future<String?> pickDirectory();
}

class SystemLocalFolderPicker implements LocalFolderPicker {
  const SystemLocalFolderPicker();

  @override
  Future<String?> pickDirectory() => file_selector.getDirectoryPath(
        confirmButtonText: 'Добавить папку',
        canCreateDirectories: false,
      );
}

class FakeLocalFolderPicker implements LocalFolderPicker {
  FakeLocalFolderPicker(this.path);
  final String? path;

  @override
  Future<String?> pickDirectory() async => path;
}
