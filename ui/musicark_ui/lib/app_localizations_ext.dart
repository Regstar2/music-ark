import 'package:flutter/widgets.dart';

import 'l10n/app_localizations.dart';

extension MusicArkLocalizations on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this)!;
}

extension MusicArkLocalizationAliases on AppLocalizations {
  String get yandexFavoriteAlbumsTitle => yandexAlbumsTab;
}
