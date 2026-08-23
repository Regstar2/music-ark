import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/coverage_bridge.dart';
import 'package:musicark_ui/coverage_page.dart';
import 'package:musicark_ui/download_bridge.dart';
import 'package:musicark_ui/download_page.dart';
import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/matching_bridge.dart';

void main() {
  Widget localized(Widget child) => MaterialApp(
        locale: const Locale('ru'),
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(body: child),
      );

  testWidgets('Coverage handles more than 5000 selected tracks in bounded chunks', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final coverage = _LargeCoverageBridge(5201);

    await tester.pumpWidget(
      localized(
        CoveragePage(
          bridge: coverage,
          matchingBridge: FakeMatchingBridge(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('coverage-select-all')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('coverage-bulk-bar')), findsOneWidget);
    expect(coverage.maxRequestedPageSize, 2000);

    await tester.tap(find.byKey(const Key('coverage-bulk-wanted')));
    await tester.pumpAndSettle();

    expect(coverage.bulkSizes, [1000, 1000, 1000, 1000, 1000, 201]);
    expect(coverage.bulkSizes.every((size) => size <= 1000), isTrue);
    expect(find.textContaining('limited to 5000'), findsNothing);
  });

  testWidgets('persistent Downloads page refreshes Wanted when reactivated', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final coverage = _ReactivationCoverageBridge();
    final downloads = FakeDownloadBridge();
    late StateSetter setHostState;
    var active = true;

    await tester.pumpWidget(
      localized(
        StatefulBuilder(
          builder: (context, setState) {
            setHostState = setState;
            return DownloadPage(
              bridge: downloads,
              coverageBridge: coverage,
              active: active,
            );
          },
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.textContaining('Нужные').last);
    await tester.pumpAndSettle();
    final callsBefore = coverage.wantedCalls;
    expect(find.byKey(const ValueKey('downloads-wanted-new')), findsNothing);

    coverage.exposeWanted = true;
    setHostState(() => active = false);
    await tester.pump();
    setHostState(() => active = true);
    await tester.pumpAndSettle();

    expect(coverage.wantedCalls, greaterThan(callsBefore));
    expect(find.byKey(const ValueKey('downloads-wanted-new')), findsOneWidget);
  });
}

class _LargeCoverageBridge implements CoverageBridgeClient {
  _LargeCoverageBridge(int count)
      : items = List.generate(
          count,
          (index) => <String, dynamic>{
            'providerId': 'yandex_music',
            'externalId': '${1000000 + index}',
            'provider': {
              'title': 'Missing $index',
              'artists': ['Artist'],
              'album_title': 'Album',
              'duration_seconds': 180,
            },
            'collections': const [],
            'coverageStatus': 'missing',
            'matchingStatus': 'unmatched',
            'confidence': 0.0,
            'reason': 'no_candidates',
            'variantStatus': null,
            'userAction': 'unreviewed',
            'local': null,
          },
        );

  final List<Map<String, dynamic>> items;
  final List<int> bulkSizes = [];
  int maxRequestedPageSize = 0;

  @override
  Future<Map<String, dynamic>> coverageSummary({String collectionId = ''}) async => {
        'providerId': 'yandex_music',
        'collectionId': collectionId,
        'total': items.length,
        'covered': 0,
        'missing': items.length,
        'needsReview': 0,
        'notAnalyzed': 0,
        'coveragePercent': 0.0,
        'matchingAnalyzedPercent': 100.0,
        'variantVerification': const {
          'same': 0,
          'altered': 0,
          'differentVersion': 0,
          'uncertain': 0,
          'notChecked': 0,
        },
        'missingActions': {
          'wanted': items.where((item) => item['userAction'] == 'wanted').length,
          'ignored': 0,
          'unreviewed': items.where((item) => item['userAction'] == 'unreviewed').length,
        },
      };

  @override
  Future<Map<String, dynamic>> coverageCollections() async => {'items': const []};

  @override
  Future<Map<String, dynamic>> coverageTracks({
    int limit = 100,
    int offset = 0,
    String status = 'missing',
    String collectionId = '',
    String search = '',
    String sort = 'artist',
    String userAction = '',
    String variantStatus = '',
  }) async {
    if (limit > maxRequestedPageSize) maxRequestedPageSize = limit;
    final filtered = items.where((item) {
      if (status.isNotEmpty && item['coverageStatus'] != status) return false;
      if (userAction.isNotEmpty && item['userAction'] != userAction) return false;
      return true;
    }).toList(growable: false);
    final end = (offset + limit) < filtered.length ? offset + limit : filtered.length;
    final page = offset >= filtered.length ? const <Map<String, dynamic>>[] : filtered.sublist(offset, end);
    return {'count': filtered.length, 'limit': limit, 'offset': offset, 'items': page};
  }

  @override
  Future<Map<String, dynamic>> coverageTrack(String externalId) async => {
        'track': items.firstWhere((item) => item['externalId'] == externalId),
        'matching': null,
        'variant': const {'status': null, 'applicable': false},
      };

  @override
  Future<Map<String, dynamic>> coverageSetAction(String externalId, String action) async {
    items.firstWhere((item) => item['externalId'] == externalId)['userAction'] = action;
    return {'externalId': externalId, 'userAction': action};
  }

  @override
  Future<Map<String, dynamic>> coverageSetActions(
    List<String> externalIds,
    String action,
  ) async {
    bulkSizes.add(externalIds.length);
    final ids = externalIds.toSet();
    var updated = 0;
    for (final item in items) {
      if (ids.contains(item['externalId'])) {
        item['userAction'] = action;
        updated++;
      }
    }
    return {'action': action, 'requested': externalIds.length, 'updated': updated};
  }
}

class _ReactivationCoverageBridge implements CoverageBridgeClient {
  bool exposeWanted = false;
  int wantedCalls = 0;

  Map<String, dynamic> get wanted => {
        'providerId': 'yandex_music',
        'externalId': 'new',
        'provider': {
          'title': 'Fresh wanted track',
          'artists': ['Artist'],
          'album_title': 'Album',
        },
        'collections': const [],
        'coverageStatus': 'missing',
        'matchingStatus': 'unmatched',
        'confidence': 0.0,
        'reason': 'no_candidates',
        'variantStatus': null,
        'userAction': 'wanted',
        'local': null,
      };

  @override
  Future<Map<String, dynamic>> coverageSummary({String collectionId = ''}) async => {
        'total': exposeWanted ? 1 : 0,
        'covered': 0,
        'missing': exposeWanted ? 1 : 0,
        'needsReview': 0,
        'notAnalyzed': 0,
        'coveragePercent': 0.0,
        'matchingAnalyzedPercent': 100.0,
        'variantVerification': const {},
        'missingActions': {'wanted': exposeWanted ? 1 : 0, 'ignored': 0, 'unreviewed': 0},
      };

  @override
  Future<Map<String, dynamic>> coverageCollections() async => {'items': const []};

  @override
  Future<Map<String, dynamic>> coverageTracks({
    int limit = 100,
    int offset = 0,
    String status = 'missing',
    String collectionId = '',
    String search = '',
    String sort = 'artist',
    String userAction = '',
    String variantStatus = '',
  }) async {
    if (userAction == 'wanted') wantedCalls++;
    final items = userAction == 'wanted' && exposeWanted ? [wanted] : <Map<String, dynamic>>[];
    return {'count': items.length, 'limit': limit, 'offset': offset, 'items': items};
  }

  @override
  Future<Map<String, dynamic>> coverageTrack(String externalId) async => {'track': wanted};

  @override
  Future<Map<String, dynamic>> coverageSetAction(String externalId, String action) async => {};

  @override
  Future<Map<String, dynamic>> coverageSetActions(List<String> externalIds, String action) async => {};
}
