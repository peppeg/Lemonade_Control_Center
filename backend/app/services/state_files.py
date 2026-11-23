"""Private, crash-safe files for the state LCC keeps under its data directory."""
from __future__ import annotations

import contextlib
import logging
import os
import tempfile
from itertools import pairwise
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
_SHARED_BITS = 0o077


def write_private_text(path: Path, text: str) -> None:
    """Replace a file in one step, readable by its owner only.

    A crash or a full disk leaves the previous content in place. A symbolic link
    keeps pointing to the same file.
    """
    target = Path(os.path.realpath(path))
    ensure_private_dir(target.parent)
    # mkstemp() creates the file with mode 0600.
    descriptor, temporary = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise


def append_private_line(path: Path, line: str, *, max_bytes: int, backups: int) -> None:
    """Append a line to a log readable by its owner only, rotating it by size."""
    ensure_private_dir(path.parent)
    try:
        _rotate(path, max_bytes=max_bytes, backups=backups)
    except OSError as error:
        # Keep the record: an oversized log is better than a missing entry.
        logger.warning("Could not rotate %s: %s", path.name, error)
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, PRIVATE_FILE_MODE)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _rotate(path: Path, *, max_bytes: int, backups: int) -> None:
    """Move path to path.1, path.1 to path.2 and so on, dropping the oldest."""
    if not path.exists() or path.stat().st_size < max_bytes:
        return
    files = [path, *(path.with_name(f"{path.name}.{index}") for index in range(1, backups + 1))]
    for newer, older in reversed(list(pairwise(files))):
        if newer.exists():
            os.replace(newer, older)


def ensure_private_dir(path: Path) -> None:
    """Create a directory and its missing parents with mode 0700."""
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=PRIVATE_DIR_MODE, exist_ok=True)


def protect_data_dir(data_dir: Path = DATA_DIR) -> None:
    """Create the data directory, or tighten one left by an earlier version.

    The directory mode is what keeps other users out. The configuration holds
    Lemonade keys, so it is tightened as well in case the directory is opened up.
    """
    try:
        ensure_private_dir(data_dir)
    except OSError as error:
        logger.warning("Could not create the data directory %s: %s", data_dir, error)
        return
    for path, mode in ((data_dir, PRIVATE_DIR_MODE), (data_dir / "config.json", PRIVATE_FILE_MODE)):
        try:
            if path.exists() and path.stat().st_mode & _SHARED_BITS:
                path.chmod(mode)
        except OSError as error:
            logger.warning("Could not restrict access to %s: %s", path, error)
