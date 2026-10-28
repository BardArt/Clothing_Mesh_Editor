import sys
from pathlib import Path

import numpy as np
from core import Bundle, Pieces, Reversed

# check_flip.py <bundle> <new output folder>
# 1. Turns every other piece of every mesh (the first mesh also simplified), exports, reopens and compares
#    each vertex stream, morph and triangle with the source.
# 2. Turns the pieces Outward() finds facing inward, exports, reopens: Outward() then finds none.
source = Bundle(sys.argv[1])
output = Path(sys.argv[2]).resolve()
for mesh in source.Meshes:
    assert not mesh.Changed()
    _, remap = np.unique(mesh.Positions, axis=0, return_inverse=True)
    remap = remap.ravel()
    labels = Pieces(remap[np.concatenate(mesh.Parts)].reshape(-1, 3), remap.max() + 1)
    pieces = np.unique(labels[remap[np.concatenate(mesh.Parts)]])
    mesh.Flip = np.isin(labels, pieces[::2])[remap] if len(pieces) > 1 else np.ones(len(mesh.Positions), bool)
    assert mesh.Changed()
first = source.Meshes[0]
first.Current, _ = first.Simplify(first.Triangles(True) // 2, .01, 0, 0)
path, size = source.Export(output / source.Path.parent.name)
result = Bundle(Path(path) / source.Path.name)


def Shapes(tree, used=None):
    shapes = tree.get('m_Shapes', {})
    rows = {}
    for s, shape in enumerate(shapes.get('shapes', [])):
        for v in shapes['vertices'][shape['firstVertex']:shape['firstVertex'] + shape['vertexCount']]:
            index = v['index'] if used is None else int(np.searchsorted(used, v['index']))
            if used is not None and (index >= len(used) or used[index] != v['index']):
                continue
            rows[(s, index)] = [v[field][axis] for field in ('vertex', 'normal', 'tangent') for axis in 'xyz']
    return rows


for before, after in zip(source.Meshes, result.Meshes):
    used = np.unique(np.concatenate(before.Current))
    turned = before.Flip[used]
    assert np.array_equal(after.Positions, before.Positions[used])
    assert np.array_equal(after.UV, before.UV[used])
    assert np.array_equal(after.Normals, np.where(turned[:, None], -before.Normals[used], before.Normals[used]))
    if before.Handler.m_Tangents:
        old = np.asarray(before.Handler.m_Tangents, np.float32)[used]
        new = np.asarray(after.Handler.m_Tangents, np.float32)
        assert np.array_equal(new[:, :3], old[:, :3]) and np.array_equal(new[:, 3], np.where(turned, -old[:, 3], old[:, 3]))
    for a, b in zip(after.Parts, before.Current):
        triangles = b.reshape(-1, 3)
        assert np.all(before.Flip[triangles] == before.Flip[triangles[:, :1]]), 'a triangle spans two pieces'
        assert np.array_equal(a, Reversed(np.searchsorted(used, b).astype(np.uint32), before.Flip[triangles[:, 0]]))
    if before.Tree.get('m_Skin'):
        assert after.Tree['m_Skin'] == [before.Tree['m_Skin'][int(i)] for i in used]
    old, new = Shapes(before.Tree, used), Shapes(after.Tree)
    assert old.keys() == new.keys()
    for (shape, index), row in old.items():
        sign = -1 if turned[index] else 1
        assert new[(shape, index)] == row[:3] + [sign * x for x in row[3:6]] + row[6:], (shape, index)
    print(f'{after.Name}: {after.Triangles():,} triangles, {len(after.Positions):,} vertices, '
          f'{int(turned.sum()):,} turned, {len(new)} morph rows', flush=True)

again = Bundle(sys.argv[1])
for mesh in again.Meshes:
    inward, mesh.Turned = mesh.Outward()
    mesh.Flip = inward if inward.any() else None
    print(f'{mesh.Name}: Outward() turns {mesh.Turned[0]} of {mesh.Turned[1]} pieces', flush=True)
if any(mesh.Flip is not None for mesh in again.Meshes):
    outward = Bundle(Path(again.Export(output / (source.Path.parent.name + ' outward'))[0]) / source.Path.name)
    for mesh in outward.Meshes:
        assert mesh.Outward()[1][0] == 0, f'{mesh.Name}: pieces still face inward after the turn'
print('PASS: turned pieces get reversed triangles and negated normals, tangent w and morph normals; '
      'the rest, positions, UVs, skin and morph positions unchanged; after Outward() nothing faces inward.')
