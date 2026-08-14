class AppStrings {
  const AppStrings._();

  static const appTitle = 'MusicArk';
  static const loginTitle = 'Вход в Яндекс Музыку';
  static const loginDescription =
      'Введите OAuth-токен Яндекс Музыки. Токен передаётся Python-процессу через окружение и не сохраняется MusicArk.';
  static const tokenLabel = 'Yandex Music token';
  static const signIn = 'Войти';
  static const signingIn = 'Вход...';
  static const tokenRequired = 'Введите токен.';
  static const likedTracks = 'Мне нравится';
  static const refresh = 'Обновить';
  static const logout = 'Выйти';
  static const emptyLikes = 'В «Мне нравится» нет доступных треков.';
  static const unknownArtist = 'Неизвестный исполнитель';
  static const unknownTitle = 'Без названия';
  static const tokenMissing =
      'Токен не передан приложению. Введите токен ещё раз.';
  static const authenticationFailed =
      'Яндекс отклонил токен. Проверьте токен и попробуйте снова.';
  static const yandexRequestFailed =
      'Не удалось получить данные из Яндекс Музыки. Проверьте соединение и повторите запрос.';
  static const unexpectedError =
      'Не удалось выполнить операцию. Техническая причина показана ниже.';
  static const pythonNotFound =
      'Python не найден. Установите Python 3.10+ или задайте MUSICARK_PYTHON.';
  static String trackCount(int count) => '$count треков';

  static const repoRootNotFound =
      'Не найден корень репозитория MusicArk. Запускайте сборку из каталога репозитория или задайте MUSICARK_REPO_ROOT.';
}
