from __future__ import annotations

from pathlib import Path


PATH = Path("ui/musicark_ui/lib/sync_page.dart")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


text = PATH.read_text(encoding="utf-8")

text = replace_once(
    text,
    """                    Text(\n                      dialogL10n.v0111ConfirmRole(\n                        dialogL10n.v0111RoleUnavailable,\n                        _int(uploadByRole['unavailable']),\n                      ),\n                    ),\n""",
    "",
    "remove unavailable confirmation row",
)

text = replace_once(
    text,
    """    final state = '${item['recoveryState'] ?? ''}';\n    final role = state.startsWith('censored_') ? 'censored' : 'unavailable';\n    final playlistKind = _managedRoleKind(role);\n    if (bridge == null || localFileId == null || playlistKind == null) return;\n""",
    """    final state = '${item['recoveryState'] ?? ''}';\n    if (!state.startsWith('censored_')) return;\n    const role = 'censored';\n    final playlistKind = _managedRoleKind(role);\n    if (bridge == null || localFileId == null || playlistKind == null) return;\n""",
    "guard row-level restore to censorship only",
)

text = replace_once(
    text,
    """      (\n        context.l10n.v0111Recoverable,\n        _int(summary['unavailableRecoverable']) +\n            _int(summary['censoredRecoverable']),\n      ),\n""",
    """      (\n        context.l10n.v0111Recoverable,\n        _int(summary['censoredRecoverable']),\n      ),\n""",
    "exclude unavailable local copies from actionable recoverable count",
)

text = replace_once(
    text,
    """    final localReady = item['localMp3Ready'] == true;\n    final needsReview = '${item['recoveryState'] ?? ''}'.contains(\n      'needs_review',\n    );\n    final role = '${item['recoveryState'] ?? ''}'.startsWith('censored_')\n        ? 'censored'\n        : 'unavailable';\n    final canRestore =\n        localReady && !needsReview && _managedRoleKind(role) != null;\n""",
    """    final localReady = item['localMp3Ready'] == true;\n    final recoveryState = '${item['recoveryState'] ?? ''}';\n    final needsReview = recoveryState.contains('needs_review');\n    final censoredRecovery = recoveryState.startsWith('censored_');\n    final canRestore =\n        censoredRecovery &&\n        localReady &&\n        !needsReview &&\n        _managedRoleKind('censored') != null;\n""",
    "make unavailable rows informational",
)

text = replace_once(
    text,
    """          const SizedBox(width: 8),\n          OutlinedButton.icon(\n            key: Key('sync-recovery-restore-$externalId'),\n            onPressed: canRestore ? () => _restoreRecoveryTrack(item) : null,\n            icon: const Icon(Icons.cloud_upload_outlined),\n            label: Text(\n              localReady\n                  ? context.l10n.v0111ReadyToRestore\n                  : context.l10n.v0111NeedsLocalFile,\n            ),\n          ),\n""",
    """          if (censoredRecovery) ...[\n            const SizedBox(width: 8),\n            OutlinedButton.icon(\n              key: Key('sync-recovery-restore-$externalId'),\n              onPressed: canRestore ? () => _restoreRecoveryTrack(item) : null,\n              icon: const Icon(Icons.cloud_upload_outlined),\n              label: Text(\n                localReady\n                    ? context.l10n.v0111ReadyToRestore\n                    : context.l10n.v0111NeedsLocalFile,\n              ),\n            ),\n          ],\n""",
    "hide restore button on unavailable rows",
)

if "v0111RoleUnavailable" in text:
    raise RuntimeError("unavailable managed-role UI reference remains")

PATH.write_text(text, encoding="utf-8")
print(f"Patched {PATH}")
