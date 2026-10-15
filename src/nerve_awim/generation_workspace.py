"""Host-reviewed text artifacts; same memory authority, no execution or scheduler.

Caller controls reviewed manifest and filesystem roots. Same-user hostile processes
or writers controlling the SQLite database are outside this local trust boundary.
Public/synthetic declarations and secret screening are not a patient-data detector.
"""
import ctypes
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import PurePosixPath
import re
import sqlite3
import stat
import sys
import time
import uuid

from .generation_memory import GenerationMemory, _json, _digest
from .memory_v18 import _id, _PLACEHOLDER


def _parts(path):
    if (type(path) is not str or len(path)>240 or not path or '\\' in path
            or any(p in ('', '.', '..') or p.startswith('.') for p in path.split('/'))
            or not re.fullmatch(r'[A-Za-z0-9_./-]+',path)):
        raise ValueError('safe relative artifact path required')
    parts=path.split('/')
    if len(parts)>8 or PurePosixPath(path).suffix.lower() not in ('.txt','.md','.json','.csv'):
        raise ValueError('bounded text artifact required')
    if any(re.search(r'credential|secret|token|password|private|patient|medical|id_rsa|id_ed25519',p,re.I) for p in parts):
        raise ValueError('sensitive artifact path denied')
    return parts


def _directory(path):
    """Open each component without following links, including the root argument."""
    path=os.fspath(path)
    if not os.path.isabs(path) or '..' in path.split('/'):
        raise ValueError('host must supply an absolute non-traversing root')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in path.split('/'):
            if not part:continue
            next_fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=next_fd
        return fd
    except BaseException:
        os.close(fd);raise


def _read(root,parts):
    fd=os.dup(root)
    try:
        for part in parts[:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=child
        file_fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        try:
            before=os.fstat(file_fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>65536:
                raise ValueError('single-link bounded regular file required')
            raw=b''
            while len(raw)<=65536:
                chunk=os.read(file_fd,min(8192,65537-len(raw)))
                if not chunk:break
                raw+=chunk
            after=os.fstat(file_fd)
            if len(raw)>65536 or (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns) or after.st_nlink!=1:
                raise ValueError('source changed or exceeded bound')
            text=raw.decode('utf-8')
            if '\x00' in text or _PLACEHOLDER.search(text):raise ValueError('secret or nontext artifact denied')
            return text
        finally:os.close(file_fd)
    finally:os.close(fd)


def _cleanup(parent,name):
    fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
    try:
        for child in os.listdir(fd):
            info=os.stat(child,dir_fd=fd,follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):_cleanup(fd,child)
            else:os.unlink(child,dir_fd=fd)
    finally:os.close(fd)
    os.rmdir(name,dir_fd=parent)


def _rename_exclusive(fd,source,target):
    libc=ctypes.CDLL(None,use_errno=True)
    if sys.platform=='darwin':
        fn=libc.renameatx_np;flag=4
    elif sys.platform.startswith('linux'):
        fn=libc.renameat2;flag=1
    else:raise RuntimeError('atomic exclusive directory rename unsupported')
    fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    fn.restype=ctypes.c_int
    if fn(fd,os.fsencode(source),fd,os.fsencode(target),flag):
        error=ctypes.get_errno();raise OSError(error,os.strerror(error))


class GenerationWorkspace:
    def __init__(self,memory):
        if not isinstance(memory,GenerationMemory):raise TypeError('existing generation memory required')
        self.memory=memory
        with sqlite3.connect(memory.ledger.path) as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS generation_artifacts(id TEXT PRIMARY KEY,tenant TEXT,agent TEXT,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS generation_artifact_revocations(id TEXT PRIMARY KEY,review_id TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS artifact_no_update BEFORE UPDATE ON generation_artifacts BEGIN SELECT RAISE(ABORT,'immutable artifact'); END;
            CREATE TRIGGER IF NOT EXISTS artifact_no_delete BEFORE DELETE ON generation_artifacts BEGIN SELECT RAISE(ABORT,'immutable artifact'); END;
            CREATE TRIGGER IF NOT EXISTS artifact_revocation_no_update BEFORE UPDATE ON generation_artifact_revocations BEGIN SELECT RAISE(ABORT,'immutable revocation'); END;
            CREATE TRIGGER IF NOT EXISTS artifact_revocation_no_delete BEFORE DELETE ON generation_artifact_revocations BEGIN SELECT RAISE(ABORT,'immutable revocation'); END;
            ''')

    def capture(self,actor,scope,*,snapshot_id,source_root,reviewed_manifest):
        self.memory._scope(actor,scope,'approve')
        self.memory.handoff(actor,snapshot_id,scope)
        manifest=json.loads(_json(reviewed_manifest))
        if type(manifest) is not dict or set(manifest)!={'review_id','files'}:
            raise ValueError('exact reviewed manifest required')
        _id(manifest['review_id'],'review')
        if type(manifest['files']) is not list or not 1<=len(manifest['files'])<=8:raise ValueError('bounded file list required')
        records=[];seen=set();total=0
        root=_directory(source_root)
        try:
            for item in manifest['files']:
                if (type(item) is not dict or set(item)!={'path','sha256','data_class'}
                        or item['data_class'] not in ('public','synthetic')
                        or type(item['sha256']) is not str or not re.fullmatch('[a-f0-9]{64}',item['sha256'])):
                    raise ValueError('explicit reviewed file and digest required')
                parts=_parts(item['path'])
                if item['path'] in seen:raise ValueError('duplicate artifact path')
                seen.add(item['path'])
                text=_read(root,parts);raw=text.encode();total+=len(raw)
                if sha256(raw).hexdigest()!=item['sha256'] or total>262144:raise ValueError('artifact hash or total budget mismatch')
                records.append(dict(item,text=text))
        finally:os.close(root)
        value=dict(version=1,tenant=actor.tenant_id,agent=actor.agent_id,scope=asdict(scope),snapshot_id=snapshot_id,
                   review_id=manifest['review_id'],files=records,authorization_granted=False)
        ident=_digest(value)
        with sqlite3.connect(self.memory.ledger.path) as db:
            db.execute('BEGIN IMMEDIATE')
            self.memory._load(db,actor,snapshot_id,scope,int(time.time()),set())
            db.execute('INSERT OR IGNORE INTO generation_artifacts VALUES(?,?,?,?)',(ident,actor.tenant_id,actor.agent_id,_json(value)))
        return ident

    def _load(self,db,actor,scope,artifact_id):
        if type(artifact_id) is not str or not re.fullmatch('[a-f0-9]{64}',artifact_id):raise ValueError('invalid artifact ID')
        row=db.execute('SELECT payload FROM generation_artifacts WHERE id=? AND tenant=? AND agent=?',(artifact_id,actor.tenant_id,actor.agent_id)).fetchone()
        if not row:raise LookupError('artifact not found in scope')
        if db.execute('SELECT 1 FROM generation_artifact_revocations WHERE id=?',(artifact_id,)).fetchone():raise ValueError('artifact revoked')
        value=json.loads(row[0])
        if _digest(value)!=artifact_id or value['scope']!=asdict(scope) or value['tenant']!=actor.tenant_id or value['agent']!=actor.agent_id:
            raise ValueError('artifact binding drift')
        self.memory._load(db,actor,value['snapshot_id'],scope,int(time.time()),set())
        return value

    def revoke(self,actor,scope,*,artifact_id,review_id):
        self.memory._scope(actor,scope,'approve');_id(review_id,'review')
        with sqlite3.connect(self.memory.ledger.path) as db:
            # Revocation must remain possible even after note expiry/revocation.
            row=db.execute('SELECT payload FROM generation_artifacts WHERE id=? AND tenant=? AND agent=?',(artifact_id,actor.tenant_id,actor.agent_id)).fetchone()
            if not row or json.loads(row[0])['scope']!=asdict(scope):raise LookupError('artifact not found in scope')
            db.execute('INSERT OR IGNORE INTO generation_artifact_revocations VALUES(?,?)',(artifact_id,review_id))

    def restore(self,actor,scope,*,artifact_id,destination_parent,directory_name):
        self.memory._scope(actor,scope,'read')
        if type(directory_name) is not str or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,63}',directory_name):raise ValueError('new isolated directory name required')
        root=_directory(destination_parent);stage='generation-stage-'+uuid.uuid4().hex
        made=False
        try:
            with sqlite3.connect(self.memory.ledger.path) as db:
                # Prevent concurrent ledger revocation between validation and publish.
                db.execute('BEGIN IMMEDIATE')
                value=self._load(db,actor,scope,artifact_id)
                os.mkdir(stage,0o700,dir_fd=root);made=True
                stage_fd=os.open(stage,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=root)
                try:
                    for item in value['files']:
                        parts=_parts(item['path']);fd=os.dup(stage_fd)
                        try:
                            for part in parts[:-1]:
                                try:os.mkdir(part,0o700,dir_fd=fd)
                                except FileExistsError:pass
                                child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
                            raw=item['text'].encode()
                            if sha256(raw).hexdigest()!=item['sha256']:raise ValueError('captured content drift')
                            out=os.open(parts[-1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=fd)
                            with os.fdopen(out,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                        finally:os.close(fd)
                    self._load(db,actor,scope,artifact_id)
                    _rename_exclusive(root,stage,directory_name);made=False
                finally:os.close(stage_fd)
            return dict(artifact_id=artifact_id,snapshot_id=value['snapshot_id'],directory_name=directory_name,file_count=len(value['files']),authorization_granted=False)
        finally:
            try:
                if made:_cleanup(root,stage)
            finally:os.close(root)
