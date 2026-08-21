import 'dart:convert';

import 'package:flutter/material.dart';

import 'musicark_icon_data.dart';

/// Shared MusicArk brand mark used by the desktop shell.
///
/// The Windows executable still uses the tracked ICO resource. The small
/// in-app mark is decoded from embedded PNG bytes so it cannot break because
/// of a stale/missing Flutter asset manifest.
class MusicArkMark extends StatelessWidget {
  const MusicArkMark({super.key, this.size = 32});

  final double size;

  static final _iconBytes = base64Decode(musicArkAppIconPngBase64);

  @override
  Widget build(BuildContext context) => SizedBox.square(
        key: const Key('musicark-mark'),
        dimension: size,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(size * .22),
          child: Image.memory(
            _iconBytes,
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
