"""Offline recovery and online SQLite backup; never overwrite existing stores."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import time


REQUIRED = frozenset({'gl_state', 'gl_releases', 'gl_candidates', 'gl_tasks',
                      'gl_outcomes', 'gl_events', 'gl_http_bindings'})


def _source(path):
    source = Path(path).resolve(strict=True)
    if not source.is_file():
        raise ValueError('existing database file required')
    return source


def _verify_connection(con):
    if [r[0] for r in con.execute('PRAGMA quick_check')] != ['ok']:
        raise ValueError('SQLite integrity check failed')
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not REQUIRED <= tables:
        raise ValueError('not a repository host database')
    # Logical routing/contract eligibility is separately checked by host --check.
    return {'integrity': 'ok', 'scopes': con.execute('SELECT COUNT(*) FROM gl_state').fetchone()[0]}


def verify_store(path):
    source = _source(path)
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=10)) as con:
        return _verify_connection(con)


def copy_store(source, destination, *, timeout=30):
    """Consistent backup to a new 0600 file, published atomically without clobber.

    Restore uses this same operation into a NEW offline destination. The caller
    must stop traffic and review freshness before switching the host to it.
    """
    source = _source(source)
    destination = Path(destination).absolute()
    if not destination.parent.is_dir() or destination.exists() or destination.is_symlink():
        raise FileExistsError('new destination in an existing directory required')
    if type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise ValueError('backup timeout must be between zero and 300 seconds')
    started = time.monotonic()
    def progress(status, remaining, total):
        if time.monotonic() - started > timeout:
            raise TimeoutError('backup time budget exceeded')
    fd, temporary = tempfile.mkstemp(prefix='.nerve-backup-', dir=destination.parent)
    os.close(fd)
    try:
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro', uri=True, timeout=10)) as origin:
            with closing(sqlite3.connect(temporary)) as target:
                origin.backup(target, pages=128, progress=progress, sleep=0.05)
                report = _verify_connection(target)
        with open(temporary, 'rb') as stream:
            os.fsync(stream.fileno())
        # Hard-link publication fails atomically if another writer creates target.
        os.link(temporary, destination)
        directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return {**report, 'published': True}
    finally:
        os.unlink(temporary)
