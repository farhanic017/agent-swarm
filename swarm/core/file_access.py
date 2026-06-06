from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable


class FileAccessDenied(PermissionError):
    """Raised when an agent tries to access a path outside its allowed roots."""


DENIED_NAMES = {
    ".env",
    ".netrc",
    "config.json",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}

DENIED_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
DENIED_PARTS = {".git", ".ssh", ".aws", ".azure", ".gnupg"}


def default_allowed_roots() -> list[Path]:
    configured = os.environ.get("AGENT_SWARM_ALLOWED_ROOTS", "")
    roots = [item.strip() for item in configured.split(os.pathsep) if item.strip()]
    if not roots:
        roots = [str(Path.cwd())]
    return [Path(root).expanduser().resolve() for root in roots]


def assert_allowed_path(
    path: str | os.PathLike[str],
    operation: str,
    allowed_roots: Iterable[str | os.PathLike[str]] | None = None,
) -> Path:
    target = Path(path).expanduser()
    resolved = target.resolve(strict=False)
    roots = [
        Path(root).expanduser().resolve(strict=False)
        for root in (allowed_roots if allowed_roots is not None else default_allowed_roots())
    ]
    if not roots:
        raise FileAccessDenied(f"{operation} denied: no allowed roots configured")

    if not any(_is_relative_to(resolved, root) for root in roots):
        root_text = ", ".join(str(root) for root in roots)
        raise FileAccessDenied(f"{operation} denied for {resolved}; allowed roots: {root_text}")

    _assert_not_sensitive(resolved, operation)
    return resolved


def secure_read_file(path: str) -> str:
    target = assert_allowed_path(path, "read")
    if not target.is_file():
        raise FileNotFoundError(str(target))
    return target.read_text(encoding="utf-8")


def secure_write_file(path: str, content: str) -> str:
    target = assert_allowed_path(path, "write")
    if not target.parent.exists():
        raise FileNotFoundError(str(target.parent))
    target.write_text(content, encoding="utf-8")
    return f"Written to {target}"


def secure_list_directory(path: str) -> str:
    target = assert_allowed_path(path, "list")
    if not target.is_dir():
        raise NotADirectoryError(str(target))
    return json.dumps([str(item) for item in sorted(target.iterdir())], indent=2)


def describe_file_access_policy() -> dict:
    return {
        "allowed_roots": [str(root) for root in default_allowed_roots()],
        "env": "AGENT_SWARM_ALLOWED_ROOTS",
        "denied_names": sorted(DENIED_NAMES),
        "denied_suffixes": list(DENIED_SUFFIXES),
        "denied_parts": sorted(DENIED_PARTS),
        "policy": "File tools resolve paths and block reads/writes/lists outside allowed roots or inside sensitive credential locations.",
    }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _assert_not_sensitive(path: Path, operation: str) -> None:
    parts = {part.lower() for part in path.parts}
    if DENIED_PARTS & parts:
        raise FileAccessDenied(f"{operation} denied for sensitive path {path}")
    name = path.name.lower()
    if name in DENIED_NAMES or name.startswith(".env.") or name.endswith(DENIED_SUFFIXES):
        raise FileAccessDenied(f"{operation} denied for sensitive file {path}")
