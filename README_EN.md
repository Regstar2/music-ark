# MusicArk

MusicArk is a Windows desktop application for a personal music collection. **v0.2.0 Persistent Library** builds on the verified v0.1.0 flow: after the first successful Yandex Music sign-in, the token is stored in the operating-system credential store and the Liked library is cached locally for immediate startup.

[Русский](README.md) · **English**

## v0.2.0 features

- first sign-in with a Yandex Music OAuth token;
- secure token persistence through Python `keyring` / Windows Credential Locker;
- automatic session restoration after restarting MusicArk;
- SQLite snapshot cache for Liked tracks;
- cache-first startup followed by a network refresh;
- cached library remains visible when refresh fails;
- tracks removed from Yandex Liked are removed from the next local snapshot;
- track count and last-update timestamp;
- search by title, artist, and album;
- sorting by Yandex order, title, or artist;
- refresh diff for added/removed tracks;
- logout deletes both the stored token and cached library.

Legacy download, matching, sync, metadata, and local-library modules remain outside the supported UI.

## Architecture

```text
Flutter UI
  -> musicark.mvp_bridge subprocess
       -> SystemCredentialStore -> Windows Credential Locker
       -> PersistentLibraryService
            -> YandexMusicProvider -> yandex-music
            -> LikedCacheRepository -> SQLite
```

The token is sent through the child-process environment only for the first sign-in. After successful authentication, later bridge processes read it from the OS credential store. SQLite never contains the token.

## Requirements

- Windows;
- Python >= 3.10;
- Flutter SDK with Windows desktop support;
- the Visual Studio C++ toolchain required by `flutter doctor`;
- Git;
- internet access for initial sign-in and Yandex Music refreshes.

## Full run from a new PowerShell session

```powershell
cd C:\Base\projects\MusicArk

git fetch origin
git switch agent/v0.2-persistent-library
git pull

git status

.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt

python -c "import keyring; print(keyring.get_keyring())"
python -c "import musicark.mvp_bridge; print('MVP bridge import OK')"
python -m unittest discover -s tests -p "test_*.py" -v

$env:Path = "C:\Base\tools\flutter\bin;$env:Path"
$env:MUSICARK_PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path

flutter --version
flutter doctor -v
flutter config --enable-windows-desktop
flutter devices

cd .\ui\musicark_ui
flutter pub get
flutter analyze
flutter test
flutter run -d windows
```

If `.venv` does not exist yet:

```powershell
cd C:\Base\projects\MusicArk
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
```

## Manual checks

### First launch

Enter a valid token, sign in, verify the account and several Liked tracks, then test search and sorting.

### Second launch

Close MusicArk and run again:

```powershell
flutter run -d windows
```

Expected: no token prompt, cached tracks appear automatically, then the application refreshes them from Yandex Music.

### Offline/cache behavior

After at least one successful sign-in, disconnect the network and launch MusicArk again. The cached library should remain visible and the refresh error must not clear it.

### Removed track

Remove a test track from Yandex Music Liked, refresh MusicArk, and verify that the track disappears from the local snapshot.

### Logout

Logout should delete the Windows credential and cached library. The next launch must show the token form again.

## Tests

Python:

```powershell
cd C:\Base\projects\MusicArk
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -p "test_*.py" -v
```

Flutter:

```powershell
cd C:\Base\projects\MusicArk\ui\musicark_ui
flutter analyze
flutter test
```

## Release build

```powershell
cd C:\Base\projects\MusicArk\ui\musicark_ui
flutter clean
flutter pub get
flutter analyze
flutter test
flutter build windows --release

$env:MUSICARK_PYTHON = "C:\Base\projects\MusicArk\.venv\Scripts\python.exe"
$env:MUSICARK_REPO_ROOT = "C:\Base\projects\MusicArk"
.\build\windows\x64\runner\Release\musicark_ui.exe
```

The v0.2.0 release build is still not standalone. It requires the MusicArk checkout and an installed Python environment. Standalone Windows packaging is intentionally a later milestone.

## Data locations

With the standard checkout setup:

- configuration/SQLite: `C:\Base\projects\MusicArk\.musicark\`;
- Liked cache: `provider_collection_snapshots` and `provider_collection_items` in SQLite;
- Yandex token: Windows credential store, service `MusicArk`, username `yandex_music_token`.

Never place the token in Git, README files, issues, logs, or SQLite.

## Troubleshooting

Credential backend:

```powershell
python -m keyring diagnose
python -c "import keyring; print(keyring.get_keyring())"
```

Flutter not found:

```powershell
$env:Path = "C:\Base\tools\flutter\bin;$env:Path"
flutter --version
```

Python override:

```powershell
$env:MUSICARK_PYTHON = "C:\Base\projects\MusicArk\.venv\Scripts\python.exe"
```

Repository root override:

```powershell
$env:MUSICARK_REPO_ROOT = "C:\Base\projects\MusicArk"
```

## Documentation

- [MVP scope](docs/product/mvp-scope.md)
- [Roadmap](docs/product/roadmap.md)
- [Architecture](docs/architecture/architecture.md)
- [Versions](docs/versions/versions-index.md)
- [Manual test plan](docs/testing/manual-test-plan.md)
- [Release checklist](docs/release/release-checklist.md)
- [CHANGELOG](CHANGELOG.md)

## v0.2.0 limitations

- Yandex Music Liked is the only supported library surface;
- the first token is still entered manually;
- the release build does not bundle Python;
- playlists/download/matching/sync/local-library UI are not restored yet;
- Yandex integration depends on the unofficial `yandex-music` library.

## License

There is no `LICENSE` file yet.
