import 'package:flutter/material.dart';

/// Small, shared set of desktop presentation constants for MusicArk.
///
/// These values intentionally describe layout and density only. Colors continue
/// to come from [ColorScheme] so light/dark/system themes stay coherent.
class AppUiTokens {
  const AppUiTokens._();

  static const sidebarWidth = 200.0;
  static const pagePadding = 24.0;
  static const sectionGap = 16.0;
  static const compactGap = 8.0;
  static const controlHeight = 48.0;
  static const trackRowHeight = 68.0;
  static const artworkSize = 48.0;
  static const iconSize = 22.0;
  static const radiusSmall = 8.0;
  static const radiusMedium = 12.0;
  static const radiusLarge = 16.0;

  /// Maximum width for Settings, Help and About content on large desktops.
  static const utilityContentMaxWidth = 1180.0;

  /// Utility-page rows keep controls side by side above this content width.
  static const utilityRowWide = 820.0;

  /// About information uses two columns above this content width.
  static const utilityGridWide = 760.0;

  /// Content width where the Yandex toolbar can remain on a single row.
  static const yandexToolbarWide = 900.0;

  /// Content width where album/time columns are shown as a desktop table.
  static const yandexTableWide = 820.0;

  /// Minimum width of the side-by-side Matching comparison table.
  static const matchingTableMinimum = 980.0;

  static BorderRadius get smallRadius => BorderRadius.circular(radiusSmall);
  static BorderRadius get mediumRadius => BorderRadius.circular(radiusMedium);
  static BorderRadius get largeRadius => BorderRadius.circular(radiusLarge);
}
