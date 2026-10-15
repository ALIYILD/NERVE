"""External associative memory with analytic MSE gradient; no hosted weights."""
import hashlib
import json
import numpy as np

VERSION='external-linear-memory-v1'
DIM=8


def vector(value):
    x=np.asarray(value,dtype=np.float64)
    if x.shape!=(DIM,) or not np.isfinite(x).all(): raise ValueError('finite eight-dimensional vector required')
    norm=np.linalg.norm(x)
    if norm==0: raise ValueError('nonzero vector required')
    return x/max(1.,norm)


class FastMemory:
    def __init__(self, *, learning_rate=.1, initial=None):
        if type(learning_rate) not in (int,float) or not np.isfinite(learning_rate) or not 0<learning_rate<=4:
            raise ValueError('learning rate must be finite and in (0,4]')
        self.learning_rate=learning_rate
        initial=np.zeros((DIM,DIM)) if initial is None else np.asarray(initial,dtype=np.float64)
        if initial.shape!=(DIM,DIM) or not np.isfinite(initial).all() or np.linalg.norm(initial)>8: raise ValueError('invalid initialization')
        self.initial=initial.copy(); self.initial.flags.writeable=False
        self.reset()

    def reset(self): self.weights=self.initial.copy()

    def read(self,query):
        if not np.isfinite(self.weights).all(): raise ValueError('nonfinite memory')
        return vector(query) @ self.weights

    def update(self,key,value, *, verified=False, valid=True):
        if type(verified) is not bool or type(valid) is not bool: raise ValueError('Boolean masks required')
        if not valid or not verified: return False
        k,v=vector(key),vector(value)
        if not np.isfinite(self.weights).all(): raise ValueError('nonfinite memory')
        gradient=2*np.outer(k,k@self.weights-v)/DIM
        change=-self.learning_rate*gradient
        change/=max(1.,np.linalg.norm(change))
        candidate=self.weights+change
        if not np.isfinite(candidate).all() or np.linalg.norm(candidate)>8: raise ValueError('update rejected; use structured evidence')
        self.weights=candidate
        return True

    def checkpoint(self):
        data={'version':VERSION,'learning_rate':self.learning_rate,'initial':self.initial.tolist(),'weights':self.weights.tolist()}
        encoded=json.dumps(data,sort_keys=True,allow_nan=False)
        return {'data':data,'sha256':hashlib.sha256(encoded.encode()).hexdigest()}

    @classmethod
    def restore(cls,artifact):
        data=artifact['data']; encoded=json.dumps(data,sort_keys=True,allow_nan=False)
        if hashlib.sha256(encoded.encode()).hexdigest()!=artifact['sha256'] or data['version']!=VERSION: raise ValueError('corrupt or incompatible checkpoint')
        memory=cls(learning_rate=data['learning_rate'],initial=data['initial'])
        weights=np.asarray(data['weights'],dtype=np.float64)
        if weights.shape!=(DIM,DIM) or not np.isfinite(weights).all() or np.linalg.norm(weights)>8: raise ValueError('invalid checkpoint weights')
        memory.weights=weights.copy()
        return memory
