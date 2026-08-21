import 'package:flutter/material.dart';

/// Shared MusicArk brand mark used by the desktop shell.
///
/// The same artwork is used for the Windows executable icon and the in-app
/// sidebar brand, so the application keeps one consistent visual identity.
class MusicArkMark extends StatelessWidget {
  const MusicArkMark({super.key, this.size = 32});

  final double size;

  @override
  Widget build(BuildContext context) => SizedBox.square(
        key: const Key('musicark-mark'),
        dimension: size,
        child: Image.asset(
          'assets/branding/musicark_app_icon.png',
          width: size,
          height: size,
          fit: BoxFit.contain,
          filterQuality: FilterQuality.high,
          excludeFromSemantics: true,
        ),
      );
}
