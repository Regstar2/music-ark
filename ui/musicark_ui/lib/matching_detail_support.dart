part of 'matching_detail_dialog.dart';

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

String _duration(dynamic value) {
  final seconds = double.tryParse('$value');
  if (seconds == null || seconds < 0) return '—';
  return '${seconds.toStringAsFixed(seconds == seconds.roundToDouble() ? 0 : 3)} с';
}

String _formatSeconds(double seconds) {
  final safe = seconds.isFinite && seconds >= 0 ? seconds.round() : 0;
  final minutes = safe ~/ 60;
  final remainder = safe % 60;
  return '$minutes:${remainder.toString().padLeft(2, '0')}';
}

String _errorText(Object error) {
  if (error is MatchingBridgeException) return error.message;
  if (error is MusicArkBridgeException) return error.message;
  return error.toString();
}
