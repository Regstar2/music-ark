import 'package:flutter/widgets.dart';

import 'l10n/app_localizations.dart';

extension MusicArkLocalizations on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this)!;

  bool get _musicArkEnglish => Localizations.localeOf(this).languageCode == 'en';

  String get v013SourceFormat => _musicArkEnglish ? 'Source format' : 'Исходный формат';
  String get v013UploadFormat => _musicArkEnglish ? 'Upload format' : 'Формат загрузки';
  String get v013ConversionRequired =>
      _musicArkEnglish ? 'Conversion required' : 'Требуется преобразование';
  String get v013Yes => _musicArkEnglish ? 'Yes' : 'Да';
  String get v013No => _musicArkEnglish ? 'No' : 'Нет';
  String get v013ConversionWarning => _musicArkEnglish
      ? 'Will be converted to MP3 for upload. The source file will not be changed.'
      : 'Будет преобразован в MP3 для загрузки. Исходный файл не изменится.';
  String get v013Converting => _musicArkEnglish ? 'Converting' : 'Преобразование';
  String get v013ConvertingHint => _musicArkEnglish
      ? 'MusicArk is preparing a temporary MP3. The source file remains unchanged.'
      : 'MusicArk подготавливает временный MP3. Исходный файл остаётся без изменений.';
  String get v013FfmpegUnavailable => _musicArkEnglish
      ? 'FFmpeg is unavailable. Configure a supported FFmpeg executable and try again.'
      : 'FFmpeg недоступен. Настройте поддерживаемый FFmpeg и повторите попытку.';
  String get v013UnsupportedFormat => _musicArkEnglish
      ? 'This audio format cannot be uploaded safely.'
      : 'Этот аудиоформат нельзя безопасно загрузить.';
  String get v013MetadataSupported =>
      _musicArkEnglish ? 'Metadata editing: supported' : 'Редактирование метаданных: поддерживается';
  String get v013MetadataReadOnly =>
      _musicArkEnglish ? 'Metadata editing: read-only' : 'Редактирование метаданных: только чтение';
  String get v013ArtworkSupported =>
      _musicArkEnglish ? 'Artwork editing: supported' : 'Редактирование обложки: поддерживается';
  String get v013ArtworkUnavailable =>
      _musicArkEnglish ? 'Artwork editing: unavailable' : 'Редактирование обложки: недоступно';
  String get v013DirectMp3 => _musicArkEnglish ? 'Direct MP3' : 'MP3 без преобразования';
  String get v013WillConvert => _musicArkEnglish ? 'Will convert' : 'Будет преобразовано';
  String get v013Unsupported => _musicArkEnglish ? 'Unsupported' : 'Не поддерживается';
}

extension MusicArkLocalizationAliases on AppLocalizations {
  String get yandexFavoriteAlbumsTitle => yandexAlbumsTab;
}
