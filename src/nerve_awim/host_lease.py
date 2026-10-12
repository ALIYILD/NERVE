"""Advisory single-service ownership for the local SQLite pilot.

This is a local process lease, not a distributed lock or SQLite transaction lock.
Never replace, unlink or restore over a database while its service is running.
"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import sys

# A stable root independent of TMPDIR ensures cooperating processes agree.
# Its owner and permissions are checked through an opened directory descriptor.
_LOCK_ROOT = Path('/tmp') / ('nerve-host-leases-' + str(os.getuid()))


def _darwin_lock(database_stat):
    """macOS flock conflicts with SQLite byte-range locks on the same inode."""
    try:
        _LOCK_ROOT.mkdir(mode=0o700)
    except FileExistsError:
        pass
    directory = os.open(_LOCK_ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(directory)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise PermissionError('private host lease directory required')
        name = f'{database_stat.st_dev}-{database_stat.st_ino}.lock'
        fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
                     0o600, dir_fd=directory)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise PermissionError('private regular host lease file required')
        except BaseException:
            os.close(fd)
            raise
        return fd
    finally:
        os.close(directory)


@contextmanager
def exclusive_host(database, *, create=False):
    """Hold ownership keyed by database inode until exit or crash.

    Linux locks the database itself. macOS locks a private file keyed by device
    and inode, so symlink/hardlink aliases still share ownership without blocking
    SQLite. Lock files persist: unlinking one could split competing owners.
    """
    path = Path(database).resolve()
    flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    if create:
        flags |= os.O_CREAT
    fd = os.open(path, flags, 0o600)
    lease_fd = fd
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('regular database required')
        if sys.platform == 'darwin':
            lease_fd = _darwin_lock(info)
        fcntl.flock(lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield path
    finally:
        if lease_fd != fd:
            os.close(lease_fd)
        os.close(fd)
