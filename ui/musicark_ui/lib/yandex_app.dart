import 'package:flutter/widgets.dart';
import 'package:media_kit/media_kit.dart';

import 'yandex_workspace.dart';
export 'yandex_workspace.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  MediaKit.ensureInitialized();
  runApp(const MusicArkDesktopApp());
}
