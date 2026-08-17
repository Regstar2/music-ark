import 'package:flutter/material.dart';

/// Lightweight vector mark used by the desktop shell.
///
/// It is intentionally painted with theme colors so no external SVG package or
/// asset pipeline is required for a single brand glyph.
class MusicArkMark extends StatelessWidget {
  const MusicArkMark({super.key, this.size = 32});

  final double size;

  @override
  Widget build(BuildContext context) => CustomPaint(
        key: const Key('musicark-mark'),
        size: Size.square(size),
        painter: _MusicArkMarkPainter(
          background: Theme.of(context).colorScheme.primary,
          foreground: Theme.of(context).colorScheme.onPrimary,
        ),
      );
}

class _MusicArkMarkPainter extends CustomPainter {
  const _MusicArkMarkPainter({required this.background, required this.foreground});

  final Color background;
  final Color foreground;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, Radius.circular(size.width * .25)),
      Paint()..color = background,
    );

    final stroke = Paint()
      ..color = foreground
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = size.width * .07;

    final arch = Path()
      ..moveTo(size.width * .20, size.height * .60)
      ..cubicTo(
        size.width * .32,
        size.height * .39,
        size.width * .42,
        size.height * .34,
        size.width * .50,
        size.height * .34,
      )
      ..cubicTo(
        size.width * .58,
        size.height * .34,
        size.width * .68,
        size.height * .39,
        size.width * .80,
        size.height * .60,
      );
    canvas.drawPath(arch, stroke);

    final wave = Path()
      ..moveTo(size.width * .25, size.height * .55)
      ..lineTo(size.width * .37, size.height * .45)
      ..lineTo(size.width * .50, size.height * .58)
      ..lineTo(size.width * .64, size.height * .42)
      ..lineTo(size.width * .76, size.height * .54);
    canvas.drawPath(wave, stroke..strokeWidth = size.width * .055);

    final hull = Path()
      ..moveTo(size.width * .27, size.height * .68)
      ..cubicTo(
        size.width * .40,
        size.height * .75,
        size.width * .60,
        size.height * .75,
        size.width * .73,
        size.height * .68,
      );
    canvas.drawPath(hull, stroke..strokeWidth = size.width * .05);
  }

  @override
  bool shouldRepaint(covariant _MusicArkMarkPainter oldDelegate) =>
      oldDelegate.background != background || oldDelegate.foreground != foreground;
}
