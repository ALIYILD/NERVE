"""Separately administered state with hash-chained audit and protected anchor.

The anchor must live outside the monitored application's write boundary. A crash
between database commit and anchor replacement is deliberately detected, not healed
by trusting the database. Operator recovery requires independent evidence.
"""
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from contextlib import contextmanager


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class IntegrityError(RuntimeError):
    pass


class Store:
    def __init__(self, directory, anchor_directory=None, clock=time.time):
        self.directory=Path(directory)
        self.anchor_directory=Path(anchor_directory or directory)
        for path in (self.directory,self.anchor_directory):
            if path.is_symlink(): raise IntegrityError('symlink state directory')
            path.mkdir(parents=True,exist_ok=True,mode=0o700)
            if path.stat().st_mode & 0o077: raise IntegrityError('state directory must be private')
        self.path=self.directory/'guardian.sqlite3'
        self.anchor=self.anchor_directory/'guardian-anchor.json'
        self.clock=clock; self.lock=threading.RLock()
        if self.path.is_symlink() or self.anchor.is_symlink(): raise IntegrityError('symlink state')
        with self.locked():
            existed=self.path.exists()
            if existed != self.anchor.exists(): raise IntegrityError('state or anchor missing')
            with self.db() as con:
                if not existed:
                    con.executescript('''CREATE TABLE state(id INTEGER PRIMARY KEY CHECK(id=1),document TEXT NOT NULL);
                    CREATE TABLE audit(sequence INTEGER PRIMARY KEY,record TEXT NOT NULL,hash TEXT NOT NULL);
                    CREATE TRIGGER audit_immutable BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'immutable'); END;
                    CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'immutable'); END;''')
                    con.execute('INSERT INTO state VALUES(1,?)',(canonical({'incidents':{},'requests':{},'tokens':{},'notifications':{}}),))
                    con.commit(); self._anchor(con)
                self._verify(con)
            os.chmod(self.path,0o600)

    @contextmanager
    def locked(self):
        with self.lock:
            fd=os.open(self.directory/'state.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
            try:
                fcntl.flock(fd,fcntl.LOCK_EX);yield
            finally:
                fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)

    @contextmanager
    def db(self):
        con=None
        try:
            con=sqlite3.connect(self.path,timeout=3)
            con.row_factory=sqlite3.Row
            with con:yield con
        except PermissionError:
            raise
        except (sqlite3.Error,OSError) as error:
            raise IntegrityError('state storage unavailable') from error
        finally:
            if con is not None:con.close()

    def _value(self,con):
        state=json.loads(con.execute('SELECT document FROM state WHERE id=1').fetchone()[0])
        head=con.execute('SELECT sequence,hash FROM audit ORDER BY sequence DESC LIMIT 1').fetchone()
        return {'sequence':head['sequence'] if head else 0,'head':head['hash'] if head else '0'*64,'state':digest(state)}

    def _anchor(self,con):
        value=canonical(self._value(con)).encode()
        temp=self.anchor.with_suffix('.pending')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'wb') as out:out.write(value);out.flush();os.fsync(out.fileno())
            os.replace(temp,self.anchor)
            directory=os.open(self.anchor_directory,os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
        finally:
            if temp.exists():temp.unlink()

    def _verify(self,con):
        try:
            expected=json.loads(self.anchor.read_text())
            if expected!=self._value(con):raise IntegrityError('audit anchor mismatch')
            previous='0'*64
            for sequence,row in enumerate(con.execute('SELECT * FROM audit ORDER BY sequence'),1):
                record=json.loads(row['record'])
                if row['sequence']!=sequence or record['previous']!=previous or digest(record)!=row['hash']:
                    raise IntegrityError('audit chain mismatch')
                previous=row['hash']
        except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as error:
            raise IntegrityError('audit unavailable') from error

    def read(self):
        with self.locked(),self.db() as con:
            self._verify(con)
            return json.loads(con.execute('SELECT document FROM state WHERE id=1').fetchone()[0])

    def change(self,tenant,kind,operation):
        with self.locked(),self.db() as con:
            self._verify(con);con.execute('BEGIN IMMEDIATE')
            state=json.loads(con.execute('SELECT document FROM state WHERE id=1').fetchone()[0])
            result=operation(state)
            head=self._value(con)
            record={'sequence':head['sequence']+1,'previous':head['head'],'tenant':tenant,'kind':kind,'timestamp':self.clock(),'state_digest':digest(state)}
            con.execute('UPDATE state SET document=? WHERE id=1',(canonical(state),))
            con.execute('INSERT INTO audit VALUES(?,?,?)',(record['sequence'],canonical(record),digest(record)))
            con.commit();self._anchor(con)
            return copy.deepcopy(result)

    def audit(self,tenant):
        with self.locked(),self.db() as con:
            self._verify(con)
            return [json.loads(r[0]) for r in con.execute('SELECT record FROM audit') if json.loads(r[0])['tenant']==tenant]
