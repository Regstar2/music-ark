# Third-Party Notices

This file covers third-party components redistributed in the MusicArk v1.0.0
Windows x64 portable ZIP and Inno Setup installer.

MusicArk's own source code is licensed under the MIT License in `LICENSE`.
Third-party components keep their own licenses. The MIT License for MusicArk
does not relicense third-party code, libraries, runtimes, DLLs or bundled tools.

MusicArk integrates with Yandex Music through an unofficial API wrapper. MusicArk
is not an official Yandex product and is not affiliated with Yandex.

## Audit Basis

The redistributed Windows package was audited from the staged runtime produced
by:

```powershell
.\tools\package_windows.ps1 -SkipInstaller -PythonVersion 3.13
```

The actual staged directory was `.build/v015/MusicArk`. It contained:

- `Music Ark.exe`, Flutter data and native Windows plugins;
- `flutter_windows.dll`;
- `file_selector_windows_plugin.dll`;
- `media_kit_libs_windows_audio_plugin.dll`;
- `libmpv-2.dll`;
- `data/flutter_assets/packages/media_kit/assets/web/hls1.4.10.js`;
- frozen CPython/PyInstaller runtime under `.venv/Scripts`;
- `imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe`;
- generated Flutter `data/flutter_assets/NOTICES.Z`.

Package metadata was checked from the staged PyInstaller output, PyInstaller
analysis/PYZ inventory, `pip` package metadata/license files, `pubspec.lock`,
Flutter package cache license files, native DLL version metadata and upstream
project pages where package metadata did not fully describe bundled binaries.

## Distribution Notes

- No modified third-party LGPL/GPL source code is stored in the MusicArk source
  tree.
- `yandex-music`, `mutagen`, FFmpeg and libmpv are redistributed unmodified as
  installed by the packaging process.
- MusicArk invokes FFmpeg as an external executable for local audio processing.
- libmpv is redistributed as a dynamic DLL used by `media_kit`.
- Generated Flutter notices are also present in packaged builds at
  `data/flutter_assets/NOTICES.Z`.
- License texts and source-offer notes are copied to the installation root under
  `licenses/`.

## Source Availability For Copyleft Components

| Component | Redistributed form | Source / source offer |
|---|---|---|
| MusicArk own code | Python/Dart/C++ source plus packaged binaries | Public repository: https://github.com/Regstar2/music-ark |
| yandex-music 3.0.0 | Python package in frozen runtime | Upstream: https://github.com/MarshalX/yandex-music-api/ |
| mutagen 1.48.1 | Python package in frozen runtime | Upstream: https://github.com/quodlibet/mutagen |
| FFmpeg 7.1 essentials build | `ffmpeg-win-x86_64-v7.1.exe` | See `licenses/native/FFmpeg-SOURCE-OFFER.txt` |
| libmpv `v0.36.0-403-g652a1dd907` | `libmpv-2.dll` | See `licenses/native/libmpv-SOURCE-OFFER.txt` |
| PyInstaller 6.16.0 bootloader/runtime hooks | Frozen backend executable/runtime hooks | Upstream: https://github.com/pyinstaller/pyinstaller; license text in `licenses/pyinstaller-6.16.0/COPYING.txt` |

## Python Runtime And Native Runtime Libraries

| Component | Version | Source | License | Notices / obligations |
|---|---:|---|---|---|
| CPython for Windows | 3.13.14 | https://www.python.org/ | Python Software Foundation License | Include `licenses/python-3.13.14/LICENSE.txt`; keep Python and Windows binary-build notices. |
| OpenSSL | 3.0.21 | https://www.openssl.org/ | Apache-2.0 | Redistributed as `libcrypto-3.dll` and `libssl-3.dll`; include Apache-2.0 text. |
| SQLite | 3.50.4 | https://sqlite.org/ | Public domain / blessing | Redistributed as `sqlite3.dll`; no additional source offer required. |
| zlib | 1.3.1 | https://zlib.net/ | zlib License | Included through CPython runtime; see Python license text. |
| libffi | 8.x DLL from CPython build | https://sourceware.org/libffi/ | MIT-style | Included through CPython runtime; see Python license text. |
| Microsoft Universal C Runtime / Visual C++ runtime | Windows runtime DLLs bundled by CPython/PyInstaller | Microsoft | Microsoft Distributable Code terms | See additional Windows binary-build conditions in `licenses/python-3.13.14/LICENSE.txt`. |

## Frozen Python Packages

These packages were present in the PyInstaller analysis/PYZ inventory or copied
into `.venv/Scripts/_internal`.

| Package | Version | Source | License | Notices / obligations |
|---|---:|---|---|---|
| anyio | 4.14.2 | https://github.com/agronholm/anyio | MIT | Include package license text. |
| certifi | 2026.7.22 | https://github.com/certifi/python-certifi | MPL-2.0 | Include package license text for the Mozilla CA bundle. |
| charset-normalizer | 3.5.1 | https://github.com/jawah/charset_normalizer | MIT | Include package license text. |
| h11 | 0.16.0 | https://github.com/python-hyper/h11 | MIT | Include package license text. |
| h2 | 4.4.1 | https://github.com/python-hyper/h2/ | MIT | Include package license text. |
| hpack | 4.2.0 | https://github.com/python-hyper/hpack/ | MIT | Include package license text. |
| httpcore | 1.0.9 | https://github.com/encode/httpcore | BSD-3-Clause | Include package license text. |
| httpx | 0.28.1 | https://github.com/encode/httpx | BSD-3-Clause | Include package license text. |
| hyperframe | 6.1.0 | https://github.com/python-hyper/hyperframe/ | MIT | Include package license text. |
| idna | 3.19 | https://github.com/kjd/idna | BSD-3-Clause | Include package license text. |
| imageio-ffmpeg | 0.6.0 | https://github.com/imageio/imageio-ffmpeg | BSD-2-Clause | Include package license text; bundled FFmpeg executable has separate GPLv3 notice/source offer. |
| jaraco.classes | 3.4.0 | https://github.com/jaraco/jaraco.classes | MIT | Include package license text. |
| jaraco.context | 6.1.2 | https://github.com/jaraco/jaraco.context | MIT | Include package license text. |
| jaraco.functools | 4.6.0 | https://github.com/jaraco/jaraco.functools | MIT | Include package license text. |
| keyring | 25.7.0 | https://github.com/jaraco/keyring | MIT | Include package license text. |
| more-itertools | 11.1.0 | https://github.com/more-itertools/more-itertools | MIT | Include package license text. |
| mutagen | 1.48.1 | https://github.com/quodlibet/mutagen | GPL-2.0-or-later | Include GPL text/copyright notice and provide source availability. |
| packaging | 26.3 | https://github.com/pypa/packaging | Apache-2.0 OR BSD-2-Clause | Include package license texts. |
| PySocks | 1.7.1 | https://github.com/Anorov/PySocks | BSD-style | Include package license text. |
| pywin32-ctypes | 0.2.3 | https://github.com/enthought/pywin32-ctypes | BSD-3-Clause | Include package license text. |
| requests | 2.34.2 | https://github.com/psf/requests | Apache-2.0 | Include package license and NOTICE. |
| setuptools | 84.0.0 | https://github.com/pypa/setuptools | MIT | Include package license/notice and licenses for the vendored subset present in the frozen runtime. |
| socksio | 1.0.0 | https://github.com/sethmlarson/socksio | MIT | Include package license text. |
| typing_extensions | 4.16.0 | https://github.com/python/typing_extensions | PSF-2.0 | Include package license text. |
| urllib3 | 2.7.0 | https://github.com/urllib3/urllib3 | MIT | Include package license text. |
| yandex-music | 3.0.0 | https://github.com/MarshalX/yandex-music-api/ | LGPLv3 | Include LGPLv3/GPLv3 license texts and provide source availability. |

The PyInstaller `PYZ` inventory also includes these modules vendored under
`setuptools._vendor` in the frozen backend runtime:

| Vendored component | Version | Source | License | Notices / obligations |
|---|---:|---|---|---|
| importlib_metadata | 8.7.1 | https://github.com/python/importlib_metadata | Apache-2.0 | Include `licenses/python-packages/setuptools-84.0.0/vendor/importlib_metadata-8.7.1-LICENSE.txt`. |
| jaraco.text | 4.0.0 | https://github.com/jaraco/jaraco.text | MIT | Include `licenses/python-packages/setuptools-84.0.0/vendor/jaraco.text-4.0.0-LICENSE.txt`. |
| packaging | 26.0 | https://github.com/pypa/packaging | Apache-2.0 OR BSD-2-Clause | Include `licenses/python-packages/setuptools-84.0.0/vendor/packaging-26.0-LICENSE.txt`, `packaging-26.0-LICENSE.APACHE.txt` and `packaging-26.0-LICENSE.BSD.txt`. |
| tomli | 2.4.0 | https://github.com/hukkin/tomli | MIT | Include `licenses/python-packages/setuptools-84.0.0/vendor/tomli-2.4.0-LICENSE.txt`. |
| wheel | 0.46.3 | https://github.com/pypa/wheel | MIT | Include `licenses/python-packages/setuptools-84.0.0/vendor/wheel-0.46.3-LICENSE.txt`. |
| zipp | 3.23.0 | https://github.com/jaraco/zipp | MIT | Include `licenses/python-packages/setuptools-84.0.0/vendor/zipp-3.23.0-LICENSE.txt`. |

## Flutter, Dart And Windows UI Runtime

The release build uses Flutter 3.44.9 and Dart 3.12.2. The Windows bundle
contains `flutter_windows.dll` and Flutter asset/runtime data. Flutter's
generated notices are shipped at `data/flutter_assets/NOTICES.Z`.

Runtime packages from `pubspec.lock` and the Windows release dependency graph:

| Package | Version | Source | License | Notices / obligations |
|---|---:|---|---|---|
| Flutter SDK / flutter / flutter_localizations / sky_engine | 3.44.9 / Dart 3.12.2 | https://github.com/flutter/flutter | BSD-3-Clause-style | Include Flutter SDK license and generated `NOTICES.Z`. |
| archive | 4.1.0 | https://pub.dev/packages/archive | MIT | Include package license text. |
| async | 2.13.1 | https://pub.dev/packages/async | BSD-3-Clause | Include package license/authors. |
| characters | 1.4.1 | https://pub.dev/packages/characters | BSD-3-Clause | Include package license/authors. |
| clock | 1.1.2 | https://pub.dev/packages/clock | Apache-2.0 | Include package license/authors. |
| collection | 1.19.1 | https://pub.dev/packages/collection | BSD-3-Clause | Include package license/authors. |
| cross_file | 0.3.5+4 | https://pub.dev/packages/cross_file | BSD-3-Clause | Include package license/authors. |
| crypto | 3.0.7 | https://pub.dev/packages/crypto | BSD-3-Clause | Include package license/authors. |
| cupertino_icons | 1.0.9 | https://pub.dev/packages/cupertino_icons | MIT | Include package license text. |
| ffi | 2.2.0 | https://pub.dev/packages/ffi | BSD-3-Clause | Include package license/authors. |
| file_selector | 1.1.0 | https://pub.dev/packages/file_selector | BSD-3-Clause | Include package license/authors. |
| file_selector_platform_interface | 2.7.0 | https://pub.dev/packages/file_selector_platform_interface | BSD-3-Clause | Include package license/authors. |
| file_selector_windows | 0.9.3+5 | https://pub.dev/packages/file_selector_windows | BSD-3-Clause | Include package license/authors; native DLL is redistributed. |
| fixnum | 1.1.1 | https://pub.dev/packages/fixnum | BSD-3-Clause | Include package license/authors. |
| http | 1.6.0 | https://pub.dev/packages/http | BSD-3-Clause | Include package license text. |
| http_parser | 4.1.2 | https://pub.dev/packages/http_parser | BSD-3-Clause | Include package license text. |
| image | 4.9.2 | https://pub.dev/packages/image | MIT | Include package license text. |
| intl | 0.20.2 | https://pub.dev/packages/intl | BSD-3-Clause | Include package license/authors. |
| material_color_utilities | 0.13.0 | https://pub.dev/packages/material_color_utilities | Apache-2.0 | Include package license text. |
| media_kit | 1.2.6 | https://github.com/media-kit/media-kit | MIT | Include package license text. |
| media_kit_libs_audio | 1.0.7 | https://github.com/media-kit/media-kit | MIT | Include package license text. |
| media_kit_libs_windows_audio | 1.0.9 | https://github.com/media-kit/media-kit | MIT | Include package license text; `libmpv-2.dll` has separate LGPL/source notice. |
| hls.js asset bundled by media_kit | 1.4.10 | https://github.com/video-dev/hls.js/tree/v1.4.10 | Apache-2.0 | Included as `data/flutter_assets/packages/media_kit/assets/web/hls1.4.10.js`; include hls.js license text. |
| meta | 1.18.0 | https://pub.dev/packages/meta | BSD-3-Clause | Include package license text. |
| path | 1.9.1 | https://pub.dev/packages/path | BSD-3-Clause | Include package license text. |
| plugin_platform_interface | 2.1.8 | https://pub.dev/packages/plugin_platform_interface | BSD-3-Clause | Include package license/authors. |
| posix | 6.5.2 | https://pub.dev/packages/posix | MIT | Include package license text. |
| safe_local_storage | 2.0.6 | https://pub.dev/packages/safe_local_storage | MIT | Include package license text. |
| synchronized | 3.4.1+2 | https://pub.dev/packages/synchronized | MIT | Include package license text. |
| typed_data | 1.4.0 | https://pub.dev/packages/typed_data | BSD-3-Clause | Include package license/authors. |
| universal_platform | 1.1.0 | https://pub.dev/packages/universal_platform | MIT | Include package license text. |
| uri_parser | 3.0.2 | https://pub.dev/packages/uri_parser | MIT | Include package license text. |
| uuid | 4.6.0 | https://pub.dev/packages/uuid | MIT | Include package license text. |
| vector_math | 2.2.0 | https://pub.dev/packages/vector_math | BSD-3-Clause | Include package license/authors. |
| web | 1.1.1 | https://pub.dev/packages/web | BSD-3-Clause | Include package license text. |

Dev-only packages from `flutter_test` and lint tooling are not listed as
redistributed runtime components.

## Native Media Binaries

| Component | Version / evidence | Source | License | Notices / obligations |
|---|---|---|---|---|
| FFmpeg executable from imageio-ffmpeg | `ffmpeg version 7.1-essentials_build-www.gyan.dev`; configuration includes `--enable-gpl --enable-version3` | https://ffmpeg.org/ and https://www.gyan.dev/ffmpeg/builds/ | GPLv3 for the redistributed binary | Include GPLv3 text and source-offer note in `licenses/native/FFmpeg-SOURCE-OFFER.txt`. |
| libmpv | `v0.36.0-403-g652a1dd907`; `media_kit_libs_windows_audio` changelog pins `mpv-player/mpv@652a1dd90711839acdccc08004056d25514ef2d8` | https://github.com/mpv-player/mpv and media-kit build repositories | LGPL-2.1-or-later/GPL-family mpv licensing depending on enabled build parts; treated as LGPL-relevant dynamic library for notices | Include LGPL text and source-offer note in `licenses/native/libmpv-SOURCE-OFFER.txt`. |

## Yandex Music Notice

The `yandex-music` dependency is an unofficial Python wrapper for Yandex Music.
MusicArk uses it as a provider adapter. MusicArk is not endorsed by, certified
by, or affiliated with Yandex. Users are responsible for complying with the
terms that apply to their Yandex Music account and any content they access,
download, convert, upload or store.
