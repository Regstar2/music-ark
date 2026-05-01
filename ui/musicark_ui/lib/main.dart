import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

void main() {
  runApp(const MusicArkDesktopApp());
}

class MusicArkDesktopApp extends StatelessWidget {
  const MusicArkDesktopApp({super.key, this.bridge});

  final MusicArkBridge? bridge;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MusicArk Desktop',
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue)),
      home: MusicArkHomePage(bridge: bridge ?? const MusicArkBridge()),
    );
  }
}

class MusicArkHomePage extends StatefulWidget {
  const MusicArkHomePage({super.key, required this.bridge});

  final MusicArkBridge bridge;

  @override
  State<MusicArkHomePage> createState() => _MusicArkHomePageState();
}

class _MusicArkHomePageState extends State<MusicArkHomePage> {
  late final MusicArkBridge _bridge;
  final TextEditingController _localScanPathController = TextEditingController();
  final TextEditingController _dbPathController = TextEditingController();
  final TextEditingController _logLevelController = TextEditingController();

  /// Metadata Editor (v0.10)
  final TextEditingController _metaFileIdController = TextEditingController();
  final TextEditingController _metaTitleController = TextEditingController();
  final TextEditingController _metaArtistController = TextEditingController();
  final TextEditingController _metaAlbumController = TextEditingController();
  final TextEditingController _metaTrackController = TextEditingController();
  final TextEditingController _metaYearController = TextEditingController();
  final TextEditingController _metaGenreController = TextEditingController();
  final TextEditingController _metaCoverPathController = TextEditingController();
  final TextEditingController _metaBulkIdsController = TextEditingController();
  bool _metaWriteConfirmed = false;
  bool _metaClearCover = false;
  String? _metaResolvedPathHint;

  int _tabIndex = 0;
  bool _loading = true;
  bool _runningAction = false;
  String? _error;
  Map<String, dynamic> _snapshot = const {};

  static const List<_NavItem> _tabs = [
    _NavItem('Dashboard', Icons.dashboard),
    _NavItem('Collection', Icons.library_music),
    _NavItem('Local Library', Icons.folder),
    _NavItem('Providers', Icons.cloud),
    _NavItem('Download Queue', Icons.download),
    _NavItem('Sync Plan', Icons.sync_alt),
    _NavItem('Conflicts', Icons.warning_amber),
    _NavItem('Logs', Icons.receipt_long),
    _NavItem('Metadata', Icons.edit_note),
    _NavItem('Settings', Icons.settings),
  ];

  @override
  void initState() {
    super.initState();
    _bridge = widget.bridge;
    _refresh();
  }

  @override
  void dispose() {
    _localScanPathController.dispose();
    _dbPathController.dispose();
    _logLevelController.dispose();
    _metaFileIdController.dispose();
    _metaTitleController.dispose();
    _metaArtistController.dispose();
    _metaAlbumController.dispose();
    _metaTrackController.dispose();
    _metaYearController.dispose();
    _metaGenreController.dispose();
    _metaCoverPathController.dispose();
    _metaBulkIdsController.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final snapshot = await _bridge.snapshot();
      _dbPathController.text = (snapshot['settings']?['database_path'] ?? '').toString();
      _logLevelController.text = (snapshot['settings']?['log_level'] ?? '').toString();
      setState(() {
        _snapshot = snapshot;
      });
    } catch (err) {
      setState(() {
        _error = '$err';
      });
    } finally {
      setState(() {
        _loading = false;
      });
    }
  }

  Future<void> _runAction(String name, {String? path}) async {
    setState(() {
      _runningAction = true;
      _error = null;
    });
    try {
      await _bridge.action(name, path: path);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Action `$name` completed.')),
        );
      }
      await _refresh();
    } catch (err) {
      setState(() {
        _error = '$err';
      });
    } finally {
      setState(() {
        _runningAction = false;
      });
    }
  }

  Future<void> _saveSettings() async {
    setState(() {
      _runningAction = true;
      _error = null;
    });
    try {
      await _bridge.updateSettings(
        databasePath: _dbPathController.text.trim(),
        logLevel: _logLevelController.text.trim(),
      );
      await _refresh();
    } catch (err) {
      setState(() {
        _error = '$err';
      });
    } finally {
      setState(() {
        _runningAction = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final body = _loading
        ? const Center(child: CircularProgressIndicator())
        : _error != null
            ? Center(child: Text(_error!, style: const TextStyle(color: Colors.red)))
            : _buildTabBody();
    return Scaffold(
      appBar: AppBar(
        title: const Text('MusicArk Desktop v0.10'),
        actions: [
          IconButton(onPressed: _runningAction ? null : _refresh, icon: const Icon(Icons.refresh)),
        ],
      ),
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: _tabIndex,
            onDestinationSelected: (idx) => setState(() {
              _tabIndex = idx;
            }),
            labelType: NavigationRailLabelType.all,
            destinations: _tabs
                .map((item) => NavigationRailDestination(icon: Icon(item.icon), label: Text(item.title)))
                .toList(),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  _buildActionBar(),
                  const SizedBox(height: 12),
                  Expanded(child: body),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionBar() {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        ElevatedButton(
          onPressed: _runningAction ? null : () => _runAction('scan_yandex'),
          child: const Text('Run Yandex Scan'),
        ),
        SizedBox(
          width: 260,
          child: TextField(
            controller: _localScanPathController,
            decoration: const InputDecoration(labelText: 'Local scan path'),
          ),
        ),
        ElevatedButton(
          onPressed: _runningAction
              ? null
              : () => _runAction('scan_local', path: _localScanPathController.text.trim()),
          child: const Text('Run Local Scan'),
        ),
        ElevatedButton(
          onPressed: _runningAction ? null : () => _runAction('match_run'),
          child: const Text('Run Matching'),
        ),
        ElevatedButton(
          onPressed: _runningAction ? null : () => _runAction('sync_plan'),
          child: const Text('Build Sync Plan'),
        ),
      ],
    );
  }

  Widget _buildTabBody() {
    switch (_tabIndex) {
      case 0:
        return _buildDashboard();
      case 1:
        return _buildTable(_listOfMaps('collection'));
      case 2:
        return _buildTable(_listOfMaps('local_library'));
      case 3:
        return _buildTable(_listOfMaps('providers'));
      case 4:
        return _buildTable(_listOfMaps('download_queue'));
      case 5:
        return _buildTable(_listOfMaps('sync_plans'));
      case 6:
        return _buildTable(_listOfMaps('conflicts'));
      case 7:
        return _buildTable(_listOfMaps('logs'));
      case 8:
        return _buildMetadataEditor();
      case 9:
        return _buildSettings();
      default:
        return const SizedBox.shrink();
    }
  }

  Future<void> _loadMetadataFromDisk() async {
    final raw = _metaFileIdController.text.trim();
    final id = int.tryParse(raw);
    if (id == null) {
      setState(() => _error = 'Metadata: enter numeric local file id (from Local Library list).');
      return;
    }
    setState(() {
      _runningAction = true;
      _error = null;
    });
    try {
      final row = await _bridge.action('metadata_get', payload: {'local_file_id': id});
      final tags = row['tags'] as Map<String, dynamic>? ?? const {};
      _metaTitleController.text = '${tags['title'] ?? ''}';
      _metaArtistController.text = '${tags['artist'] ?? ''}';
      _metaAlbumController.text = '${tags['album'] ?? ''}';
      _metaTrackController.text = '${tags['track_number'] ?? ''}';
      _metaYearController.text = '${tags['year'] ?? ''}';
      _metaGenreController.text = '${tags['genre'] ?? ''}';
      setState(() {
        _metaResolvedPathHint = row['path']?.toString();
        _metaClearCover = false;
      });
    } catch (err) {
      setState(() => _error = '$err');
    } finally {
      setState(() => _runningAction = false);
    }
  }

  Future<void> _saveMetadataToDisk() async {
    if (_metaResolvedPathHint == null) {
      setState(() => _error = 'Load tags once so the bridge resolves the indexed path, then edit and save.');
      return;
    }
    if (!_metaWriteConfirmed) {
      setState(() => _error = 'Check the confirmation box before writing tags to disk.');
      return;
    }
    final raw = _metaFileIdController.text.trim();
    final id = int.tryParse(raw);
    if (id == null) {
      setState(() => _error = 'Metadata: invalid file id.');
      return;
    }
    final payload = <String, dynamic>{
      'confirm': true,
      'local_file_id': id,
      'title': _metaTitleController.text.trim(),
      'artist': _metaArtistController.text.trim(),
      'album': _metaAlbumController.text.trim(),
      'genre': _metaGenreController.text.trim(),
    };
    final tr = _metaTrackController.text.trim();
    if (tr.isNotEmpty) {
      final tn = int.tryParse(tr.split('/').first.trim());
      if (tn != null) {
        payload['track_number'] = tn;
      }
    }
    final y = _metaYearController.text.trim();
    if (y.isNotEmpty) {
      final yi = int.tryParse(y.length >= 4 ? y.substring(0, 4) : y);
      if (yi != null) {
        payload['year'] = yi;
      }
    }
    final cov = _metaCoverPathController.text.trim();
    if (cov.isNotEmpty) {
      payload['cover_image_path'] = cov;
    }
    if (_metaClearCover) {
      payload['clear_cover'] = true;
    }
    setState(() {
      _runningAction = true;
      _error = null;
    });
    try {
      final res = await _bridge.action('metadata_update', payload: payload);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              res['backup_path'] != null
                  ? 'Saved. Backup: ${res['backup_path']}'
                  : 'Metadata saved.',
            ),
          ),
        );
      }
      await _refresh();
    } catch (err) {
      setState(() => _error = '$err');
    } finally {
      setState(() => _runningAction = false);
    }
  }

  Future<void> _saveMetadataBulk() async {
    if (!_metaWriteConfirmed) {
      setState(() => _error = 'Check the confirmation box for bulk edits.');
      return;
    }
    final parts = _metaBulkIdsController.text.trim().split(RegExp(r'[\s,;]+'));
    final ids = <int>[];
    for (final p in parts) {
      if (p.isEmpty) {
        continue;
      }
      final v = int.tryParse(p);
      if (v == null) {
        setState(() => _error = 'Bulk ids: invalid token "$p".');
        return;
      }
      ids.add(v);
    }
    if (ids.length < 2) {
      setState(() => _error = 'Bulk update needs at least two numeric ids (comma/space-separated).');
      return;
    }
    final payload = <String, dynamic>{
      'confirm': true,
      'local_file_ids': ids,
      'title': _metaTitleController.text.trim(),
      'artist': _metaArtistController.text.trim(),
      'album': _metaAlbumController.text.trim(),
      'genre': _metaGenreController.text.trim(),
    };
    final tr = _metaTrackController.text.trim();
    if (tr.isNotEmpty) {
      final tn = int.tryParse(tr.split('/').first.trim());
      if (tn != null) {
        payload['track_number'] = tn;
      }
    }
    final y = _metaYearController.text.trim();
    if (y.isNotEmpty) {
      final yi = int.tryParse(y.length >= 4 ? y.substring(0, 4) : y);
      if (yi != null) {
        payload['year'] = yi;
      }
    }
    final cov = _metaCoverPathController.text.trim();
    if (cov.isNotEmpty) {
      payload['cover_image_path'] = cov;
    }
    if (_metaClearCover) {
      payload['clear_cover'] = true;
    }
    setState(() {
      _runningAction = true;
      _error = null;
    });
    try {
      final report = await _bridge.action('metadata_bulk_update', payload: payload);
      if (mounted) {
        final okList = report['succeeded'] as List<dynamic>? ?? const [];
        final badList = report['failed'] as List<dynamic>? ?? const [];
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Bulk: OK ${okList.length}, failed ${badList.length}.'),
          ),
        );
      }
      await _refresh();
    } catch (err) {
      setState(() => _error = '$err');
    } finally {
      setState(() => _runningAction = false);
    }
  }

  Widget _buildMetadataEditor() {
    return ListView(
      padding: const EdgeInsets.only(bottom: 24),
      children: [
        const Text(
          'Loads tags from disk via mutagen (MP3, FLAC, M4A/AAC/MP4; OGG text-only, no cover). '
          'A full-file backup copy is written under .musicark/metadata_backups before each save.',
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _metaFileIdController,
          decoration: const InputDecoration(
            labelText: 'Local file ID',
            helperText: 'Same id shown in Local Library tab',
          ),
          keyboardType: TextInputType.number,
        ),
        const SizedBox(height: 8),
        if (_metaResolvedPathHint != null) Text('Path: $_metaResolvedPathHint'),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            ElevatedButton(
              onPressed: _runningAction ? null : _loadMetadataFromDisk,
              child: const Text('Load tags from file'),
            ),
            ElevatedButton(
              onPressed: _runningAction ? null : _saveMetadataToDisk,
              style: ElevatedButton.styleFrom(foregroundColor: Colors.redAccent),
              child: const Text('Save to file + DB'),
            ),
          ],
        ),
        TextField(controller: _metaTitleController, decoration: const InputDecoration(labelText: 'Title')),
        TextField(controller: _metaArtistController, decoration: const InputDecoration(labelText: 'Artist')),
        TextField(controller: _metaAlbumController, decoration: const InputDecoration(labelText: 'Album')),
        TextField(
          controller: _metaTrackController,
          decoration: const InputDecoration(labelText: 'Track number'),
          keyboardType: TextInputType.number,
        ),
        TextField(
          controller: _metaYearController,
          decoration: const InputDecoration(labelText: 'Year'),
          keyboardType: TextInputType.number,
        ),
        TextField(controller: _metaGenreController, decoration: const InputDecoration(labelText: 'Genre')),
        TextField(
          controller: _metaCoverPathController,
          decoration: const InputDecoration(
            labelText: 'JPEG cover image path',
            helperText: 'Optional; JPEG recommended for portability',
          ),
        ),
        CheckboxListTile(
          value: _metaClearCover,
          onChanged: (v) => setState(() => _metaClearCover = v ?? false),
          title: const Text('Clear embedded cover'),
        ),
        CheckboxListTile(
          value: _metaWriteConfirmed,
          onChanged: (v) => setState(() => _metaWriteConfirmed = v ?? false),
          title: const Text('Confirm writing metadata to disk (required)'),
          controlAffinity: ListTileControlAffinity.leading,
        ),
        const Divider(height: 32),
        const Text(
          'Bulk edit: Same field values applied to multiple files — each file is backed up. '
          'Requires at least two ids.',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: _metaBulkIdsController,
          decoration: const InputDecoration(
            labelText: 'Bulk IDs',
            helperText: 'Comma or whitespace separated local file IDs',
          ),
        ),
        const SizedBox(height: 8),
        ElevatedButton(
          onPressed: _runningAction ? null : _saveMetadataBulk,
          child: const Text('Bulk apply fields'),
        ),
      ],
    );
  }

  Widget _buildDashboard() {
    final dashboard = (_snapshot['dashboard'] as Map<String, dynamic>? ?? const {});
    final cards = dashboard.entries
        .map((entry) => _DashboardCard(title: entry.key, value: '${entry.value}'))
        .toList();
    return GridView.count(
      crossAxisCount: 3,
      crossAxisSpacing: 8,
      mainAxisSpacing: 8,
      children: cards,
    );
  }

  Widget _buildSettings() {
    return ListView(
      children: [
        TextField(
          controller: _dbPathController,
          decoration: const InputDecoration(labelText: 'Database path'),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: _logLevelController,
          decoration: const InputDecoration(labelText: 'Log level'),
        ),
        const SizedBox(height: 12),
        ElevatedButton(
          onPressed: _runningAction ? null : _saveSettings,
          child: const Text('Save settings'),
        ),
      ],
    );
  }

  Widget _buildTable(List<Map<String, dynamic>> rows) {
    if (rows.isEmpty) {
      return const Center(child: Text('No data yet.'));
    }
    final columns = rows.first.keys.toList();
    return ListView.builder(
      itemCount: rows.length,
      itemBuilder: (context, index) {
        final row = rows[index];
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final col in columns)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text('$col: ${row[col]}'),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  List<Map<String, dynamic>> _listOfMaps(String key) {
    final raw = _snapshot[key];
    if (raw is! List) {
      return const [];
    }
    return raw.map((item) => Map<String, dynamic>.from(item as Map)).toList();
  }
}

class _DashboardCard extends StatelessWidget {
  const _DashboardCard({required this.title, required this.value});

  final String title;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(value, style: Theme.of(context).textTheme.headlineSmall),
          ],
        ),
      ),
    );
  }
}

class _NavItem {
  const _NavItem(this.title, this.icon);

  final String title;
  final IconData icon;
}

class MusicArkBridge {
  const MusicArkBridge();

  Future<Map<String, dynamic>> snapshot() {
    return _runBridge(['snapshot']);
  }

  Future<Map<String, dynamic>> action(
    String name, {
    String? path,
    Map<String, dynamic>? payload,
  }) {
    final args = ['action', '--name', name];
    if (path != null && path.isNotEmpty) {
      args.addAll(['--path', path]);
    }
    if (payload != null && payload.isNotEmpty) {
      args.addAll(['--payload', jsonEncode(payload)]);
    }
    return _runBridge(args);
  }

  Future<Map<String, dynamic>> updateSettings({
    required String databasePath,
    required String logLevel,
  }) {
    return _runBridge([
      'settings-update',
      '--database-path',
      databasePath,
      '--log-level',
      logLevel,
    ]);
  }

  Future<Map<String, dynamic>> _runBridge(List<String> bridgeArgs) async {
    final repoRoot = Directory.current.parent.parent.absolute.path;
    final srcPath = '$repoRoot${Platform.pathSeparator}src';
    final existingPythonPath = Platform.environment['PYTHONPATH'];
    final mergedPythonPath = (existingPythonPath == null || existingPythonPath.isEmpty)
        ? srcPath
        : '$srcPath${Platform.isWindows ? ';' : ':'}$existingPythonPath';
    final args = ['-m', 'musicark.platform_bridge', '--base-dir', repoRoot, ...bridgeArgs];
    final bridgeEnv = <String, String>{
      ...Platform.environment,
      'PYTHONPATH': mergedPythonPath,
      'PYTHONIOENCODING': 'utf-8',
      'PYTHONUTF8': '1',
    };
    final result = await Process.run(
      'python',
      args,
      runInShell: true,
      workingDirectory: repoRoot,
      environment: bridgeEnv,
    );
    final stdoutText = (result.stdout ?? '').toString().trim();
    final stderrText = (result.stderr ?? '').toString().trim();
    if (result.exitCode != 0) {
      throw Exception(stderrText.isEmpty ? stdoutText : stderrText);
    }
    if (stdoutText.isEmpty) {
      return const {};
    }
    final payload = jsonDecode(stdoutText);
    if (payload is Map<String, dynamic>) {
      if (payload.containsKey('error')) {
        throw Exception(payload['error'].toString());
      }
      return payload;
    }
    throw Exception('Bridge returned invalid payload.');
  }
}

class FakeMusicArkBridge extends MusicArkBridge {
  const FakeMusicArkBridge();

  @override
  Future<Map<String, dynamic>> snapshot() async {
    return {
      'dashboard': {'providers': 1, 'remote_tracks': 2, 'local_files': 3},
      'collection': [],
      'local_library': [],
      'providers': [],
      'download_queue': [],
      'sync_plans': [],
      'conflicts': [],
      'logs': [],
      'settings': {'database_path': '.musicark/musicark.db', 'log_level': 'INFO'},
    };
  }

  @override
  Future<Map<String, dynamic>> action(String name, {String? path, Map<String, dynamic>? payload}) async {
    return {'status': 'ok', 'name': name, 'payload Echo': payload};
  }

  @override
  Future<Map<String, dynamic>> updateSettings({
    required String databasePath,
    required String logLevel,
  }) async {
    return {
      'saved_to': '.musicark/config.json',
      'settings': {'database_path': databasePath, 'log_level': logLevel},
    };
  }
}
