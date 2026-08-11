# MusicArk

MusicArk is a desktop application for working with a personal music collection. The current project restart is intentionally limited to one flow: sign in with a Yandex Music token and display the user's Liked tracks.

[Русский](README.md) · **English**

## About

The project is being restarted from a minimal vertical slice instead of extending the previous set of loosely connected features. Existing download, synchronization, metadata, and local-library modules remain in the repository as legacy code, but they are outside the supported MVP flow.

Current flow:

```text
Flutter UI
  -> token in child-process environment
  -> Python mvp_bridge
  -> YandexMusicProvider
  -> yandex-music
  -> liked tracks
  -> Flutter list
```

## Project status

Stage: **MVP restart, v0.1.0**.

The current branch implements the sign-in UI, token validation, and reading Liked tracks. Automated tests are included, but the real network flow with a user token and the Windows release build still need to be verified manually on the developer machine.

## Features

- enter a Yandex Music token directly in the application;
- validate the token through the existing `YandexMusicProvider`;
- fetch the current Liked tracks without persisting them to SQLite;
- display track title, artists, and album;
- refresh the list during the current application session without re-entering the token;
- sign out and clear the token from UI session state;
- pass the token to Python through the child-process environment instead of command-line arguments;
- locate the repository root from debug/release directories and support `MUSICARK_REPO_ROOT`;
- locate Python through `python`, `py -3`, or `MUSICARK_PYTHON`.

## Quick start

### 1. Clone

```powershell
git clone https://github.com/Regstar2/music-ark.git
cd music-ark
```

### 2. Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
```

If PowerShell blocks the activation script, use the virtual-environment Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install -r requirements-yandex.txt
$env:MUSICARK_PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
```

### 3. Flutter dependencies

```powershell
cd ui\musicark_ui
flutter doctor
flutter config --enable-windows-desktop
flutter pub get
```

### 4. Run for testing

```powershell
flutter run -d windows
```

In the opened window:

1. paste the Yandex Music token;
2. click **Sign in** (`Войти`);
3. verify the account name;
4. verify the **Liked** (`Мне нравится`) list;
5. refresh and confirm the list loads again;
6. sign out and confirm the app returns to the token form.

## Requirements

- Windows desktop;
- Python `>=3.10`, as declared in `pyproject.toml`;
- a Flutter SDK with Dart satisfying `^3.11.5` from `ui/musicark_ui/pubspec.yaml`;
- the standard Windows C++ toolchain required by Flutter desktop builds;
- access to Yandex Music and a valid token;
- an internet connection for real sign-in and library requests.

Check the local toolchain before running:

```powershell
python --version
flutter --version
flutter doctor -v
```

## Installation

Development uses an editable installation of the Python package:

```powershell
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
```

Install Flutter packages separately:

```powershell
cd ui\musicark_ui
flutter pub get
```

The application is not yet distributed as a standalone installer.

## Usage

### Sign in

Enter the token in the application. After successful validation, MusicArk requests Liked tracks through `YandexMusicProvider.list_tracks()`.

### Refresh

The refresh button requests Liked tracks again using the token held only in the current Flutter process memory.

### Sign out

The sign-out button removes the token from the current UI session state and returns to the sign-in form.

## Configuration

Two development environment variables are supported:

| Variable | Purpose |
|---|---|
| `MUSICARK_PYTHON` | full Python path when `python` or `py -3` is unavailable through PATH |
| `MUSICARK_REPO_ROOT` | full repository-root path when automatic discovery is unsuitable |

Example:

```powershell
$env:MUSICARK_PYTHON = "C:\Path\To\python.exe"
$env:MUSICARK_REPO_ROOT = "C:\Base\music-ark"
flutter run -d windows
```

The new MVP flow does not require storing the token in `.env`, `local.properties`, or README files.

## Privacy

The MVP does not persist the entered token to SQLite or a configuration file. Flutter passes it to the child Python process through the `YANDEX_MUSIC_TOKEN` environment variable.

The Python provider still supports the legacy fallback to process-level `YANDEX_MUSIC_TOKEN` and `local.properties`, but the new UI does not write the token to either location.

Do not publish the token in Git, issues, logs, or screenshots.

## Troubleshooting

### Python is not found

Check:

```powershell
python --version
py -3 --version
```

If Python is installed but cannot be discovered automatically:

```powershell
$env:MUSICARK_PYTHON = "C:\Path\To\python.exe"
```

### Repository root is not found

Run the application from the repository checkout or set:

```powershell
$env:MUSICARK_REPO_ROOT = "C:\Path\To\music-ark"
```

### Yandex rejects the token

Enter a new valid token. MusicArk does not repair or refresh the token automatically.

### Flutter does not list Windows

Check:

```powershell
flutter config --enable-windows-desktop
flutter doctor -v
flutter devices
```

## Build

From `ui\musicark_ui`:

```powershell
flutter clean
flutter pub get
flutter analyze
flutter test
flutter build windows --release
```

Expected executable according to the current `windows/CMakeLists.txt`:

```text
ui\musicark_ui\build\windows\x64\runner\Release\musicark_ui.exe
```

Run the built application:

```powershell
.\build\windows\x64\runner\Release\musicark_ui.exe
```

The release build is **not standalone yet**: it still requires access to the repository checkout and an installed Python environment with MusicArk dependencies.

## Testing

### Python

From the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -p "test_*.py" -v
```

Without activating the venv:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

### Flutter

```powershell
cd ui\musicark_ui
flutter analyze
flutter test
```

### Full manual MVP check

After automated tests:

```powershell
flutter run -d windows
```

Follow [`docs/testing/manual-test-plan.md`](docs/testing/manual-test-plan.md).

## Documentation

- [Project idea](docs/product/idea.md)
- [MVP scope](docs/product/mvp-scope.md)
- [Roadmap](docs/product/roadmap.md)
- [Technology stack](docs/architecture/tech-stack.md)
- [Architecture](docs/architecture/architecture.md)
- [Versions index](docs/versions/versions-index.md)
- [v0.1.0](docs/versions/v0.1.0.md)
- [Manual test plan](docs/testing/manual-test-plan.md)
- [Release checklist](docs/release/release-checklist.md)
- [CHANGELOG](CHANGELOG.md)

## Limitations

- the token is currently entered manually;
- the token is not retained between application runs;
- the release build does not bundle Python runtime or Python dependencies;
- the UI only supports the Yandex Music -> Liked tracks flow;
- legacy download, sync, metadata, and local-library modules are not part of the current MVP;
- the real network flow depends on the unofficial `yandex-music` library;
- the build and real sign-in still need confirmation on the developer's Windows machine after pulling the changes.

## License

The project has no selected license and no `LICENSE` file at this time. Until a license is chosen, the code should not be assumed to permit redistribution or reuse.
