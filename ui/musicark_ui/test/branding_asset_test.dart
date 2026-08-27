import 'dart:ui' as ui;

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('MusicArk branding asset loads and decodes', (tester) async {
    final data = await rootBundle.load(
      'assets/branding/musicark_app_icon.png',
    );
    expect(data.lengthInBytes, greaterThan(0));

    final bytes = data.buffer.asUint8List(
      data.offsetInBytes,
      data.lengthInBytes,
    );
    final codec = await ui.instantiateImageCodec(bytes);
    final frame = await codec.getNextFrame();

    expect(frame.image.width, greaterThanOrEqualTo(256));
    expect(frame.image.height, greaterThanOrEqualTo(256));

    frame.image.dispose();
    codec.dispose();
  });
}
