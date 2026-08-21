from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str, *, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual < count:
        raise RuntimeError(f"{path}: expected >= {count}, found {actual}: {old[:120]!r}")
    target.write_text(text.replace(old, new, count), encoding="utf-8")


# Local Library: stale failures/finally blocks must not overwrite a newer reload.
replace(
    "ui/musicark_ui/lib/local_library_page.dart",
    "    } on MusicArkBridgeException catch (error) {\n      if (mounted) setState(() => _error = error.message);\n    } finally {\n      if (mounted) setState(() => _busy = false);\n    }\n  }\n\n  Future<void> _loadMore() async {",
    "    } on MusicArkBridgeException catch (error) {\n      if (mounted && generation == _requestGeneration) {\n        setState(() => _error = error.message);\n      }\n    } finally {\n      if (mounted && generation == _requestGeneration) {\n        setState(() => _busy = false);\n      }\n    }\n  }\n\n  Future<void> _loadMore() async {",
)
replace(
    "ui/musicark_ui/lib/local_library_page.dart",
    "    } on MusicArkBridgeException catch (error) {\n      if (mounted) setState(() => _error = error.message);\n    } finally {\n      if (mounted) setState(() => _busy = false);\n    }\n  }\n\n  Future<void> _addFolder() async {",
    "    } on MusicArkBridgeException catch (error) {\n      if (mounted && generation == _requestGeneration) {\n        setState(() => _error = error.message);\n      }\n    } finally {\n      if (mounted && generation == _requestGeneration) {\n        setState(() => _busy = false);\n      }\n    }\n  }\n\n  Future<void> _addFolder() async {",
)

# Matching: same success/error/finally generation boundary.
replace(
    "ui/musicark_ui/lib/matching_workspace_page.dart",
    "    } catch (error) {\n      if (mounted) setState(() => _error = _errorText(error));\n    } finally {\n      if (mounted) setState(() => _loading = false);\n    }\n  }\n\n  Future<void> _runMatching() async {",
    "    } catch (error) {\n      if (mounted && generation == _requestGeneration) {\n        setState(() => _error = _errorText(error));\n      }\n    } finally {\n      if (mounted && generation == _requestGeneration) {\n        setState(() => _loading = false);\n      }\n    }\n  }\n\n  Future<void> _runMatching() async {",
)
replace(
    "ui/musicark_ui/lib/matching_workspace_page.dart",
    "    } catch (error) {\n      if (mounted) setState(() => _error = _errorText(error));\n    } finally {\n      if (mounted) setState(() => _loadingMore = false);\n    }\n  }",
    "    } catch (error) {\n      if (mounted && generation == _requestGeneration) {\n        setState(() => _error = _errorText(error));\n      }\n    } finally {\n      if (mounted && generation == _requestGeneration) {\n        setState(() => _loadingMore = false);\n      }\n    }\n  }",
    count=1,
)

# Coverage: stale error/completion paths cannot clear a newer spinner or error state.
replace(
    "ui/musicark_ui/lib/coverage_page.dart",
    "    } catch (error) {\n      if (!mounted) return;\n      setState(() {\n        _loading = false;\n        _error = error.toString();\n      });\n    }\n  }\n\n  Future<void> _reloadTracks({",
    "    } catch (error) {\n      if (!mounted || generation != _requestGeneration) return;\n      setState(() {\n        _loading = false;\n        _error = error.toString();\n      });\n    }\n  }\n\n  Future<void> _reloadTracks({",
)
replace(
    "ui/musicark_ui/lib/coverage_page.dart",
    "    } catch (error) {\n      if (!mounted) return;\n      setState(() {\n        _loading = false;\n        _error = error.toString();\n      });\n    }\n  }\n\n  void _setStatus(String status) {",
    "    } catch (error) {\n      if (!mounted || generation != _requestGeneration) return;\n      setState(() {\n        _loading = false;\n        _error = error.toString();\n      });\n    }\n  }\n\n  void _setStatus(String status) {",
)

# Downloads: only latest polling/manual request may publish success or failure state.
replace(
    "ui/musicark_ui/lib/download_page.dart",
    "    } catch (error) {\n      if (!mounted) return;\n      setState(() {\n        _error = error.toString();\n        _loading = false;\n      });\n    }\n  }\n\n  Future<void> _loadWanted",
    "    } catch (error) {\n      if (!mounted || generation != _loadGeneration) return;\n      setState(() {\n        _error = error.toString();\n        _loading = false;\n      });\n    }\n  }\n\n  Future<void> _loadWanted",
)
replace(
    "ui/musicark_ui/lib/download_page.dart",
    "    } catch (error) {\n      if (!mounted) return;\n      setState(() {\n        _wantedLoading = false;\n        _error = error.toString();\n      });\n    }\n  }\n\n  Future<void> _refreshCurrent",
    "    } catch (error) {\n      if (!mounted || generation != _wantedLoadGeneration) return;\n      setState(() {\n        _wantedLoading = false;\n        _error = error.toString();\n      });\n    }\n  }\n\n  Future<void> _refreshCurrent",
)

print("stale guard patch applied")
