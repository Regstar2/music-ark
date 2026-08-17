import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';


enum AppThemePreference { system, light, dark }

enum AppLocalePreference { system, ru, en }

abstract interface class AppSettingsStorage {
  Future<Map<String, dynamic>> read();
  Future<void> write(Map<String, dynamic> value);
}

class JsonAppSettingsStorage implements AppSettingsStorage {
  JsonAppSettingsStorage({File? file}) : _file = file ?? File(_defaultPath());

  final File _file;

  static String _defaultPath() {
    final home = Platform.environment['USERPROFILE']?.trim().isNotEmpty == true
        ? Platform.environment['USERPROFILE']!.trim()
        : (Platform.environment['HOME']?.trim().isNotEmpty == true
            ? Platform.environment['HOME']!.trim()
            : Directory.current.path);
    return '$home${Platform.pathSeparator}.musicark${Platform.pathSeparator}ui_preferences.json';
  }

  @override
  Future<Map<String, dynamic>> read() async {
    if (!await _file.exists()) return const {};
    try {
      final decoded = jsonDecode(await _file.readAsString());
      return decoded is Map ? Map<String, dynamic>.from(decoded) : const {};
    } on FormatException {
      return const {};
    } on FileSystemException {
      return const {};
    }
  }

  @override
  Future<void> write(Map<String, dynamic> value) async {
    await _file.parent.create(recursive: true);
    final temp = File('${_file.path}.tmp');
    await temp.writeAsString(jsonEncode(value), flush: true);
    try {
      if (await _file.exists()) await _file.delete();
      await temp.rename(_file.path);
    } on FileSystemException {
      await _file.writeAsString(jsonEncode(value), flush: true);
      if (await temp.exists()) await temp.delete();
    }
  }
}

class AppSettingsController extends ChangeNotifier {
  AppSettingsController({AppSettingsStorage? storage})
      : _storage = storage ?? JsonAppSettingsStorage();

  final AppSettingsStorage _storage;
  AppThemePreference _theme = AppThemePreference.system;
  AppLocalePreference _locale = AppLocalePreference.system;
  bool _loaded = false;

  AppThemePreference get themePreference => _theme;
  AppLocalePreference get localePreference => _locale;
  bool get loaded => _loaded;

  ThemeMode get themeMode => switch (_theme) {
        AppThemePreference.system => ThemeMode.system,
        AppThemePreference.light => ThemeMode.light,
        AppThemePreference.dark => ThemeMode.dark,
      };

  Locale? get locale => switch (_locale) {
        AppLocalePreference.system => null,
        AppLocalePreference.ru => const Locale('ru'),
        AppLocalePreference.en => const Locale('en'),
      };

  Future<void> load() async {
    final value = await _storage.read();
    _theme = AppThemePreference.values.firstWhere(
      (item) => item.name == value['themeMode'],
      orElse: () => AppThemePreference.system,
    );
    _locale = AppLocalePreference.values.firstWhere(
      (item) => item.name == value['localeMode'],
      orElse: () => AppLocalePreference.system,
    );
    _loaded = true;
    notifyListeners();
  }

  Future<void> setThemePreference(AppThemePreference value) async {
    if (_theme == value) return;
    _theme = value;
    notifyListeners();
    await _persist();
  }

  Future<void> setLocalePreference(AppLocalePreference value) async {
    if (_locale == value) return;
    _locale = value;
    notifyListeners();
    await _persist();
  }

  Future<void> _persist() => _storage.write({
        'schemaVersion': 1,
        'themeMode': _theme.name,
        'localeMode': _locale.name,
      });
}
