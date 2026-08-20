import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/l10n/app_localizations.dart';
import 'package:musicark_ui/yandex_upload_bridge.dart';
import 'package:musicark_ui/yandex_upload_dialog.dart';

Map<String, dynamic> _mp3Track() => {
  'id': 77,
  'path': r'C:\Music\Private\Artist - Track.mp3',
  'fileName': 'Artist - Track.mp3',
  'title': 'Track',
  'artists': ['Artist'],
  'extension': '.mp3',
  'codec': 'mp3',
  'fileSize': 4 * 1024 * 1024,
};

YandexUploadResult _result(YandexUploadStatus status) => YandexUploadResult(
  status: status,
  localFileId: 77,
  playlistKind: '7',
  trackId: 'ugc-1',
  readBackVerified: status == YandexUploadStatus.verified,
  readBackAttempts: 1,
  safeMessage: status.name,
);

class _DelayedBridge implements YandexUploadBridgeClient {
  final completer = Completer<YandexUploadResult>();
  int calls = 0;

  @override
  Future<YandexUploadTargets> targets() async => const YandexUploadTargets(
    authenticated: true,
    playlists: [
      YandexUploadTarget(
        playlistKind: '7',
        title: 'My playlist',
        trackCount: 4,
      ),
    ],
  );

  @override
  Future<YandexUploadResult> uploadTrack({
    required int localFileId,
    required String playlistKind,
    required bool confirm,
    required bool rightsConfirmed,
  }) {
    calls++;
    return completer.future;
  }
}

void main() {
  Future<void> pumpDialog(
    WidgetTester tester, {
    Locale locale = const Locale('en'),
    required YandexUploadBridgeClient bridge,
    Map<String, dynamic>? track,
  }) async {
    await tester.binding.setSurfaceSize(const Size(900, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        locale: locale,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Builder(
          builder: (context) => Scaffold(
            body: Center(
              child: FilledButton(
                key: const Key('open-upload'),
                onPressed: () => showYandexUploadDialog(
                  context: context,
                  track: track ?? _mp3Track(),
                  bridge: bridge,
                ),
                child: const Text('open'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.byKey(const Key('open-upload')));
    await tester.pumpAndSettle();
  }

  Future<void> satisfyRequirements(WidgetTester tester) async {
    await tester.tap(find.byKey(const Key('yandex-upload-playlist')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('My playlist').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('yandex-upload-rights')));
    await tester.pumpAndSettle();
  }

  testWidgets('playlist and rights confirmation are required', (tester) async {
    final bridge = FakeYandexUploadBridge(
      playlists: const [
        YandexUploadTarget(
          playlistKind: '7',
          title: 'My playlist',
          trackCount: 4,
        ),
      ],
    );
    await pumpDialog(tester, bridge: bridge);

    expect(find.byKey(const Key('yandex-upload-dialog')), findsOneWidget);
    final initial = tester.widget<FilledButton>(
      find.byKey(const Key('yandex-upload-submit')),
    );
    expect(initial.onPressed, isNull);

    await tester.tap(find.byKey(const Key('yandex-upload-playlist')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('My playlist').last);
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('yandex-upload-submit')))
          .onPressed,
      isNull,
    );

    await tester.tap(find.byKey(const Key('yandex-upload-rights')));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('yandex-upload-submit')))
          .onPressed,
      isNotNull,
    );
  });

  testWidgets(
    'payload uses local id, playlist kind and explicit confirmations',
    (tester) async {
      final bridge = FakeYandexUploadBridge(
        playlists: const [
          YandexUploadTarget(
            playlistKind: '7',
            title: 'My playlist',
            trackCount: 4,
          ),
        ],
      );
      await pumpDialog(tester, bridge: bridge);
      await satisfyRequirements(tester);
      await tester.tap(find.byKey(const Key('yandex-upload-submit')));
      await tester.pumpAndSettle();

      expect(bridge.submissions, hasLength(1));
      expect(bridge.submissions.single, {
        'local_file_id': 77,
        'playlist_kind': '7',
        'confirm': true,
        'rights_confirmed': true,
      });
      expect(
        bridge.submissions.single.toString(),
        isNot(contains(r'C:\Music')),
      );
      expect(
        find.byKey(const Key('yandex-upload-state-completed')),
        findsOneWidget,
      );
    },
  );

  testWidgets('double submit is impossible while upload is in progress', (
    tester,
  ) async {
    final bridge = _DelayedBridge();
    await pumpDialog(tester, bridge: bridge);
    await satisfyRequirements(tester);
    await tester.tap(find.byKey(const Key('yandex-upload-submit')));
    await tester.pump();

    expect(bridge.calls, 1);
    expect(
      find.byKey(const Key('yandex-upload-state-uploading')),
      findsOneWidget,
    );
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('yandex-upload-submit')))
          .onPressed,
      isNull,
    );

    bridge.completer.complete(_result(YandexUploadStatus.verified));
    await tester.pumpAndSettle();
    expect(bridge.calls, 1);
  });

  testWidgets('processing is distinct from completed', (tester) async {
    final bridge = FakeYandexUploadBridge(
      playlists: const [
        YandexUploadTarget(
          playlistKind: '7',
          title: 'My playlist',
          trackCount: 0,
        ),
      ],
      nextResult: _result(YandexUploadStatus.processing),
    );
    await pumpDialog(tester, bridge: bridge);
    await satisfyRequirements(tester);
    await tester.tap(find.byKey(const Key('yandex-upload-submit')));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('yandex-upload-state-processing')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('yandex-upload-state-completed')),
      findsNothing,
    );
  });

  testWidgets('delivery unknown has its own state', (tester) async {
    final bridge = FakeYandexUploadBridge(
      playlists: const [
        YandexUploadTarget(
          playlistKind: '7',
          title: 'My playlist',
          trackCount: 0,
        ),
      ],
      nextResult: _result(YandexUploadStatus.deliveryUnknown),
    );
    await pumpDialog(tester, bridge: bridge);
    await satisfyRequirements(tester);
    await tester.tap(find.byKey(const Key('yandex-upload-submit')));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('yandex-upload-state-delivery-unknown')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('yandex-upload-state-error')), findsNothing);
  });

  testWidgets('stage2 HTTP failure exposes only safe technical diagnostics', (
    tester,
  ) async {
    final bridge = FakeYandexUploadBridge(
      playlists: const [
        YandexUploadTarget(
          playlistKind: '7',
          title: 'My playlist',
          trackCount: 0,
        ),
      ],
      nextResult: const YandexUploadResult(
        status: YandexUploadStatus.stage2HttpFailed,
        localFileId: 77,
        playlistKind: '7',
        trackId: 'ugc-1',
        stage1HttpStatus: 200,
        stage2HttpStatus: 503,
        readBackVerified: false,
        readBackAttempts: 3,
        errorCode: 'stage2_http_failed',
        safeMessage: 'safe',
      ),
    );
    await pumpDialog(tester, bridge: bridge);
    await satisfyRequirements(tester);
    await tester.tap(find.byKey(const Key('yandex-upload-submit')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('yandex-upload-state-error')), findsOneWidget);
    expect(find.textContaining('Stage 1 HTTP 200'), findsOneWidget);
    expect(find.textContaining('Stage 2 HTTP 503'), findsOneWidget);
    expect(find.textContaining('Code: stage2_http_failed'), findsOneWidget);
    expect(find.textContaining('Read-back: 3'), findsOneWidget);
    expect(find.textContaining('token='), findsNothing);
    expect(find.textContaining('yandex.net/'), findsNothing);
  });

  testWidgets('unsupported format is fail closed in UI', (tester) async {
    final track = _mp3Track()
      ..['path'] = r'C:\Music\track.flac'
      ..['fileName'] = 'track.flac'
      ..['extension'] = '.flac'
      ..['codec'] = 'flac';
    final bridge = FakeYandexUploadBridge(
      playlists: const [
        YandexUploadTarget(
          playlistKind: '7',
          title: 'My playlist',
          trackCount: 0,
        ),
      ],
    );
    await pumpDialog(tester, bridge: bridge, track: track);
    expect(find.byKey(const Key('yandex-upload-mp3-only')), findsOneWidget);
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('yandex-upload-submit')))
          .onPressed,
      isNull,
    );
    expect(bridge.submissions, isEmpty);
  });

  testWidgets('auth required and no-playlist states block upload', (
    tester,
  ) async {
    await pumpDialog(
      tester,
      bridge: FakeYandexUploadBridge(authenticated: false, playlists: const []),
    );
    expect(
      find.byKey(const Key('yandex-upload-auth-required')),
      findsOneWidget,
    );
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('yandex-upload-submit')))
          .onPressed,
      isNull,
    );
  });

  testWidgets('rights text exists in English and Russian localizations', (
    tester,
  ) async {
    final bridge = FakeYandexUploadBridge(
      playlists: const [
        YandexUploadTarget(
          playlistKind: '7',
          title: 'My playlist',
          trackCount: 0,
        ),
      ],
    );
    await pumpDialog(tester, bridge: bridge, locale: const Locale('en'));
    expect(
      find.text('I confirm that I have the right to upload this audio file.'),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('yandex-upload-close')));
    await tester.pumpAndSettle();

    await pumpDialog(tester, bridge: bridge, locale: const Locale('ru'));
    expect(
      find.text('Я подтверждаю, что имею право загружать этот аудиофайл.'),
      findsOneWidget,
    );
  });
}
