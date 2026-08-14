# MusicArk Product Scope

## Current product scope: v0.3

The current usable product is a desktop cache-first Yandex Music library.

Included:

- secure persistent Yandex session;
- account information;
- Liked collection;
- user playlist metadata;
- opening one playlist and reading its ordered tracks;
- local snapshots and offline fallback;
- search and simple sorting;
- current-collection refresh and full library metadata refresh;
- logout cleanup.

## Explicitly out of v0.3

- standalone Python packaging or installer;
- local folder scanner;
- Yandex ↔ local matching;
- missing-track analysis;
- download system;
- sync planner UI;
- metadata editor;
- playback/player;
- Yandex playlist creation/editing/upload;
- destructive local-file operations.

These belong to later roadmap stages and must not be pulled into v0.3 opportunistically.

## Success scenario

Launch → saved session → cached Likes + playlist list → open real playlist → cached/network tracks → search/sort → refresh → restart → offline cached access → logout.
