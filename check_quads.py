import numpy as np
from viewer import QuadEdges

positions = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], np.float32)
triangles = np.array([0, 1, 2, 0, 2, 3], np.uint32)
original = triangles.copy()
edges = QuadEdges(positions, triangles).reshape(-1, 2)
assert {tuple(e) for e in edges} == {(0, 1), (1, 2), (2, 3), (0, 3)}
assert np.array_equal(original, triangles)
assert len(QuadEdges(positions, triangles[:3])) == 6
bent = positions.copy()
bent[3] = [0, 0, 1]
assert len(QuadEdges(bent, triangles)) == 10
assert len(QuadEdges(positions, np.array([], np.uint32))) == 0
nonmanifold = np.concatenate((triangles, triangles[:3]))
assert len(QuadEdges(positions, nonmanifold)) == 10
print('PASS: quad diagonal removed; boundaries, sharp folds, lone triangles and nonmanifold edges retained; source indices unchanged.')
