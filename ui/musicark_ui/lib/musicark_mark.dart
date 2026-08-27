import 'package:flutter/material.dart';

/// Shared MusicArk brand mark used by the desktop shell.
///
/// The in-app mark and the Windows executable are both derived from the
/// tracked branding asset/resource rather than maintaining a second embedded
/// copy of the artwork in Dart source.
class MusicArkMark extends StatelessWidget {
  const MusicArkMark({super.key, this.size = 32});

  final double size;

  @override
  Widget build(BuildContext context) => SizedBox.square(
        key: const Key('musicark-mark'),
        dimension: size,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(size * .22),
          child: Image.asset(
            'assets/branding/musicark_app_icon.png',
            width: size,
            height: size,
            fit: BoxFit.contain,
            filterQuality: FilterQuality.high,
            gaplessPlayback: true,
            excludeFromSemantics: true,
            errorBuilder: (context, error, stackTrace) => ColoredBox(
              color: Theme.of(context).colorScheme.primary,
              child: Icon(
                Icons.music_note_rounded,
                size: size * .58,
                color: Theme.of(context).colorScheme.onPrimary,
              ),
            ),
          ),
        ),
      );
}
