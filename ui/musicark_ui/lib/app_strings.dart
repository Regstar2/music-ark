class AppStrings {
  const AppStrings._();

  static const appTitle = 'MusicArk';
  static const loginTitle = 'Вход в Яндекс Музыку';
  static const loginDescription =
      'Введите OAuth-токен один раз. После успешного входа MusicArk сохранит его в системном хранилище учётных данных Windows.';
  static const tokenLabel = 'Yandex Music token';
  static const signIn = 'Войти';
  static const signingIn = 'Вход...';
  static const tokenRequired = 'Введите токен.';
  static const likedTracks = 'Мне нравится';
  static const refresh = 'Обновить';
  static const logout = 'Выйти';
  static const search = 'Поиск по трекам, исполнителям и альбомам';
  static const sort = 'Сортировка';
  static const sortOriginal = 'Порядок Яндекса';
  static const sortTitle = 'По названию';
  static const sortArtist = 'По исполнителю';
  static const emptyLikes = 'В «Мне нравится» нет доступных треков.';
  static const noSearchResults = 'По вашему запросу ничего не найдено.';
  static const unknownArtist = 'Неизвестный исполнитель';
  static const unknownTitle = 'Без названия';
  static const cacheSource = 'Локальный кэш';
  static const networkSource = 'Яндекс Музыка';
  static const neverUpdated = 'ещё не обновлялось';
  static const refreshing = 'Обновление библиотеки...';
  static const tokenMissing =
      'Сохранённый токен не найден. Войдите в Яндекс Музыку снова.';
  static const authenticationFailed =
      'Не удалось подтвердить сохранённую сессию. Повторите запрос или выйдите и введите токен снова.';
  static const yandexRequestFailed =
      'Не удалось обновить данные из Яндекс Музыки. Сохранённая библиотека остаётся доступна.';
  static const credentialStoreFailed =
      'Не удалось использовать защищённое системное хранилище токена.';
  static const cacheFailed = 'Не удалось прочитать или обновить локальный кэш библиотеки.';
  static const unexpectedError =
      'Не удалось выполнить операцию. Техническая причина показана ниже.';
  static const pythonNotFound =
      'Python не найден. Установите Python 3.10+ или задайте MUSICARK_PYTHON.';
  static const repoRootNotFound =
      'Не найден корень репозитория MusicArk. Запускайте сборку из каталога репозитория или задайте MUSICARK_REPO_ROOT.';

  static String trackCount(int count) => '$count треков';
  static String filteredCount(int shown, int total) => '$shown из $total треков';
  static String lastUpdated(String value) => 'Последнее обновление: $value';
  static String syncDiff(int added, int removed) =>
      'Обновлено: +$added / -$removed';
}
