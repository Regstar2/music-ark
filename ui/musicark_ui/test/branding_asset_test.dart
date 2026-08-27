import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('MusicArk branding asset is a standard RGB PNG', () async {
    final data = await rootBundle.load(
      'assets/branding/musicark_app_icon.png',
    );
    expect(data.lengthInBytes, greaterThan(32));

    final bytes = data.buffer.asUint8List(
      data.offsetInBytes,
      data.lengthInBytes,
    );
    expect(
      bytes.sublist(0, 8),
      equals(const [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
    );

    expect(data.getUint32(16), greaterThanOrEqualTo(256));
    expect(data.getUint32(20), greaterThanOrEqualTo(256));
    expect(data.getUint8(25), equals(2)); // PNG truecolor/RGB.
  });
}
