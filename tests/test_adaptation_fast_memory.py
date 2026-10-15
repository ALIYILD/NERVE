import importlib.util
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

@unittest.skipUnless(importlib.util.find_spec('numpy'),'optional research NumPy unavailable')
class FastMemoryTests(unittest.TestCase):
    def test_recall_reset_and_checkpoint(self):
        import numpy as np
        from research.fast_weight_memory.module import FastMemory
        m=FastMemory(learning_rate=4); eye=np.eye(8); mapping=np.random.default_rng(85).permutation(8)
        for k,v in enumerate(mapping): m.update(eye[k],eye[v],verified=True)
        self.assertEqual(sum(np.argmax(m.read(eye[k]))==v for k,v in enumerate(mapping)),8)
        clone=FastMemory.restore(m.checkpoint()); np.testing.assert_equal(clone.weights,m.weights)
        m.reset(); self.assertFalse(m.weights.any()); self.assertTrue(clone.weights.any())
        artifact=clone.checkpoint(); artifact['data']['weights'][0][0]=float('nan')
        with self.assertRaises(ValueError): FastMemory.restore(artifact)
    def test_masks_nonfinite_and_bound(self):
        import numpy as np
        from research.fast_weight_memory.module import FastMemory
        m=FastMemory(learning_rate=4); e=np.eye(8)
        self.assertFalse(m.update(e[0],e[1],verified=False)); self.assertFalse(m.weights.any())
        self.assertFalse(m.update([float('nan')]*8,e[1],verified=True,valid=False))
        with self.assertRaises(ValueError): m.update([float('nan')]*8,e[1],verified=True)
        before=m.weights.copy(); m.update(e[0],e[1],verified=True)
        self.assertLessEqual(np.linalg.norm(m.weights-before),1.)
    def test_gradient_and_padding(self):
        from research.fast_weight_memory.experiment import sequence,train_step
        examples=sequence(4,12); rate=.4; epsilon=1e-5
        loss,g=train_step(examples,rate,segment=16)
        numeric=(train_step(examples,rate+epsilon,segment=16)[0]-train_step(examples,rate-epsilon,segment=16)[0])/(2*epsilon)
        self.assertAlmostEqual(g,numeric,places=7)
        padded=examples+[dict(key=999,target=999,valid=False,update=True,supervise=True)]
        self.assertEqual((loss,g),train_step(padded,rate,segment=16))
        self.assertEqual(train_step(examples,rate,segment=1)[1],0.)
    def test_no_label_leak_and_budgets(self):
        import numpy as np
        from research.fast_weight_memory.module import FastMemory
        from research.fast_weight_memory.experiment import train,validate_budget
        m=FastMemory(); before=m.read(np.eye(8)[0]).copy(); m.update(np.eye(8)[0],np.eye(8)[4],verified=True)
        self.assertFalse(before.any())
        with self.assertRaises(ValueError): validate_budget({})
        with self.assertRaises(ValueError): train(dict(seed=1,epochs=100,episodes=100,length=100,segment=16),dict(max_seconds=60,max_epochs=100,max_events=100,device='cpu'))
    def test_joint_projection_gradients_and_episode_reset(self):
        import numpy as np
        from research.fast_weight_memory.sequence_model import SequenceModel
        from research.fast_weight_memory.experiment import sequence
        model=SequenceModel(71); examples=sequence(31,12)
        loss,grad=model.gradients(examples,segment=16)
        self.assertEqual(loss,model.gradients(examples,segment=16)[0])
        epsilon=1e-5
        for name in model.parameters:
            indices=[()] if name=='rate' else [(0,0),(1,3),(4,2)]
            for index in indices:
                old=model.parameters[name][index].copy()
                model.parameters[name][index]=old+epsilon; plus=model.gradients(examples,segment=16)[0]
                model.parameters[name][index]=old-epsilon; minus=model.gradients(examples,segment=16)[0]
                model.parameters[name][index]=old
                self.assertAlmostEqual(grad[name][index],(plus-minus)/(2*epsilon),places=7,msg=name)
        padded=examples+[dict(key=999,target=999,valid=False,update=True,supervise=True)]
        self.assertEqual(loss,model.gradients(padded,segment=16)[0])
        m1=model.memory(); m2=model.memory(); model.write(m1,np.eye(8)[0],np.eye(8)[2]); np.testing.assert_equal(m2.weights,model.parameters['initial'])
