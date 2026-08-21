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
  String get configureWarpProxy => ru ? 'Настроить Local Proxy' : 'Configure Local Proxy';
  String get disableWarp => ru ? 'Отключить WARP' : 'Disable WARP';
  String get save => ru ? 'Сохранить' : 'Save';
  String get notInstalled => ru ? 'Не установлен' : 'Not installed';
  String get installed => ru ? 'Установлен' : 'Installed';
  String get connected => ru ? 'Подключён' : 'Connected';
  String get configuring => ru ? 'Настраивается…' : 'Configuring…';
  String get localProxyReady => ru ? 'Local Proxy готов' : 'Local Proxy ready';
  String get localProxyNotReady => ru ? 'Подключён, Local Proxy не готов' : 'Connected, Local Proxy not ready';
  String get loading => ru ? 'Проверка…' : 'Checking…';
  String get hostReached => ru ? 'хост доступен' : 'host reached';
  String networkSummary(int ok, int reached, int failed) => ru
      ? '$ok API OK · $reached хостов доступны · $failed ошибок'
      : '$ok API OK · $reached hosts reached · $failed failed';
  String get password => ru ? 'Пароль прокси' : 'Proxy password';
  String get username => ru ? 'Имя пользователя' : 'Username';
  String get host => ru ? 'Хост' : 'Host';
  String get port => ru ? 'Порт' : 'Port';

  String get sourcesTitle => ru ? 'Источники метаданных' : 'Metadata sources';
  String get sourcesHint => ru
      ? 'MusicBrainz и обложки работают без ключей. Ключи приложения для дополнительных источников обычный пользователь вводить не должен.'
      : 'MusicBrainz and cover art work without keys. Ordinary users should not have to enter application keys for optional sources.';
  String get builtIn => ru ? 'Встроен' : 'Built in';
  String get builtInFree => ru ? 'Встроенный free tier' : 'Built-in free tier';
  String get appCredential => ru ? 'Ключ MusicArk' : 'MusicArk application key';
  String get localCredential => ru ? 'Локальный ключ для тестирования' : 'Local testing key';
  String get plannedForRelease => ru ? 'Ключ приложения будет добавлен к релизу' : 'Application key will be supplied for release';
  String get optionalFallback => ru ? 'Необязательный fallback' : 'Optional fallback';
  String get advancedSources => ru ? 'Дополнительные источники — разработка/тестирование' : 'Optional sources — development/testing';
  String get advancedSourcesHint => ru
      ? 'Эти поля нужны только сейчас для разработки. В релизе AcoustID/Last.fm должны использовать ключи приложения MusicArk. Discogs останется необязательным.'
      : 'These fields are for development only. Release builds should use MusicArk application keys for AcoustID/Last.fm. Discogs remains optional.';
  String get acoustIdApplicationKey => ru ? 'AcoustID application key' : 'AcoustID application key';
  String get discogsToken => ru ? 'Discogs personal token (необязательно)' : 'Discogs personal token (optional)';
  String get lastFmApiKey => ru ? 'Last.fm API key' : 'Last.fm API key';
  String get theAudioDbKey => ru ? 'TheAudioDB key (необязательно, сейчас используется 123)' : 'TheAudioDB key (optional, currently uses 123)';
  String get leaveBlankToKeep => ru ? 'Оставь пустым, чтобы не менять' : 'Leave blank to keep current value';
  String get saveSourceKeys => ru ? 'Сохранить введённые ключи' : 'Save entered keys';
  String get clearLocalSourceKeys => ru ? 'Удалить локальные ключи' : 'Clear local keys';
  String get sourceKeysSaved => ru ? 'Ключи источников сохранены в системном хранилище.' : 'Source keys saved in the system credential store.';
  String get sourceKeysCleared => ru ? 'Локальные ключи удалены.' : 'Local source keys cleared.';

  String get automaticIdentify => ru ? 'Автоматически определить' : 'Identify automatically';
  String get moreAlternatives => ru ? 'Показать больше вариантов' : 'Show more alternatives';
  String get externalMetadata => ru ? 'Внешние метаданные' : 'External metadata';
  String get applySelected => ru ? 'Применить выбранные поля' : 'Apply selected fields';
}
