import 'package:flutter/widgets.dart';

class V012Strings {
  const V012Strings._(this.ru);
  final bool ru;

  factory V012Strings.of(BuildContext context) =>
      V012Strings._(Localizations.localeOf(context).languageCode.toLowerCase() == 'ru');

  String get networkTitle => ru ? 'Сеть и доступ к источникам' : 'Network and source access';
  String get networkHint => ru ? 'Маршрутизация применяется только к внешним источникам метаданных. Yandex upload остаётся отдельным.' : 'Routing applies only to external metadata sources. Yandex upload remains separate.';
  String get connectionMode => ru ? 'Режим подключения' : 'Connection mode';
  String get automatic => ru ? 'Автоматически' : 'Automatic';
  String get direct => ru ? 'Прямое' : 'Direct';
  String get warp => 'Cloudflare WARP';
  String get proxy => ru ? 'Прокси' : 'Proxy';
  String get proxyUrl => ru ? 'Пользовательский прокси' : 'Custom proxy';
  String get proxyType => ru ? 'Тип прокси' : 'Proxy type';
  String get refreshStatus => ru ? 'Обновить статус' : 'Refresh status';
  String get testConnection => ru ? 'Проверить подключение' : 'Test connection';
  String get installWarp => ru ? 'Установить WARP' : 'Install WARP';
  String get enableWarp => ru ? 'Включить WARP' : 'Enable WARP';
  String get disableWarp => ru ? 'Отключить WARP' : 'Disable WARP';
  String get save => ru ? 'Сохранить' : 'Save';
  String get notInstalled => ru ? 'Не установлен' : 'Not installed';
  String get installed => ru ? 'Установлен' : 'Installed';
  String get connected => ru ? 'Подключён' : 'Connected';
  String get localProxyReady => ru ? 'Local Proxy готов' : 'Local Proxy ready';
  String get localProxyNotReady => ru ? 'Подключён, Local Proxy не готов' : 'Connected, Local Proxy not ready';
  String get loading => ru ? 'Проверка…' : 'Checking…';
  String get password => ru ? 'Пароль прокси' : 'Proxy password';
  String get username => ru ? 'Имя пользователя' : 'Username';
  String get host => ru ? 'Хост' : 'Host';
  String get port => ru ? 'Порт' : 'Port';
  String get automaticIdentify => ru ? 'Автоматически определить' : 'Identify automatically';
  String get moreAlternatives => ru ? 'Показать больше вариантов' : 'Show more alternatives';
  String get externalMetadata => ru ? 'Внешние метаданные' : 'External metadata';
  String get applySelected => ru ? 'Применить выбранные поля' : 'Apply selected fields';
}
