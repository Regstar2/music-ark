import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app_info.dart';
import 'feedback_bridge.dart';
import 'update_bridge.dart';
import 'v015_strings.dart';

class DistributionSettingsCard extends StatefulWidget {
  const DistributionSettingsCard({
    super.key,
    this.updateBridge,
    this.feedbackBridge,
    this.autoCheck = true,
  });

  final UpdateBridgeClient? updateBridge;
  final FeedbackBridgeClient? feedbackBridge;
  final bool autoCheck;

  @override
  State<DistributionSettingsCard> createState() => _DistributionSettingsCardState();
}

class _DistributionSettingsCardState extends State<DistributionSettingsCard> {
  late final UpdateBridgeClient _updates;
  late final FeedbackBridgeClient _feedback;

  bool _checking = false;
  bool _preparing = false;
  bool _installing = false;
  bool? _available;
  String _current = AppInfo.version;
  String? _latest;
  String? _prepared;
  String? _message;

  @override
  void initState() {
    super.initState();
    _updates = widget.updateBridge ?? UpdateBridge();
    _feedback = widget.feedbackBridge ?? FeedbackBridge();
    if (widget.autoCheck) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _check(silentFailure: true));
    }
  }

  Future<void> _check({bool silentFailure = false}) async {
    if (_checking) return;
    setState(() {
      _checking = true;
      if (!silentFailure) _message = null;
    });
    try {
      final result = await _updates.check();
      final latest = result['latest'];
      if (!mounted) return;
      setState(() {
        _current = '${result['currentVersion'] ?? AppInfo.version}';
        _available = result['available'] == true;
        _latest = latest is Map ? '${latest['version'] ?? ''}' : null;
        _message = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        if (!silentFailure) _message = '$error';
      });
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  Future<void> _prepare() async {
    if (_preparing) return;
    setState(() {
      _preparing = true;
      _message = null;
    });
    try {
      final result = await _updates.prepare();
      if (!mounted) return;
      setState(() {
        _available = result['available'] == true;
        _prepared = result['available'] == true ? '${result['version'] ?? ''}' : null;
        _latest = '${result['version'] ?? _latest ?? ''}';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _message = '$error');
    } finally {
      if (mounted) setState(() => _preparing = false);
    }
  }

  Future<void> _install() async {
    final version = _prepared;
    if (version == null || version.isEmpty || _installing) return;
    final strings = V015Strings.of(context);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(strings.installTitle),
        content: Text(strings.installBody(version)),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: Text(strings.cancel)),
          FilledButton(
            key: const Key('confirm-install-update'),
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(strings.installUpdate),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() {
      _installing = true;
      _message = null;
    });
    try {
      await _updates.apply(version, confirm: true);
      if (!mounted) return;
      setState(() => _message = strings.installerLaunched);
    } catch (error) {
      if (!mounted) return;
      setState(() => _message = '$error');
    } finally {
      if (mounted) setState(() => _installing = false);
    }
  }

  Future<void> _openFeedback(String kind) async {
    final strings = V015Strings.of(context);
    try {
      final result = await _feedback.open(kind);
      if (result['opened'] == true) return;
      final url = '${result['url'] ?? ''}'.trim();
      if (url.isNotEmpty) {
        await Clipboard.setData(ClipboardData(text: url));
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(strings.feedbackCopied)));
      }
    } catch (error) {
      if (!mounted) return;
      setState(() => _message = '$error');
    }
  }

  @override
  Widget build(BuildContext context) {
    final strings = V015Strings.of(context);
    final latest = (_latest == null || _latest!.isEmpty) ? '—' : _latest!;
    final status = switch (_available) {
      true => strings.updateAvailable,
      false => strings.upToDate,
      null => strings.updateUnavailable,
    };

    return Card(
      key: const Key('distribution-settings-card'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.system_update_alt_outlined),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(strings.distributionTitle, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 4),
                      Text(strings.distributionHint, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                Chip(label: Text('${strings.currentVersion}: $_current')),
                Chip(label: Text('${strings.latestVersion}: $latest')),
                Chip(avatar: Icon(_available == true ? Icons.new_releases_outlined : Icons.verified_outlined, size: 18), label: Text(status)),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 10,
              runSpacing: 8,
              children: [
                OutlinedButton.icon(
                  key: const Key('check-updates'),
                  onPressed: _checking ? null : () => _check(),
                  icon: _checking
                      ? const SizedBox.square(dimension: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.refresh),
                  label: Text(_checking ? strings.checking : strings.checkUpdates),
                ),
                if (_available == true && _prepared == null)
                  FilledButton.tonalIcon(
                    key: const Key('prepare-update'),
                    onPressed: _preparing ? null : _prepare,
                    icon: _preparing
                        ? const SizedBox.square(dimension: 16, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.download_outlined),
                    label: Text(_preparing ? strings.downloading : strings.downloadUpdate),
                  ),
                if (_prepared != null)
                  FilledButton.icon(
                    key: const Key('install-update'),
                    onPressed: _installing ? null : _install,
                    icon: const Icon(Icons.install_desktop_outlined),
                    label: Text(strings.installUpdate),
                  ),
              ],
            ),
            if (_message != null) ...[
              const SizedBox(height: 10),
              Text(_message!, key: const Key('distribution-message'), style: Theme.of(context).textTheme.bodySmall),
            ],
            const Divider(height: 32),
            Text(strings.feedbackHint, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
            const SizedBox(height: 10),
            Wrap(
              spacing: 10,
              runSpacing: 8,
              children: [
                OutlinedButton.icon(
                  key: const Key('report-bug'),
                  onPressed: () => _openFeedback('bug'),
                  icon: const Icon(Icons.bug_report_outlined),
                  label: Text(strings.reportBug),
                ),
                OutlinedButton.icon(
                  key: const Key('request-feature'),
                  onPressed: () => _openFeedback('feature'),
                  icon: const Icon(Icons.lightbulb_outline),
                  label: Text(strings.requestFeature),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
