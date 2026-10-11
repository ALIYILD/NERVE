"""Advisory single-service ownership for the Linux SQLite pilot.

This is a local process lease, not a distributed lock or SQLite transaction lock.
Never replace, unlink or restore over a database while its service is running.
"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat


@contextmanager
def exclusive_host(database, *, create=False):
    """Hold the database inode for one cooperating service until exit or crash."""
    path = Path(database).resolve()
    flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    if create:
        flags |= os.O_CREAT
    fd = os.open(path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('regular database required')
        # No unlinkable sidecar: path aliases to the same inode share ownership.
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield path
    finally:
        os.close(fd)
