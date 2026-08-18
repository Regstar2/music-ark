part of 'matching_workspace_page.dart';

List<Map<String, dynamic>> _ensureVariantRows(List<Map<String, dynamic>> rows) {
  return rows.map((row) {
    final copy = Map<String, dynamic>.from(row);
    if ('${copy['status'] ?? ''}' == 'matched' &&
        copy['localFileId'] != null &&
        copy['variant'] is! Map) {
      copy['variant'] = {
        'variantStatus': 'not_checked',
        'status': 'not_checked',
        'variantReasons': ['audio_not_checked'],
        'alteredSegments': <Map<String, dynamic>>[],
      };
    }
    return copy;
  }).toList();
}

List<Map<String, dynamic>> _mapItems(dynamic value) {
  if (value is! List) return <Map<String, dynamic>>[];
  return value
      .whereType<Map>()
      .map((item) => Map<String, dynamic>.from(item))
      .toList();
}

Map<String, dynamic> _asMap(dynamic value) {
  if (value is Map) return Map<String, dynamic>.from(value);
  return <String, dynamic>{};
}

int _asInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse('$value') ?? 0;
}

double _asDouble(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse('$value') ?? 0.0;
}

String _artistText(dynamic value, String fallback) {
  if (value is List && value.isNotEmpty) {
    final result = value
        .map((item) => '$item'.trim())
        .where((item) => item.isNotEmpty)
        .join(', ');
    if (result.isNotEmpty) return result;
  }
  final text = '$value'.trim();
  if (value is! List && text.isNotEmpty && text != 'null') return text;
  return fallback;
}

String _matchingStatusLabel(AppLocalizations l10n, String status) => switch (status) {
      'matched' => l10n.matchingStatusMatched,
      'conflict' => l10n.matchingStatusConflict,
      'unmatched' => l10n.matchingStatusUnmatched,
      _ => l10n.matchingStatusUnknown,
    };

String _variantLabel(AppLocalizations l10n, String status) => switch (status) {
      'same' => l10n.matchingVariantSame,
      'altered' => l10n.matchingVariantAltered,
      'different_version' => l10n.matchingVariantDifferent,
      'uncertain' => l10n.matchingVariantUncertain,
      _ => l10n.matchingVariantNotChecked,
    };

_BadgeTone _matchingTone(String status) => switch (status) {
      'matched' => _BadgeTone.matched,
      'conflict' => _BadgeTone.conflict,
      'unmatched' => _BadgeTone.unmatched,
      _ => _BadgeTone.neutral,
    };

_BadgeTone _variantTone(String status) => switch (status) {
      'same' => _BadgeTone.same,
      'altered' => _BadgeTone.altered,
      'different_version' => _BadgeTone.different,
      _ => _BadgeTone.neutral,
    };

String _errorText(Object error) {
  if (error is MatchingBridgeException) return error.message;
  if (error is MusicArkBridgeException) return error.message;
  return error.toString();
}
