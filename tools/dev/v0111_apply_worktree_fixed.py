#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

script = Path(__file__).with_name('v0111_apply_worktree.py')
spec = importlib.util.spec_from_file_location('v0111_apply_worktree', script)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original = module.replace_once


def replace_once(path: str, old: str, new: str) -> None:
    if old == '___never___':
        return
    original(path, old, new)


module.replace_once = replace_once
module.main()
