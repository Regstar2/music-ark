class AppStrings {
  const AppStrings._();

  static const appTitle = 'MusicArk';
  static const yandexMusic = 'Яндекс Музыка';
  static const loginTitle = 'Вход в Яндекс Музыку';
  static const loginDescription =
      'Введите OAuth-токен один раз. После успешного входа MusicArk сохранит его в системном хранилище учётных данных Windows.';
  static const tokenLabel = 'Yandex Music token';
  static const signIn = 'Войти';
  static const signingIn = 'Вход...';
  static const tokenRequired = 'Введите токен.';
  static const likedTracks = 'Мне нравится';
  static const playlists = 'Плейлисты';
  static const refresh = 'Обновить';
  static const refreshLibrary = 'Обновить библиотеку';
  static const logout = 'Выйти';
  static const search = 'Поиск по трекам, исполнителям и альбомам';
  static const playlistSearch = 'Поиск по плейлистам';
  static const sort = 'Сортировка';
  static const sortOriginal = 'Порядок Яндекса';
  static const sortTitle = 'По названию';
  static const sortArtist = 'По исполнителю';
  static const emptyLikes = 'В «Мне нравится» нет доступных треков.';
  static const emptyPlaylist = 'В этом плейлисте нет доступных треков.';
  static const emptyPlaylists = 'Плейлисты не найдены.';
  static const noSearchResults = 'По вашему запросу ничего не найдено.';
  static const unknownArtist = 'Неизвестный исполнитель';
  static const unknownTitle = 'Без названия';
  static const unknownPlaylist = 'Без названия';
  static const cacheSource = 'Локальный кэш';
  static const networkSource = 'Яндекс Музыка';
  static const noneSource = 'Нет данных';
  static const neverUpdated = 'ещё не обновлялось';
  static const refreshing = 'Обновление библиотеки...';
  static const tokenMissing =
      'Сохранённый токен не найден. Войдите в Яндекс Музыку снова.';
  static const authenticationFailed =
      'Не удалось подтвердить сохранённую сессию. Повторите запрос или выйдите и введите токен снова.';
  static const yandexRequestFailed =
      'Не удалось обновить данные из Яндекс Музыки. Показана сохранённая версия.';
  static const credentialStoreFailed =
      'Не удалось использовать защищённое системное хранилище токена.';
  static const cacheFailed = 'Не удалось прочитать или обновить локальный кэш библиотеки.';
  static const invalidRequest = 'Некорректный запрос к локальному bridge.';
  static const unexpectedError =
      'Не удалось выполнить операцию. Техническая причина показана ниже.';
  static const pythonNotFound =
      'Python не найден. Установите Python 3.10+ или задайте MUSICARK_PYTHON.';
  static const repoRootNotFound =
      'Не найден корень репозитория MusicArk. Запускайте сборку из каталога репозитория или задайте MUSICARK_REPO_ROOT.';

  static const variantReasonSemanticMarkerMismatch =
      'Метки версии трека в Яндекс Музыке и локальном файле отличаются.';
  static const variantReasonStrongVersionMarkerMismatch =
      'Обнаружены признаки другой версии трека.';
  static const variantReasonExplicitMetadataMismatch =
      'Метка explicit в источниках отличается.';
  static const variantReasonSignificantDurationDifference =
      'Длительность версий заметно отличается.';
  static const variantReasonAudioEvidenceRequiredForCensorship =
      'Для проверки версии с цензурой требуется сравнение аудио.';
  static const variantReasonAudioEvidenceMissing =
      'Для уверенного вывода не хватает аудиосравнения.';
  static const variantReasonMetadataVariantMismatchRequiresAudio =
      'Метаданные указывают на различия версии; требуется аудиосравнение.';
  static const variantReasonReferenceAudioMissing =
      'Эталонная версия трека пока недоступна.';
  static const variantReasonAudioDecoderUnavailable =
      'Аудиосравнение сейчас недоступно.';
  static const variantReasonAudioNotChecked = 'Аудио ещё не проверено.';
  static const variantReasonDecodedAudioConsistent =
      'Аудиозаписи совпадают по всей доступной длительности.';
  static const variantReasonLocalizedAudioDifferences =
      'Обнаружены локальные отличия в аудио.';
  static const variantReasonPossibleCleanOrCensored =
      'Возможна версия с цензурой или без цензуры.';
  static const variantReasonDistributedAudioDifferences =
      'Отличия распределены по значительной части записи.';
  static const variantReasonSignalsNearBoundary =
      'Результат находится близко к границе классификации.';
  static const variantReasonReferenceDownloadFailed =
      'Не удалось получить эталонную версию трека.';
  static const variantReasonDecodeError = 'Не удалось декодировать аудиофайл.';
  static const variantReasonLocalFileMissing = 'Локальный аудиофайл не найден.';
  static const variantReasonReferenceFileMissing = 'Эталонный аудиофайл не найден.';
  static const variantReasonAlignmentFailed = 'Не удалось выровнять аудиозаписи.';
  static const variantReasonAudioTooShort = 'Аудиофрагмент слишком короткий для проверки.';
  static const variantReasonInsufficientOverlap =
      'Недостаточно общего аудиофрагмента для сравнения.';
  static const variantReasonNoComparisonWindows =
      'Не удалось получить участки для аудиосравнения.';
  static const variantReasonPermissionError =
      'Нет доступа к одному из аудиофайлов.';
  static const variantReasonUnknown = 'Дополнительный сигнал анализа.';

  static String trackCount(int count) => '$count треков';
  static String playlistCount(int count) => '$count плейлистов';
  static String filteredCount(int shown, int total) => '$shown из $total';
  static String lastUpdated(String value) => 'Последнее обновление: $value';
  static String syncDiff(int added, int removed) => 'Обновлено: +$added / -$removed';
  static String externalId(String value) => 'ID: $value';

  static String variantReason(String code) => switch (code) {
        'semantic_variant_marker_mismatch' => variantReasonSemanticMarkerMismatch,
        'strong_version_marker_mismatch' => variantReasonStrongVersionMarkerMismatch,
        'explicit_metadata_mismatch' => variantReasonExplicitMetadataMismatch,
        'significant_duration_difference' => variantReasonSignificantDurationDifference,
        'audio_evidence_required_for_censorship' =>
          variantReasonAudioEvidenceRequiredForCensorship,
        'audio_evidence_missing' => variantReasonAudioEvidenceMissing,
        'metadata_variant_mismatch_requires_audio' =>
          variantReasonMetadataVariantMismatchRequiresAudio,
        'reference_audio_missing' => variantReasonReferenceAudioMissing,
        'audio_decoder_unavailable' => variantReasonAudioDecoderUnavailable,
        'audio_not_checked' => variantReasonAudioNotChecked,
        'decoded_audio_consistent' => variantReasonDecodedAudioConsistent,
        'localized_audio_differences' => variantReasonLocalizedAudioDifferences,
        'possible_clean_or_censored_variant' => variantReasonPossibleCleanOrCensored,
        'distributed_audio_differences' => variantReasonDistributedAudioDifferences,
        'signals_near_classification_boundary' => variantReasonSignalsNearBoundary,
        'reference_download_failed' => variantReasonReferenceDownloadFailed,
        'decode_error' => variantReasonDecodeError,
        'local_file_missing' => variantReasonLocalFileMissing,
        'reference_file_missing' => variantReasonReferenceFileMissing,
        'alignment_failed' => variantReasonAlignmentFailed,
        'audio_too_short' => variantReasonAudioTooShort,
        'insufficient_aligned_overlap' => variantReasonInsufficientOverlap,
        'no_comparison_windows' => variantReasonNoComparisonWindows,
        'permission_error' => variantReasonPermissionError,
        _ => variantReasonUnknown,
      };
}
