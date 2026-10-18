"""Trusted source editing with revision checks, atomic writes and preserved originals."""

import hashlib
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path


class SourceConflict(ValueError):
    """Another editor changed the source; the caller must reload or save a copy."""


def source_path(root, filename):
    root = Path(root).resolve()
    if not isinstance(filename, str) or not re.fullmatch(
        r"[a-zA-Z_][a-zA-Z0-9_]{0,79}\.py", filename
    ):
        raise ValueError("Use a Python file name without directories")
    if filename == "__init__.py":
        raise ValueError("The catalog registry cannot be edited as a strategy")
    path = root / filename
    if path.is_symlink() or path.resolve().parent != root:
        raise ValueError("Source file must belong to the configured catalog")
    return path


def read_source(root, filename):
    path = source_path(root, filename)
    raw = path.read_bytes()
    if len(raw) > 256 * 1024:
        raise ValueError("Strategy source exceeds 256 KiB")
    return {
        "filename": filename,
        "source": raw.decode("utf-8-sig"),
        "revision": hashlib.sha256(raw).hexdigest(),
    }


@contextmanager
def edit_lock(root):
    # A process crash releases the OS lock. No stale lock deletion or optimistic overwrite.
    with (Path(root) / ".strategy-edit.lock").open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            if stream.tell() == 0:
                stream.write(b"0")
            stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def save_source(root, filename, source, expected_revision=None):
    path = source_path(root, filename)
    if not isinstance(source, str) or not source.strip() or len(source.encode()) > 256 * 1024:
        raise ValueError("Nonempty strategy source must fit 256 KiB")
    compile(source, filename, "exec")
    raw = source.encode("utf-8")
    with edit_lock(path.parent):
        previous = path.read_bytes() if path.exists() else None
        mode = path.stat().st_mode & 0o777 if previous is not None else 0o644
        actual = hashlib.sha256(previous).hexdigest() if previous is not None else None
        if actual != expected_revision:
            raise SourceConflict("Source changed in another editor; reload it or save a copy")
        if previous is not None:
            history = path.parent / ".history" / path.stem
            if not history.resolve().is_relative_to(path.parent):
                raise ValueError("Source history must remain inside the configured catalog")
            history.mkdir(parents=True, exist_ok=True)
            backup = history / f"{actual}.py"
            if not backup.exists():
                with backup.open("xb") as stream:
                    stream.write(previous)
                    stream.flush()
                    os.fsync(stream.fileno())
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".strategy-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            if os.name != "nt":
                os.chmod(temporary, mode)
            os.replace(temporary, path)
            if os.name != "nt":
                descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
    return {"filename": filename, "revision": hashlib.sha256(raw).hexdigest()}
