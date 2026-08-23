import 'dart:async';

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

  testWidgets('Coverage exposes progress while select-all and bulk Wanted are pending', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final coverage = _BlockingLargeCoverageBridge(5201);

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
    await tester.pump();
    await coverage.selectPageStarted.future;
    await tester.pump();
    expect(find.byKey(const Key('coverage-select-all-progress')), findsOneWidget);

    coverage.releaseSelectPage.complete();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('coverage-bulk-bar')), findsOneWidget);

    await tester.tap(find.byKey(const Key('coverage-bulk-wanted')));
    await tester.pump();
    await coverage.bulkActionStarted.future;
    await tester.pump();
    expect(find.byKey(const Key('coverage-bulk-progress')), findsOneWidget);

    coverage.releaseBulkAction.complete();
    await tester.pumpAndSettle();
    expect(coverage.bulkSizes, [1000, 1000, 1000, 1000, 1000, 201]);
  });

  testWidgets('Downloads loads Wanted count before the Wanted tab is opened', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final coverage = _FixedWantedCoverageBridge(5247);

    await tester.pumpWidget(
      localized(
        DownloadPage(
          bridge: FakeDownloadBridge(),
          coverageBridge: coverage,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('5247'), findsWidgets);
    expect(coverage.wantedCalls, greaterThan(0));
  });

  testWidgets('Download All shows operation progress before the worker finishes', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final coverage = _FixedWantedCoverageBridge(5247);
    final downloads = _BlockingDownloadBridge();

    await tester.pumpWidget(
      localized(
        DownloadPage(
          bridge: downloads,
          coverageBridge: coverage,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.textContaining('Нужные').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('downloads-wanted-download-all')));
    await tester.pump();
    await downloads.firstStarted.future;
    await tester.pump();

    expect(downloads.enqueueWantedCalls, 1);
    expect(
      downloads.items.any((item) => '${item['id']}'.startsWith('wanted-')),
      isTrue,
    );
    expect(find.byKey(const Key('downloads-operation-progress')), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const Key('downloads-wanted-download-all')),
        matching: find.byType(CircularProgressIndicator),
      ),
      findsOneWidget,
    );

    downloads.releaseFirst.complete();
    await tester.pumpAndSettle();
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

class _BlockingLargeCoverageBridge extends _LargeCoverageBridge {
  _BlockingLargeCoverageBridge(super.count);

  final selectPageStarted = Completer<void>();
  final releaseSelectPage = Completer<void>();
  final bulkActionStarted = Completer<void>();
  final releaseBulkAction = Completer<void>();
  bool _selectBlocked = false;
  bool _bulkBlocked = false;

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
    if (limit == 2000 && !_selectBlocked) {
      _selectBlocked = true;
      selectPageStarted.complete();
      await releaseSelectPage.future;
    }
    return super.coverageTracks(
      limit: limit,
      offset: offset,
      status: status,
      collectionId: collectionId,
      search: search,
      sort: sort,
      userAction: userAction,
      variantStatus: variantStatus,
    );
  }

  @override
  Future<Map<String, dynamic>> coverageSetActions(
    List<String> externalIds,
    String action,
  ) async {
    if (!_bulkBlocked) {
      _bulkBlocked = true;
      bulkActionStarted.complete();
      await releaseBulkAction.future;
    }
    return super.coverageSetActions(externalIds, action);
  }
}

class _FixedWantedCoverageBridge implements CoverageBridgeClient {
  _FixedWantedCoverageBridge(this.count);

  final int count;
  int wantedCalls = 0;

  List<Map<String, dynamic>> get items => List.generate(
        count < 3 ? count : 3,
        (index) => <String, dynamic>{
          'providerId': 'yandex_music',
          'externalId': '${9000000 + index}',
          'provider': {
            'title': 'Wanted $index',
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
        },
      );

  @override
  Future<Map<String, dynamic>> coverageSummary({String collectionId = ''}) async => {
        'total': count,
        'covered': 0,
        'missing': count,
        'needsReview': 0,
        'notAnalyzed': 0,
        'coveragePercent': 0.0,
        'matchingAnalyzedPercent': 100.0,
        'variantVerification': const {},
        'missingActions': {'wanted': count, 'ignored': 0, 'unreviewed': 0},
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
    return {
      'count': userAction == 'wanted' ? count : 0,
      'limit': limit,
      'offset': offset,
      'items': userAction == 'wanted' ? items : const <Map<String, dynamic>>[],
    };
  }

  @override
  Future<Map<String, dynamic>> coverageTrack(String externalId) async => {'track': items.first};

  @override
  Future<Map<String, dynamic>> coverageSetAction(String externalId, String action) async => {};

  @override
  Future<Map<String, dynamic>> coverageSetActions(List<String> externalIds, String action) async => {};
}

class _BlockingDownloadBridge extends FakeDownloadBridge {
  final firstStarted = Completer<void>();
  final releaseFirst = Completer<void>();
  bool _blocked = false;

  @override
  Future<Map<String, dynamic>> runTask(String taskId) async {
    if (!_blocked) {
      _blocked = true;
      firstStarted.complete();
      await releaseFirst.future;
    }
    return super.runTask(taskId);
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
