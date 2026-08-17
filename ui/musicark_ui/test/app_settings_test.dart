import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/app_settings.dart';

class _MemorySettingsStorage implements AppSettingsStorage {
  Map<String, dynamic> value = {};

  @override
  Future<Map<String, dynamic>> read() async => Map<String, dynamic>.from(value);

  @override
  Future<void> write(Map<String, dynamic> value) async {
    this.value = Map<String, dynamic>.from(value);
  }
}

void main() {
  test('settings default to system and persist explicit choices', () async {
    final storage = _MemorySettingsStorage();
    final settings = AppSettingsController(storage: storage);

    await settings.load();
    expect(settings.themeMode, ThemeMode.system);
    expect(settings.locale, isNull);

    await settings.setThemePreference(AppThemePreference.dark);
    await settings.setLocalePreference(AppLocalePreference.en);

    final recreated = AppSettingsController(storage: storage);
    await recreated.load();
    expect(recreated.themeMode, ThemeMode.dark);
    expect(recreated.locale, const Locale('en'));
  });

  test('invalid persisted values fall back to system', () async {
    final storage = _MemorySettingsStorage()
      ..value = {'themeMode': 'future-theme', 'localeMode': 'de'};
    final settings = AppSettingsController(storage: storage);

    await settings.load();

    expect(settings.themePreference, AppThemePreference.system);
    expect(settings.localePreference, AppLocalePreference.system);
  });
}
