"""Joint slow projections/W0 learning with explicitly truncated reverse BPTT.

NumPy keeps research optional. These derivatives are checked against finite
 differences; there is no provider, robot action head, or clinical objective.
"""
import numpy as np
from .module import DIM, FastMemory, vector


def normalise(x):
    norm=np.linalg.norm(x)
    return x/max(1.,norm)


def normalise_backward(x,grad):
    norm=np.linalg.norm(x)
    if norm<=1.: return grad
    return grad/norm-x*np.dot(x,grad)/(norm**3)


class SequenceModel:
    def __init__(self,seed=1,parameters=None):
        rng=np.random.default_rng(seed)
        self.parameters={name:.8*np.eye(DIM)+rng.normal(0,.005,(DIM,DIM)) for name in ('key','query','value')}
        self.parameters['initial']=np.zeros((DIM,DIM))
        self.parameters['rate']=np.array(.8)
        if parameters is not None:
            if set(parameters)!=set(self.parameters): raise ValueError('exact slow parameters required')
            for name,value in parameters.items():
                arr=np.asarray(value,dtype=np.float64)
                shape=() if name=='rate' else (DIM,DIM)
                if arr.shape!=shape or not np.isfinite(arr).all() or np.linalg.norm(arr)>8: raise ValueError('invalid slow parameter')
                self.parameters[name]=arr.copy()
            if not .01<=self.parameters['rate']<=4: raise ValueError('invalid slow learning rate')

    def serialise(self): return {name:value.tolist() for name,value in self.parameters.items()}

    def memory(self):
        return FastMemory(learning_rate=float(self.parameters['rate']),initial=self.parameters['initial'])

    def read(self,memory,key): return memory.read(normalise(key@self.parameters['query']))
    def write(self,memory,key,value): return memory.update(normalise(key@self.parameters['key']),normalise(value@self.parameters['value']),verified=True)

    def gradients(self,examples,segment=16):
        if type(segment) is not int or segment<1: raise ValueError('positive segment length required')
        p=self.parameters; w=p['initial'].copy(); gradients={n:np.zeros_like(v) for n,v in p.items()}; loss=0.; count=0; eye=np.eye(DIM)
        for boundary in range(0,len(examples),segment):
            cache=[]
            for event in examples[boundary:boundary+segment]:
                if not event['valid']: continue
                z,y=eye[event['key']],eye[event['target']]
                kr,qr,vr=z@p['key'],z@p['query'],y@p['value']
                k,q,v=normalise(kr),normalise(qr),normalise(vr)
                pred=q@w
                if event['supervise']:
                    loss+=np.mean((pred-y)**2); count+=1
                alpha=float(p['rate'])*2/DIM
                raw=alpha*np.outer(k,v-k@w) if event['update'] else np.zeros_like(w)
                change=raw/max(1.,np.linalg.norm(raw))
                cache.append((w.copy(),z,y,kr,qr,vr,k,q,v,pred,event,raw))
                w=w+change
                if not np.isfinite(w).all() or np.linalg.norm(w)>8: raise ValueError('training state outside numerical bound')
            # No gradient enters from later segments: numerical state is carried,
            # reverse derivative is detached at each segment boundary.
            gw=np.zeros_like(w)
            for old,z,y,kr,qr,vr,k,q,v,pred,event,raw in reversed(cache):
                current=gw.copy()
                if event['update']:
                    norm=np.linalg.norm(raw)
                    # Jacobian of Frobenius norm clipping on the update.
                    graw=gw if norm<=1 else gw/norm-raw*np.sum(raw*gw)/(norm**3)
                    residual=v-k@old
                    alpha=float(p['rate'])*2/DIM
                    gradients['rate']+=np.sum(graw*np.outer(k,residual))*2/DIM
                    gk=alpha*(graw@residual-old@(graw.T@k))
                    gv=alpha*(k@graw)
                    current-=alpha*np.outer(k,k@graw)
                    gradients['key']+=np.outer(z,normalise_backward(kr,gk))
                    gradients['value']+=np.outer(y,normalise_backward(vr,gv))
                if event['supervise']:
                    error=2*(pred-y)/DIM
                    current+=np.outer(q,error)
                    gradients['query']+=np.outer(z,normalise_backward(qr,old@error))
                gw=current
            if boundary==0: gradients['initial']+=gw
        return loss/max(count,1),{n:g/max(count,1) for n,g in gradients.items()}

    def optimize(self,gradients,step=.5):
        for name,grad in gradients.items():
            if not np.isfinite(grad).all(): raise ValueError('nonfinite slow gradient')
            proposed=self.parameters[name]-step*grad/max(1.,np.linalg.norm(grad))
            if name=='rate': proposed=np.clip(proposed,.01,4.)
            else: proposed=proposed/max(1.,np.linalg.norm(proposed)/7.)
            self.parameters[name]=np.asarray(proposed)
