import importlib.util
from pathlib import Path
import sys

import numpy as np
from core import Bundle


bundle = Bundle(sys.argv[1])
mesh = bundle.Meshes[0]
previous = Path(__file__).resolve().parent.parent / 'ClothingMeshEditor_0.4_Portable/core.py'
spec = importlib.util.spec_from_file_location('previous_core', previous)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
before, _ = module.Mesh.Simplify(mesh, 10000, 0.01, 0, 0)
regular, _ = mesh.Simplify(10000, 0.01, 0, 0)
assert all(np.array_equal(a, b) for a, b in zip(before, regular))
aggressive, _ = mesh.Simplify(10000, 0.01, 0, 0, True)
protected, _ = mesh.Simplify(10000, 0.01, 0, 75, True)
assert sum(map(len, aggressive)) < sum(map(len, regular))
assert sum(map(len, protected)) >= sum(map(len, aggressive))
used = np.unique(np.concatenate(protected))
locks = mesh.DetailLocks(75)
referenced = np.unique(np.concatenate(mesh.Parts))
required = {tuple(p) for p in mesh.Positions[referenced[locks[referenced] != 0]]}
remaining = {tuple(p) for p in mesh.Positions[used]}
assert required <= remaining
again, _ = mesh.Simplify(10000, 0.01, 0, 0, False)
assert all(np.array_equal(a, b) for a, b in zip(again, regular))
for label, parts in [('Regular', regular), ('Aggressive', aggressive), ('Aggressive + protection 75', protected)]:
    print(label, sum(map(len, parts)) // 3, flush=True)
print('PASS: off matches v0.4; on reduces further; protected positions survive; switching off restores original behavior.')
