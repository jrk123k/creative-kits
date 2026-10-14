"""Small ** glob matcher. Matching is case-insensitive."""

from __future__ import annotations

import re

_CACHE: dict[str, re.Pattern[str]] = {}


def glob_match(path: str, pattern: str) -> bool:
    """Return True if a relative posix path matches a glob.

    ``*`` stays inside one path segment. ``**`` crosses directories.
    ``a/**`` matches everything under ``a/``, including nested files.
    """
    path = path.replace("\\", "/").lstrip("./")
    return _compile(pattern).fullmatch(path.lower()) is not None


def _compile(pattern: str) -> re.Pattern[str]:
    key = pattern.replace("\\", "/")
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    src = key.lower()
    i = 0
    parts = ["^"]
    while i < len(src):
        if src.startswith("**/", i):
            parts.append("(?:.*/)?")
            i += 3
        elif src.startswith("**", i):
            parts.append(".*")
            i += 2
        elif src[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif src[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(src[i]))
            i += 1
    parts.append("$")
    compiled = re.compile("".join(parts))
    _CACHE[key] = compiled
    return compiled
