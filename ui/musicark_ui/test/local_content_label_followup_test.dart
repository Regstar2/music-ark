import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/content_label_bridge.dart';
import 'package:musicark_ui/folder_picker.dart';
import 'package:musicark_ui/local_library_page.dart';
import 'package:musicark_ui/main.dart';

void main() {
  testWidgets('Local Library scans configured roots on every tab activation', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    await bridge.localRootAdd(r'C:\Music');
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(MusicArkDesktopApp(bridge: bridge));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('nav-local-library')));
    await tester.pumpAndSettle();
    expect(bridge.localScanCalls, 1);

    await tester.tap(find.byIcon(Icons.cloud_outlined));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('nav-local-library')));
    await tester.pumpAndSettle();
    expect(bridge.localScanCalls, 2);
  });

  testWidgets('local track ORIGINAL/CENSORED label is visible and editable', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    await bridge.localRootAdd(r'C:\Music');
    final labels = FakeContentLabelBridge()..localLabels[1] = 'original';
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: LocalLibraryPage(
          bridge: bridge,
          folderPicker: FakeLocalFolderPicker(null),
          contentLabelBridge: labels,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('local-content-label-1')), findsOneWidget);
    expect(find.text('ОРИГИНАЛ'), findsOneWidget);
    await tester.tap(find.byKey(const Key('local-content-label-menu-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('ЦЕНЗУРА').last);
    await tester.pumpAndSettle();
    expect(labels.localLabels[1], 'censored');
    expect(find.text('ЦЕНЗУРА'), findsOneWidget);
  });
}
