import base64
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import zlib

import numpy as np
import UnityPy
from core import Bundle


def Check(Filename):
    bundle = Bundle(Filename)
    source_hash = hashlib.sha256(bundle.Path.read_bytes()).hexdigest()
    mesh = bundle.Meshes[0]
    unchanged, _ = mesh.Simplify(mesh.Triangles(True), 0.01, 0)
    assert all(np.array_equal(a, b) for a, b in zip(unchanged, mesh.Parts))
    for mode in (0, 1):
        for error in (0.01, 0.05, 0.1):
            parts, worst = mesh.Simplify(mesh.Triangles(True) // 2, error, mode)
            print(f'Mode {mode}, error {error:.0%}: {sum(map(len, parts)) // 3:,} triangles; metric {worst:.4f}')
    mesh.Current, mesh.Error = mesh.Simplify(mesh.Triangles(True) // 2, 0.01, 0,
                                          0 if '--aggressive' in sys.argv else 50, '--aggressive' in sys.argv)
    with tempfile.TemporaryDirectory(prefix='cma-mesh-check-') as temp:
        output = Path(temp) / bundle.Path.parent.name
        bundle.Export(output)
        rebuilt = Bundle(output / bundle.Path.name)
        result = rebuilt.Meshes[0]
        used = np.unique(np.concatenate(mesh.Current))
        print('Exported:', result.Triangles(), 'triangles,', len(result.Positions), 'vertices', flush=True)
        if len(mesh.BoneData):
            for new, old in enumerate(used):
                before = mesh.BoneData[int(mesh.BoneData[old]):int(mesh.BoneData[old + 1])]
                after = result.BoneData[int(result.BoneData[new]):int(result.BoneData[new + 1])]
                assert np.array_equal(before, after), 'full variable bone weights'
        assert np.array_equal(result.Positions, mesh.Positions[used])
        assert np.array_equal(result.UV, mesh.UV[used])
        assert np.array_equal(result.Normals, mesh.Normals[used])
        for name in ('m_BoneWeights', 'm_BoneIndices', 'm_Tangents'):
            before = getattr(mesh.Handler, name)
            after = getattr(result.Handler, name)
            if before:
                assert np.array_equal(np.asarray(after), np.asarray(before)[used]), name
        for key in ('m_BindPose', 'm_BoneNameHashes', 'm_RootBoneNameHash', 'm_BonesAABB'):
            assert mesh.Tree[key] == result.Tree[key], key
        old = mesh.Tree['m_Shapes']
        new = result.Tree['m_Shapes']
        assert old['channels'] == new['channels']
        assert old['fullWeights'] == new['fullWeights']
        remap = {int(index): i for i, index in enumerate(used)}
        for a, b in zip(old['shapes'], new['shapes']):
            expected = [dict(v, index=remap[v['index']]) for v in old['vertices'][a['firstVertex']:a['firstVertex'] + a['vertexCount']] if v['index'] in remap]
            actual = new['vertices'][b['firstVertex']:b['firstVertex'] + b['vertexCount']]
            assert expected == actual, 'morph remapping'
        original_objects = {(o.assets_file.name, o.path_id): o for o in bundle.Environment.objects}
        changed_objects = {(o.assets_file.name, o.path_id): o for o in rebuilt.Environment.objects}
        assert original_objects.keys() == changed_objects.keys()
        for key, obj in original_objects.items():
            if obj.type.name != 'Mesh':
                assert obj.get_raw_data() == changed_objects[key].get_raw_data(), f'Untouched object {key}'
        for key, image in bundle.Textures.items():
            assert image.tobytes() == rebuilt.Textures[key].tobytes(), 'texture pixels'
        for file in output.glob('catalog*.json'):
            data = json.loads(file.read_text())
            extra = base64.b64decode(data['m_ExtraDataString'])
            pos = 1
            for _ in range(2):
                pos += 1 + extra[pos]
            length = struct.unpack_from('<I', extra, pos)[0]
            options = json.loads(extra[pos + 4:pos + 4 + length].decode('utf-16-le'))
            crc = zlib.crc32(b''.join(f.reader.bytes if hasattr(f, 'reader') else f.bytes for f in rebuilt.Environment.file.files.values()))
            assert options['m_Crc'] == crc
            assert options['m_BundleSize'] == (output / bundle.Path.name).stat().st_size
            assert options['m_Hash'] == hashlib.md5(rebuilt.Bytes).hexdigest()
            assert file.with_suffix('.hash').read_text() == hashlib.md5(file.read_bytes()).hexdigest()
        try:
            bundle.Export(output)
            raise AssertionError('Existing folder was overwritten')
        except ValueError:
            pass
        try:
            bundle.Export(bundle.Path.parent)
            raise AssertionError('Source folder was overwritten')
        except ValueError:
            pass
    assert source_hash == hashlib.sha256(bundle.Path.read_bytes()).hexdigest()
    print('PASS: round trip, UV, normals, tangents, full skin weights, bone IDs, bind poses, all morphs, textures, untouched objects, catalog CRC/hash, overwrite protection, source unchanged.')


if __name__ == '__main__':
    Check(sys.argv[1])
