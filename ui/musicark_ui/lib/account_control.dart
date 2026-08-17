import 'package:flutter/material.dart';

import 'account_session.dart';
import 'app_localizations_ext.dart';

class AccountControl extends StatelessWidget {
  const AccountControl({
    super.key,
    required this.session,
    required this.onOpenYandex,
    required this.onLogout,
  });

  final AccountSessionController session;
  final VoidCallback onOpenYandex;
  final Future<void> Function() onLogout;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: session,
      builder: (context, _) {
        if (session.initializing) {
          return _AccountSurface(
            avatar: const CircleAvatar(child: Icon(Icons.person_outline)),
            title: context.l10n.accountLoading,
          );
        }
        if (!session.isSignedIn) {
          return Semantics(
            button: true,
            label: context.l10n.signIn,
            child: InkWell(
              key: const Key('global-account-sign-in'),
              onTap: onOpenYandex,
              borderRadius: BorderRadius.circular(12),
              child: _AccountSurface(
                avatar: const CircleAvatar(child: Icon(Icons.person_outline)),
                title: context.l10n.signIn,
              ),
            ),
          );
        }

        final title = session.displayName.isNotEmpty
            ? session.displayName
            : context.l10n.accountProvider;
        return PopupMenuButton<_AccountAction>(
          key: const Key('global-account-menu'),
          tooltip: context.l10n.accountMenuTitle,
          onSelected: (value) async {
            switch (value) {
              case _AccountAction.openYandex:
                onOpenYandex();
                return;
              case _AccountAction.logout:
                await onLogout();
                return;
            }
          },
          itemBuilder: (context) => [
            PopupMenuItem<_AccountAction>(
              enabled: false,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 260),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    Text(context.l10n.accountProvider),
                  ],
                ),
              ),
            ),
            const PopupMenuDivider(),
            PopupMenuItem<_AccountAction>(
              value: _AccountAction.openYandex,
              child: ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.cloud_outlined),
                title: Text(context.l10n.openYandexMusic),
              ),
            ),
            PopupMenuItem<_AccountAction>(
              value: _AccountAction.logout,
              child: ListTile(
                key: const Key('global-account-logout'),
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.logout),
                title: Text(context.l10n.signOut),
              ),
            ),
          ],
          child: _AccountSurface(
            avatar: _AccountAvatar(session: session),
            title: title,
            subtitle: context.l10n.accountProvider,
          ),
        );
      },
    );
  }
}

enum _AccountAction { openYandex, logout }

class _AccountSurface extends StatelessWidget {
  const _AccountSurface({
    required this.avatar,
    required this.title,
    this.subtitle,
  });

  final Widget avatar;
  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      child: Row(
        children: [
          avatar,
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
                if (subtitle != null)
                  Text(
                    subtitle!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _AccountAvatar extends StatelessWidget {
  const _AccountAvatar({required this.session});

  final AccountSessionController session;

  @override
  Widget build(BuildContext context) {
    final initials = session.initials;
    if (initials.isNotEmpty) {
      return CircleAvatar(
        key: const Key('global-account-initials'),
        child: Text(initials),
      );
    }
    return const CircleAvatar(
      key: Key('global-account-generic-avatar'),
      child: Icon(Icons.person),
    );
  }
}
