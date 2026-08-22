import 'package:flutter/widgets.dart';

class V015Strings {
  const V015Strings._(this.ru);
  final bool ru;

  factory V015Strings.of(BuildContext context) =>
      V015Strings._(Localizations.localeOf(context).languageCode.toLowerCase() == 'ru');

  String get distributionTitle => ru ? 'Обновления и обратная связь' : 'Updates and feedback';
  String get distributionHint => ru
      ? 'MusicArk проверяет подписанный release manifest, сверяет размер и SHA-256 установщика и запускает обновление только после подтверждения.'
      : 'MusicArk checks the release manifest, verifies installer size and SHA-256, and launches an update only after confirmation.';
  String get checkUpdates => ru ? 'Проверить обновления' : 'Check for updates';
  String get checking => ru ? 'Проверка…' : 'Checking…';
  String get currentVersion => ru ? 'Текущая версия' : 'Current version';
  String get latestVersion => ru ? 'Последняя версия' : 'Latest version';
  String get updateAvailable => ru ? 'Доступно обновление' : 'Update available';
  String get upToDate => ru ? 'Установлена актуальная версия' : 'MusicArk is up to date';
  String get updateUnavailable => ru ? 'Канал обновлений пока недоступен.' : 'The update channel is currently unavailable.';
  String get downloadUpdate => ru ? 'Скачать обновление' : 'Download update';
  String get downloading => ru ? 'Загрузка и проверка…' : 'Downloading and verifying…';
  String get installUpdate => ru ? 'Установить обновление' : 'Install update';
  String get installTitle => ru ? 'Установить обновление MusicArk?' : 'Install MusicArk update?';
  String installBody(String version) => ru
      ? 'Будет запущен уже проверенный установщик версии $version. Установщик обновит приложение поверх текущей версии и не должен удалять пользовательские данные.'
      : 'The already verified installer for version $version will be launched. It upgrades the current installation and must not delete user data.';
  String get installerLaunched => ru ? 'Установщик запущен.' : 'Installer launched.';
  String get cancel => ru ? 'Отмена' : 'Cancel';
  String get reportBug => ru ? 'Сообщить об ошибке' : 'Report a bug';
  String get requestFeature => ru ? 'Предложить улучшение' : 'Request a feature';
  String get feedbackHint => ru
      ? 'Форма GitHub не получает токены, cookies, пути к музыке или содержимое библиотеки. Перед отправкой всё равно проверь текст отчёта.'
      : 'The GitHub form does not receive tokens, cookies, music paths, or library contents. Review the report text before submitting.';
  String get feedbackCopied => ru ? 'Ссылка скопирована в буфер обмена.' : 'The feedback link was copied to the clipboard.';
  String get operationFailed => ru ? 'Операция не выполнена.' : 'The operation could not be completed.';
}
