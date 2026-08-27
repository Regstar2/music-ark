import 'l10n/app_localizations.dart';

/// RU/EN copy for the v0.11.1 recovery/upload workspace.
///
/// This stays next to the generated localization facade so widgets never carry
/// language conditionals or duplicate product copy inline.
extension V0111Localizations on AppLocalizations {
  bool get _ru => localeName.toLowerCase().startsWith('ru');

  String get v0111Collection => _ru ? 'Коллекция' : 'Collection';
  String get v0111LocalFolder => _ru ? 'Локальная папка' : 'Local folder';
  String get v0111LocalFolders => _ru ? 'Локальные папки' : 'Local folders';
  String get v0111AllFolders => _ru ? 'Все папки' : 'All folders';
  String get v0111FolderNotSelected => _ru ? 'не выбрана' : 'not selected';
  String get v0111FolderNotRequired => _ru
      ? 'не выбрана / не требуется для этого плана'
      : 'not selected / not required for this plan';

  String v0111Selected(int count) =>
      _ru ? 'Выбрано: $count' : 'Selected: $count';
  String get v0111SelectAllVisible =>
      _ru ? 'Выбрать все видимые' : 'Select all visible';
  String get v0111ClearSelection => _ru ? 'Снять выбор' : 'Clear selection';
  String get v0111UploadToYandex =>
      _ru ? 'Загрузить в Яндекс Музыку' : 'Upload to Yandex Music';
  String v0111BulkUploadTitle(int count) => _ru
      ? 'Загрузить $count треков в Яндекс Музыку'
      : 'Upload $count tracks to Yandex Music';
  String get v0111TrackCount => _ru ? 'Количество' : 'Tracks';
  String get v0111TotalSize => _ru ? 'Общий размер' : 'Total size';
  String get v0111Mp3Count => _ru ? 'MP3' : 'MP3';
  String get v0111UnsupportedCount => _ru ? 'Неподдерживаемые' : 'Unsupported';
  String get v0111TargetPlaylist =>
      _ru ? 'Целевой плейлист' : 'Target playlist';
  String get v0111BatchRights => _ru
      ? 'Я подтверждаю, что имею право загружать выбранные аудиофайлы в Яндекс Музыку.'
      : 'I confirm that I have the right to upload the selected audio files to Yandex Music.';
  String v0111BatchProgress(int done, int total) => '$done / $total';
  String get v0111CancelRemaining =>
      _ru ? 'Отменить оставшиеся' : 'Cancel remaining';
  String get v0111RetryFailures => _ru ? 'Повторить ошибки' : 'Retry failures';
  String get v0111CheckPlaylist =>
      _ru ? 'Проверить плейлист' : 'Check playlist';
  String get v0111BatchFinished =>
      _ru ? 'Массовая загрузка завершена' : 'Bulk upload finished';
  String get v0111BatchCancelled =>
      _ru ? 'Оставшиеся отменены' : 'Remaining items cancelled';
  String get v0111BatchFailed =>
      _ru ? 'Загрузка завершилась с ошибками' : 'Upload finished with errors';
  String get v0111Verified => _ru ? 'Подтверждено' : 'Verified';
  String get v0111Processing => _ru ? 'Обрабатывается' : 'Processing';
  String get v0111DeliveryUnknown =>
      _ru ? 'Результат не определён' : 'Delivery unknown';
  String get v0111Failed => _ru ? 'Ошибки' : 'Failed';
  String get v0111Skipped => _ru ? 'Пропущено' : 'Skipped';
  String get v0111Cancelled => _ru ? 'Отменено' : 'Cancelled';

  String get v0111ManagedPlaylists =>
      _ru ? 'Плейлисты MusicArk' : 'MusicArk playlists';
  String get v0111ManagedConfigured => _ru ? 'Настроен' : 'Configured';
  String get v0111ManagedNotConfigured =>
      _ru ? 'Не настроен' : 'Not configured';
  String get v0111ManagedCreateUnavailable => _ru
      ? 'Автосоздание отключено до подтверждённого live-теста API.'
      : 'Automatic creation is disabled until a live API proof succeeds.';
  String get v0111Select => _ru ? 'Выбрать' : 'Select';
  String get v0111Change => _ru ? 'Изменить' : 'Change';
  String get v0111Ensure => _ru ? 'Проверить плейлисты' : 'Ensure playlists';
  String get v0111RoleCensored => _ru ? 'ЦЕНЗУРА' : 'CENSORED';
  String get v0111RoleUploaded => _ru ? 'ЗАГРУЖЕННЫЕ ТРЕКИ' : 'UPLOADED TRACKS';
  String get v0111RoleUnavailable => _ru ? 'НЕДОСТУПНЫЕ' : 'UNAVAILABLE';

  String get v0111SyncPlanTab => _ru ? 'План синхронизации' : 'Sync plan';
  String get v0111RecoveryTab => _ru ? 'Восстановление' : 'Recovery';
  String get v0111PlaylistFilter => _ru ? 'Плейлист' : 'Playlist';
  String get v0111AllPlaylists => _ru ? 'Все плейлисты' : 'All playlists';

  String get v0111UnavailableSection =>
      _ru ? 'Недоступные в Яндекс Музыке' : 'Unavailable in Yandex Music';
  String get v0111RecoveryAll => _ru ? 'Все' : 'All';
  String get v0111RecoveryRecoverable =>
      _ru ? 'Можно восстановить' : 'Recoverable';
  String get v0111RecoveryMissingLocal =>
      _ru ? 'Нет локального файла' : 'No local file';
  String get v0111RecoveryNeedsReview =>
      _ru ? 'Требует проверки' : 'Needs review';
  String get v0111YandexUnavailable =>
      _ru ? 'Яндекс: недоступен' : 'Yandex: unavailable';
  String get v0111YandexUnknown =>
      _ru ? 'Яндекс: требует проверки' : 'Yandex: needs review';
  String get v0111LocalFound =>
      _ru ? 'Локальная копия: найдена' : 'Local copy: found';
  String get v0111LocalMissing =>
      _ru ? 'Локальная копия: нет' : 'Local copy: missing';
  String get v0111ReadyToRestore =>
      _ru ? 'Готов к восстановлению' : 'Ready to restore';
  String get v0111NeedsLocalFile =>
      _ru ? 'Требуется локальный файл' : 'Local file required';
  String get v0111SourcePlaylists => _ru ? 'Был в' : 'Was in';

  String get v0111DownloadToLocal =>
      _ru ? 'Скачать локально' : 'Download locally';
  String get v0111UploadToYandexGroup =>
      _ru ? 'Загрузить в Яндекс' : 'Upload to Yandex';
  String get v0111NeedsDecision => _ru ? 'Требует решения' : 'Needs decision';
  String get v0111UnavailableTracks =>
      _ru ? 'Недоступны в Яндекс Музыке' : 'Unavailable in Yandex Music';
  String get v0111Recoverable =>
      _ru ? 'Готовы к восстановлению' : 'Ready to recover';
  String get v0111CensoredTracks => _ru ? 'Цензурированные' : 'Censored';
  String get v0111ReadyToUpload =>
      _ru ? 'Готовы к загрузке' : 'Ready to upload';
  String v0111ConfirmDownloads(int count) => _ru
      ? 'Будет поставлено в загрузку с Яндекс Музыки: $count'
      : 'Will be queued for download from Yandex Music: $count';
  String v0111ConfirmUploads(int count) => _ru
      ? 'Будет загружено в Яндекс Музыку: $count'
      : 'Will be uploaded to Yandex Music: $count';
  String v0111ConfirmRole(String role, int count) => '$role: $count';
  String get v0111SyncRights => _ru
      ? 'Локальные аудиофайлы будут загружены в Яндекс Музыку как пользовательские треки. Я подтверждаю, что имею право их загружать.'
      : 'Local audio files will be uploaded to Yandex Music as user-uploaded tracks. I confirm that I have the right to upload them.';
  String get v0111UploadOnlyFolderHint => _ru
      ? 'Для этого плана локальная папка загрузок не требуется.'
      : 'This plan does not require a local download folder.';
}
