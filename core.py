import base64
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import zlib

import numpy as np
import UnityPy
import meshoptimizer
from UnityPy.helpers.MeshHelper import MeshHandler
from meshoptimizer._loader import lib

# The Python wrapper omits this ABI declaration in 0.2.30a0.
lib.meshopt_simplifyWithAttributes.argtypes = [
    ct.POINTER(ct.c_uint), ct.POINTER(ct.c_uint), ct.c_size_t,
    ct.POINTER(ct.c_float), ct.c_size_t, ct.c_size_t,
    ct.POINTER(ct.c_float), ct.c_size_t, ct.POINTER(ct.c_float), ct.c_size_t,
    ct.POINTER(ct.c_ubyte), ct.c_size_t, ct.c_float, ct.c_uint, ct.POINTER(ct.c_float)]
lib.meshopt_simplifyWithAttributes.restype = ct.c_size_t


def Reversed(Indices, Which=None):
    triangles = Indices.reshape(-1, 3)
    if Which is None:
        return np.ascontiguousarray(triangles[:, [0, 2, 1]].ravel())
    triangles = triangles.copy()
    triangles[Which] = triangles[Which][:, [0, 2, 1]]
    return triangles.ravel()


def Pieces(Triangles, Count):
    # Connected pieces: every point gets the smallest point number of its piece.
    labels = np.arange(Count)
    while True:
        joined = labels.copy()
        np.minimum.at(joined, Triangles.ravel(), np.repeat(labels[Triangles].min(axis=1), 3))
        joined = joined[joined]
        if np.array_equal(joined, labels):
            return labels
        labels = joined


def Meets(Origin, Direction, Start, Side1, Side2):
    # Whether the ray crosses one of the triangles in front of its origin (Moller-Trumbore).
    p = np.cross(Direction, Side2)
    det = np.einsum('ij,ij->i', Side1, p)
    usable = np.abs(det) > 1e-30
    inverse = np.where(usable, 1 / np.where(usable, det, 1), 0)
    s = Origin - Start
    u = np.einsum('ij,ij->i', s, p) * inverse
    q = np.cross(s, Side1)
    v = (q @ Direction) * inverse
    t = np.einsum('ij,ij->i', Side2, q) * inverse
    return bool(np.any(usable & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)))


class Mesh:
    def __init__(self, Reader):
        self.Reader = Reader
        self.Tree = Reader.read_typetree()
        self.Name = self.Tree['m_Name'] or str(Reader.path_id)
        self.Handler = MeshHandler(Reader.read())
        self.Handler.process()
        self.Handler.src.m_Shapes = None
        self.Positions = np.ascontiguousarray(self.Handler.m_Vertices, dtype=np.float32)
        self.Normals = np.ascontiguousarray(self.Handler.m_Normals, dtype=np.float32)[:, :3] if self.Handler.m_Normals else np.zeros_like(self.Positions)
        self.UV = np.ascontiguousarray(self.Handler.m_UV0, dtype=np.float32)[:, :2] if self.Handler.m_UV0 else np.zeros((len(self.Positions), 2), np.float32)
        self.Parts = []
        size = 2 if self.Tree['m_IndexFormat'] == 0 else 4
        indices = np.frombuffer(bytes(self.Tree['m_IndexBuffer']), dtype='<u2' if size == 2 else '<u4')
        for part in self.Tree['m_SubMeshes']:
            if part['topology'] != 0:
                raise ValueError(f'{self.Name}: only triangle meshes are supported.')
            start = part['firstByte'] // size
            data = np.array(indices[start:start + part['indexCount']], dtype=np.uint32) + part.get('baseVertex', 0)
            if len(data) % 3 or (len(data) and data.max() >= len(self.Positions)):
                raise ValueError(f'{self.Name}: invalid triangle indices.')
            self.Parts.append(data)
        self.Current = self.Parts
        self.Materials = []
        self.Error = 0.0
        self.Canonical = None
        self.DetailScores = None
        self.DetailLevel = 0
        self.Aggressive = False
        self.Junctions = None
        self.Flip = None
        self.Turned = (0, 0)
        self.BoneData = np.asarray(self.Tree.get('m_VariableBoneCountWeights', {}).get('m_Data', []), dtype=np.uint32)
        if len(self.BoneData):
            count = len(self.Positions)
            offsets = self.BoneData[:count + 1].astype(np.int64)
            if (len(offsets) != count + 1 or offsets[0] != count + 1 or
                    offsets[-1] != len(self.BoneData) or np.any(np.diff(offsets) < 0) or
                    np.any(np.diff(offsets) > 255)):
                raise ValueError(f'{self.Name}: unsupported variable bone-weight layout.')
            payload = self.BoneData[count + 1:]
            if np.any((payload & 65535) >= len(self.Tree['m_BindPose'])):
                raise ValueError(f'{self.Name}: invalid variable bone index.')

    def Triangles(self, Original=False):
        return sum(len(p) for p in (self.Parts if Original else self.Current)) // 3

    def Vertices(self):
        return len(np.unique(np.concatenate(self.Current)))

    def Changed(self):
        return self.Flip is not None or any(not np.array_equal(a, b) for a, b in zip(self.Parts, self.Current))

    def Oriented(self, Part):
        # Triangles of turned pieces in reversed order; all corners of a triangle belong to one piece.
        if self.Flip is None:
            return Part
        return Reversed(Part, self.Flip[Part[::3]])

    def Shown(self, Original=False):
        # Turned pieces are drawn with reversed winding and negated normals, as they will be exported.
        parts = self.Parts if Original else self.Current
        if Original or self.Flip is None:
            return parts, self.Normals
        return [self.Oriented(part) for part in parts], np.where(self.Flip[:, None], -self.Normals, self.Normals)

    def Outward(self):
        # Outward means away from the wearer, as Blender's Recalculate Outside. Pieces are triangles joined
        # through shared points; each faces outward or is turned whole.
        # - A closed piece faces outward when its signed volume is positive.
        # - An open piece that wraps around space (a skirt, a sleeve, a cuff, a shoe's upper, a lining) is
        #   judged by rays from 8 to 16 random points of its faces, both ways along the face normal: the
        #   side where the ray meets the piece itself is inside. It is turned when three quarters of its
        #   rays say inward and three times as many as say outward; a curl open to one side (a frog
        #   button) meets itself only from some points and stays.
        # - A flat piece (a stripe, a patch, a stud) stays as it is: its shape does not tell which side
        #   is out.
        # Only the shape decides, so a second run turns nothing.
        # Returns the points of the pieces that face inward, and the piece counts.
        positions, remap = np.unique(self.Positions, axis=0, return_inverse=True)
        remap = remap.ravel()
        triangles = remap[np.concatenate(self.Parts)].reshape(-1, 3)
        triangles = triangles[(triangles[:, 0] != triangles[:, 1]) & (triangles[:, 1] != triangles[:, 2]) & (triangles[:, 0] != triangles[:, 2])]
        labels = Pieces(triangles, len(positions))
        points = positions.astype(np.float64)
        points -= (points.min(axis=0) + points.max(axis=0)) / 2
        start = points[triangles[:, 0]]
        side1 = points[triangles[:, 1]] - start
        side2 = points[triangles[:, 2]] - start
        normals = np.cross(side1, side2)
        areas = np.linalg.norm(normals, axis=1)
        middles = start + (side1 + side2) / 3
        pieces, faces, sizes = np.unique(labels[triangles[:, 0]], return_inverse=True, return_counts=True)
        order = np.argsort(faces, kind='stable')
        first = np.cumsum(sizes) - sizes
        total = np.bincount(faces, weights=areas, minlength=len(pieces))
        edges = np.sort(triangles[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
        _, inverse, counts = np.unique(edges, axis=0, return_inverse=True, return_counts=True)
        open_edges = np.bincount(np.repeat(faces, 3)[counts[inverse.ravel()] == 1], minlength=len(pieces))
        volume = np.bincount(faces, weights=np.einsum('ij,ij->i', middles, normals), minlength=len(pieces))
        centre = np.stack([np.bincount(faces, weights=middles[:, k] * areas, minlength=len(pieces)) for k in range(3)], axis=1) / np.maximum(total, 1e-300)[:, None]
        spread = np.bincount(faces, weights=np.linalg.norm(middles - centre[faces], axis=1) * areas, minlength=len(pieces))
        closed = (open_edges == 0) & (np.abs(volume) > 1e-3 * spread)
        turned = closed & (volume < 0)
        offset = 1e-5 * max(float(np.ptp(points, axis=0).max()), 1e-12)
        random = np.random.default_rng(1)
        for piece in np.flatnonzero(~closed & (total > 0)):
            members = order[first[piece]:first[piece] + sizes[piece]]
            members = members[areas[members] > 0]
            rays = min(len(members), int(np.clip(np.round(16 * np.sqrt(total[piece] / total.max())), 8, 16)))
            chosen = random.choice(members, rays, replace=False, p=areas[members] / areas[members].sum())
            a, b = random.random((2, rays))
            a, b = np.where(a + b > 1, 1 - a, a), np.where(a + b > 1, 1 - b, b)
            # Corners in point order, so a turned triangle gives the same point.
            corners = points[np.sort(triangles[chosen], axis=1)]
            sources = corners[:, 0] + a[:, None] * (corners[:, 1] - corners[:, 0]) + b[:, None] * (corners[:, 2] - corners[:, 0])
            directions = normals[chosen] / areas[chosen, None]
            own = (start[members], side1[members], side2[members])
            inside = outside = 0
            for source, direction in zip(sources, directions):
                ahead = Meets(source + offset * direction, direction, *own)
                behind = Meets(source - offset * direction, -direction, *own)
                inside += ahead and not behind
                outside += behind and not ahead
            turned[piece] = inside >= 0.75 * rays and inside >= 3 * outside
        inward = np.isin(labels, pieces[turned])
        return inward[remap], (int(np.count_nonzero(turned)), len(pieces))

    def FlipStreams(self, Raw, Streams):
        # Negates the normals and the tangent sign (w) of turned points; tangent directions, positions and UVs stay.
        data = bytearray(Raw)
        count = len(self.Positions)
        for channel in (1, 2):
            info = self.Handler.src.m_VertexData.m_Channels[channel]
            dimension = info.dimension & 15
            if not dimension:
                continue
            kind = self.Handler.get_channel_dtype(info)
            if kind not in ('f', 'e', 'b', 'h'):
                raise ValueError(f'{self.Name}: vertex format {info.format} of the normals cannot be flipped.')
            dtype = {'f': '<u4', 'e': '<u2', 'b': 'i1', 'h': '<i2'}[kind]
            size = np.dtype(dtype).itemsize
            stream = Streams[info.stream]
            view = np.frombuffer(data, np.uint8, count=count * stream.stride, offset=stream.offset).reshape(count, stream.stride)
            for component in (range(dimension) if channel == 1 else [3] if dimension == 4 else []):
                start = info.offset + component * size
                values = np.ascontiguousarray(view[:, start:start + size]).view(dtype).ravel()
                if kind in ('f', 'e'):
                    values[self.Flip] ^= np.array(1 << (8 * size - 1), dtype)
                else:
                    # SNorm: the lowest value decodes as -1 like the one above it.
                    values[self.Flip] = -np.maximum(values[self.Flip], -np.iinfo(dtype).max)
                view[:, start:start + size] = values.view(np.uint8).reshape(count, size)
        return bytes(data)

    def DetailLocks(self, Strength):
        if Strength <= 0:
            return None
        if self.DetailScores is None:
            positions, remap = np.unique(self.Positions, axis=0, return_inverse=True)
            triangles = remap[np.concatenate(self.Parts)].reshape(-1, 3)
            face = positions[triangles]
            normals = np.cross(face[:, 1] - face[:, 0], face[:, 2] - face[:, 0])
            lengths = np.linalg.norm(normals, axis=1)
            normals /= np.maximum(lengths[:, None], 1e-30)
            centers = face.mean(axis=1)
            edges = np.sort(triangles[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
            unique, inverse, counts = np.unique(edges, axis=0, return_inverse=True, return_counts=True)
            order = np.argsort(inverse, kind='stable')
            starts = np.cumsum(counts) - counts
            shared = np.flatnonzero(counts == 2)
            first = order[starts[shared]] // 3
            second = order[starts[shared] + 1] // 3
            angle = np.arccos(np.clip(np.einsum('ij,ij->i', normals[first], normals[second]), -1, 1))
            extent = max(float(np.ptp(positions, axis=0).max()), 1e-20)
            distance = np.linalg.norm(centers[first] - centers[second], axis=1) / extent
            # Tight local curvature and sharp creases get higher protection scores.
            score = np.maximum(angle / np.maximum(distance, 1e-8), angle * 20)
            score[(lengths[first] <= 1e-20) | (lengths[second] <= 1e-20) | (angle < 1e-4)] = 0
            values = np.zeros(len(positions), np.float32)
            np.maximum.at(values, unique[shared].ravel(), np.repeat(score, 2))
            self.DetailScores = values[remap]
        threshold = 1000 * (0.008 ** (min(100, Strength) / 100))
        return np.ascontiguousarray(self.DetailScores >= threshold, dtype=np.uint8)

    def Simplify(self, Target, Error, Mode, Detail=0, Aggressive=False):
        if self.Tree['m_MeshCompression']:
            raise ValueError('Compressed mesh geometry is not supported yet. Variable bone weights are supported.')
        if self.Canonical is None:
            raw = bytes(self.Handler.src.m_VertexData.m_DataSize)
            records = []
            for stream in self.Handler.get_streams(self.Handler.src.m_VertexData.m_Channels, len(self.Positions)):
                if stream.stride:
                    records.append(np.frombuffer(raw, np.uint8, count=len(self.Positions) * stream.stride, offset=stream.offset).reshape(-1, stream.stride))
            shapes = self.Tree.get('m_Shapes', {})
            for shape in shapes.get('shapes', []):
                delta = np.zeros((len(self.Positions), 9), np.float32)
                for v in shapes['vertices'][shape['firstVertex']:shape['firstVertex'] + shape['vertexCount']]:
                    delta[v['index']] = [v[field][axis] for field in ('vertex', 'normal', 'tangent') for axis in ('x', 'y', 'z')]
                records.append(delta.view(np.uint8))
            if self.Tree.get('m_Skin'):
                records.append(np.asarray(self.Handler.m_BoneIndices, np.int32).view(np.uint8))
                records.append(np.asarray(self.Handler.m_BoneWeights, np.float32).view(np.uint8))
            if len(self.BoneData):
                counts = np.diff(self.BoneData[:len(self.Positions) + 1])
                variable = np.zeros((len(self.Positions), int(counts.max()) + 1), np.uint32)
                variable[:, 0] = counts
                for i, count in enumerate(counts):
                    start = int(self.BoneData[i])
                    variable[i, 1:int(count) + 1] = self.BoneData[start:start + int(count)]
                records.append(variable.view(np.uint8))
            data = np.ascontiguousarray(np.column_stack(records))
            _, first, inverse = np.unique(data.view(np.dtype((np.void, data.shape[1]))).ravel(), return_index=True, return_inverse=True)
            self.Canonical = np.asarray(first[inverse], dtype=np.uint32)
        attributes = [self.UV, self.Normals]
        weights = [1.0, 1.0, 0.25, 0.25, 0.25]
        extent = max(float(np.ptp(self.Positions, axis=0).max()), 1e-6)
        shapes = self.Tree.get('m_Shapes', {})
        for shape in shapes.get('shapes', [])[:4]:
            delta = np.zeros_like(self.Positions)
            for v in shapes['vertices'][shape['firstVertex']:shape['firstVertex'] + shape['vertexCount']]:
                delta[v['index']] = list(v['vertex'].values())
            attributes.append(delta / extent)
            weights.extend([1.0] * 3)
        if len(self.BoneData):
            payload = self.BoneData[len(self.Positions) + 1:]
            bones = payload & 65535
            active, columns = np.unique(bones, return_inverse=True)
            dense = np.zeros((len(self.Positions), len(active)), np.float32)
            rows = np.repeat(np.arange(len(self.Positions)), np.diff(self.BoneData[:len(self.Positions) + 1]))
            np.add.at(dense, (rows, columns), (payload >> 16).astype(np.float32) / 65535)
            available = 32 - len(weights)
            if dense.shape[1] > available:
                # Project all bone influences instead of dropping lower-ranked weights.
                _, axes = np.linalg.eigh(dense.T @ dense)
                dense = dense @ axes[:, -available:]
            attributes.append(dense)
            weights.extend([1.0] * dense.shape[1])
        elif self.Handler.m_BoneIndices and self.Handler.m_BoneWeights:
            bones = np.asarray(self.Handler.m_BoneIndices)
            skin = np.asarray(self.Handler.m_BoneWeights, dtype=np.float32)
            if self.Tree['m_VertexData']['m_Channels'][12]['format'] == 4:
                skin /= 65535
            active = np.unique(bones[skin > 0.001])
            if len(active) <= 32 - len(weights):
                dense = np.zeros((len(self.Positions), len(active)), np.float32)
                for i, bone in enumerate(active):
                    dense[:, i] = np.sum(np.where(bones == bone, skin, 0), axis=1)
                attributes.append(dense)
                weights.extend([1.0] * len(active))
        attributes = np.ascontiguousarray(np.column_stack(attributes), dtype=np.float32)
        weights = np.asarray(weights, dtype=np.float32)
        locks = self.DetailLocks(Detail)
        if self.Junctions is None:
            # Points used by more than one submesh stay, so the submeshes keep meeting without cracks.
            _, ids = np.unique(self.Positions, axis=0, return_inverse=True)
            ids = ids.ravel()
            owners = np.zeros(ids.max() + 1, np.int32)
            for part in self.Parts:
                owners[np.unique(ids[self.Canonical[part]])] += 1
            self.Junctions = owners[ids] > 1
        if Aggressive:
            native = ct.CDLL(str(Path(__file__).resolve().parent / 'CmaMeshSimplifier.dll'))
            simplify = native.meshopt_simplifyWithAttributes
            simplify.argtypes = lib.meshopt_simplifyWithAttributes.argtypes
            simplify.restype = ct.c_size_t
        result = []
        worst = 0.0
        for part in self.Parts:
            if not len(part):
                result.append(part.copy())
                continue
            target = max(3, round(Target * len(part) / max(1, self.Triangles(True)) / 3) * 3)
            if target >= len(part):
                result.append(part.copy())
                continue
            # Only this submesh's points go to the simplifier: an unused copy at the same position (a welded
            # duplicate, or another submesh's point) made meshoptimizer lock the point as a seam.
            used, part = np.unique(self.Canonical[part], return_inverse=True)
            part = np.ascontiguousarray(part.ravel(), dtype=np.uint32)
            positions = np.ascontiguousarray(self.Positions[used])
            values = np.ascontiguousarray(attributes[used])
            lock = self.Junctions[used] if locks is None else self.Junctions[used] | (locks[used] != 0)
            lock = np.ascontiguousarray(lock, dtype=np.uint8) if lock.any() else None
            output = np.empty_like(part)
            error = np.zeros(1, np.float32)
            if Aggressive:
                count = simplify(
                    output.ctypes.data_as(ct.POINTER(ct.c_uint)),
                    part.ctypes.data_as(ct.POINTER(ct.c_uint)), len(part),
                    positions.ctypes.data_as(ct.POINTER(ct.c_float)), len(positions), positions.strides[0],
                    values.ctypes.data_as(ct.POINTER(ct.c_float)), values.strides[0],
                    weights.ctypes.data_as(ct.POINTER(ct.c_float)), len(weights),
                    lock.ctypes.data_as(ct.POINTER(ct.c_ubyte)) if lock is not None else None,
                    target, Error, 32 | (1 if Mode == 0 else 0),
                    error.ctypes.data_as(ct.POINTER(ct.c_float)))
            else:
                count = meshoptimizer.simplify_with_attributes(
                    output, part, positions, values, weights,
                    target_index_count=target, target_error=Error,
                    options=1 if Mode == 0 else 0, result_error=error, vertex_lock=lock)
            if count < 3 or count % 3:
                raise ValueError('The simplifier returned an empty or invalid submesh.')
            result.append(np.ascontiguousarray(used[output[:count]], dtype=np.uint32))
            worst = max(worst, float(error[0]))
        return result, worst

    def ExportTree(self):
        tree = dict(self.Tree)
        tree['m_VertexData'] = dict(tree['m_VertexData'])
        tree['m_SubMeshes'] = [dict(part) for part in tree['m_SubMeshes']]
        if 'm_Shapes' in tree:
            tree['m_Shapes'] = dict(tree['m_Shapes'])
            tree['m_Shapes']['shapes'] = [dict(shape) for shape in tree['m_Shapes']['shapes']]
        used = np.unique(np.concatenate(self.Current))
        remap = np.full(len(self.Positions), -1, dtype=np.int64)
        remap[used] = np.arange(len(used))
        streams = self.Handler.get_streams(self.Handler.src.m_VertexData.m_Channels, len(self.Positions))
        raw = bytes(self.Handler.src.m_VertexData.m_DataSize)
        if self.Flip is not None:
            raw = self.FlipStreams(raw, streams)
        output = bytearray()
        for stream in streams:
            if not stream.stride:
                continue
            data = np.frombuffer(raw, np.uint8, count=len(self.Positions) * stream.stride, offset=stream.offset).reshape(-1, stream.stride)
            output.extend(data[used].tobytes())
            output.extend(b'\0' * (-len(output) % 16))
        tree['m_VertexData']['m_DataSize'] = bytes(output)
        tree['m_VertexData']['m_VertexCount'] = len(used)
        if 'm_StreamData' in tree:
            tree['m_StreamData'] = dict(offset=0, size=0, path='')
        size = 2 if len(used) <= 65535 else 4
        tree['m_IndexFormat'] = 0 if size == 2 else 1
        indices = []
        offset = 0
        for sub, part in zip(tree['m_SubMeshes'], self.Current):
            mapped = remap[self.Oriented(part)]
            sub.update(firstByte=offset, indexCount=len(mapped), baseVertex=0,
                       firstVertex=int(mapped.min()) if len(mapped) else 0,
                       vertexCount=int(np.ptp(mapped)) + 1 if len(mapped) else 0)
            indices.append(mapped.astype('<u2' if size == 2 else '<u4').tobytes())
            offset += len(mapped) * size
        tree['m_IndexBuffer'] = b''.join(indices)
        shapes = tree.get('m_Shapes', {})
        original = shapes.get('vertices', [])
        vertices = []
        for shape in shapes.get('shapes', []):
            selected = []
            for v in original[shape['firstVertex']:shape['firstVertex'] + shape['vertexCount']]:
                index = int(remap[v['index']])
                if index >= 0:
                    selected.append(dict(v, index=index))
                    if self.Flip is not None and self.Flip[v['index']]:
                        selected[-1]['normal'] = {axis: -value for axis, value in v['normal'].items()}
            shape['firstVertex'] = len(vertices)
            shape['vertexCount'] = len(selected)
            vertices.extend(selected)
        if shapes:
            shapes['vertices'] = vertices
        if tree.get('m_Skin'):
            tree['m_Skin'] = [tree['m_Skin'][int(i)] for i in used]
        if len(self.BoneData):
            counts = self.BoneData[used + 1] - self.BoneData[used]
            offsets = np.empty(len(used) + 1, np.uint32)
            offsets[0] = len(used) + 1
            offsets[1:] = np.cumsum(counts, dtype=np.uint32) + offsets[0]
            payload = np.concatenate([self.BoneData[int(self.BoneData[i]):int(self.BoneData[i + 1])] for i in used])
            tree['m_VariableBoneCountWeights'] = {'m_Data': np.concatenate((offsets, payload)).tolist()}
        for key in ('m_BakedConvexCollisionMesh', 'm_BakedTriangleCollisionMesh'):
            if key in tree:
                tree[key] = []
        return tree


class Bundle:
    def __init__(self, Filename):
        self.Path = Path(Filename).resolve()
        self.Bytes = self.Path.read_bytes()
        self.Environment = UnityPy.load(self.Bytes)
        if not hasattr(self.Environment.file, 'save'):
            raise ValueError('Please open a Unity asset bundle.')
        self.Meshes = []
        self.Warnings = []
        self.Textures = {}
        objects = {(o.assets_file.name, o.path_id): o for o in self.Environment.objects}

        def resolve(owner, pointer):
            if pointer.get('m_FileID', 0) != 0:
                return None
            return objects.get((owner.assets_file.name, pointer['m_PathID']))

        by_id = {}
        for obj in self.Environment.objects:
            if obj.type.name == 'Mesh':
                try:
                    mesh = Mesh(obj)
                    self.Meshes.append(mesh)
                    by_id[(obj.assets_file.name, obj.path_id)] = mesh
                except Exception as error:
                    self.Warnings.append(f'Mesh {obj.path_id}: {error}')
        for obj in self.Environment.objects:
            if obj.type.name not in ('SkinnedMeshRenderer', 'MeshRenderer'):
                continue
            tree = obj.read_typetree()
            pointer = tree.get('m_Mesh')
            if pointer is None:
                go = resolve(obj, tree['m_GameObject'])
                if go:
                    for component in go.read_typetree()['m_Component']:
                        child = resolve(go, component['component'])
                        if child and child.type.name == 'MeshFilter':
                            pointer = child.read_typetree()['m_Mesh']
                            break
            mesh = by_id.get((obj.assets_file.name, (pointer or {}).get('m_PathID')))
            if mesh is None or mesh.Materials:
                continue
            for pointer in tree.get('m_Materials', []):
                material = {'Name': 'Default', 'Texture': None, 'Color': (0.78, 0.8, 0.84, 1), 'Scale': (1, 1), 'Offset': (0, 0)}
                mat = resolve(obj, pointer)
                if mat:
                    data = mat.read_typetree()
                    material['Name'] = data['m_Name']
                    props = data['m_SavedProperties']
                    colors = dict(props.get('m_Colors', []))
                    color = colors.get('_BaseColor', colors.get('_Color'))
                    if color:
                        material['Color'] = tuple(color[k] for k in ('r', 'g', 'b', 'a'))
                    textures = dict(props.get('m_TexEnvs', []))
                    for key in ('_BaseColorMap', '_MainTex', '_BaseMap', '_Diffuse'):
                        entry = textures.get(key)
                        texture = resolve(mat, entry['m_Texture']) if entry else None
                        if texture:
                            tid = (texture.assets_file.name, texture.path_id)
                            try:
                                if tid not in self.Textures:
                                    self.Textures[tid] = texture.read().image.convert('RGBA')
                                material['Texture'] = self.Textures[tid]
                                material['Scale'] = tuple(entry['m_Scale'][k] for k in ('x', 'y'))
                                material['Offset'] = tuple(entry['m_Offset'][k] for k in ('x', 'y'))
                            except Exception as error:
                                self.Warnings.append(f'Texture {texture.path_id}: {error}')
                            break
                mesh.Materials.append(material)
        if not self.Meshes:
            raise ValueError('No supported meshes found.\n' + '\n'.join(self.Warnings))

    @staticmethod
    def Catalog(Data, BundleName, Digest, Size, Crc):
        data = json.loads(Data)
        ids = data.get('m_InternalIds', [])
        matching = [i for i, v in enumerate(ids) if v.replace('\\', '/').split('/')[-1].lower() == BundleName.lower()]
        if not matching:
            return None
        entries = bytearray(base64.b64decode(data['m_EntryDataString']))
        extra = base64.b64decode(data['m_ExtraDataString'])
        replacements = {}
        count = struct.unpack_from('<I', entries)[0]
        for i in range(count):
            row = struct.unpack_from('<7i', entries, 4 + i * 28)
            if row[0] not in matching or row[4] < 0 or row[4] in replacements:
                continue
            start = row[4]
            pos = start
            if extra[pos] != 7:
                raise ValueError('Unsupported catalog bundle options encoding.')
            pos += 1
            for _ in range(2):
                pos += 1 + extra[pos]
            length = struct.unpack_from('<I', extra, pos)[0]
            options = json.loads(extra[pos + 4:pos + 4 + length].decode('utf-16-le'))
            options.update(m_Hash=Digest, m_Crc=Crc, m_BundleSize=Size)
            text = json.dumps(options, separators=(',', ':'), ensure_ascii=False).encode('utf-16-le')
            replacements[start] = (pos + 4 + length, extra[start:pos] + struct.pack('<I', len(text)) + text)
        if not replacements:
            raise ValueError('The catalog refers to this bundle but has no editable request options.')
        output = bytearray()
        cursor = 0
        shifts = []
        for start, (end, replacement) in sorted(replacements.items()):
            output.extend(extra[cursor:start])
            shifts.append((start, end, len(replacement) - (end - start)))
            output.extend(replacement)
            cursor = end
        output.extend(extra[cursor:])
        for i in range(count):
            offset = 4 + i * 28 + 16
            old = struct.unpack_from('<i', entries, offset)[0]
            if old >= 0:
                struct.pack_into('<i', entries, offset, old + sum(delta for start, end, delta in shifts if end <= old))
        data['m_EntryDataString'] = base64.b64encode(entries).decode()
        data['m_ExtraDataString'] = base64.b64encode(output).decode()
        data['m_BuildResultHash'] = Digest
        return json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')

    def Export(self, Directory):
        destination = Path(Directory).resolve()
        if destination == self.Path.parent or self.Path.parent in destination.parents:
            raise ValueError('Choose a separate output folder outside the source mod folder.')
        if destination.exists():
            raise ValueError('The output folder already exists. Choose a new folder to avoid overwriting files.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        env = UnityPy.load(self.Bytes)
        objects = {(o.assets_file.name, o.path_id): o for o in env.objects}
        changed = []
        for mesh in self.Meshes:
            if mesh.Changed():
                key = (mesh.Reader.assets_file.name, mesh.Reader.path_id)
                objects[key].save_typetree(mesh.ExportTree())
                changed.append(mesh)
        if not changed:
            raise ValueError('No changes to export. Apply simplification or flip normals first.')
        result = env.file.save(packer='lz4')
        verified = UnityPy.load(result)
        crc = zlib.crc32(b''.join(f.reader.bytes if hasattr(f, 'reader') else f.bytes for f in verified.file.files.values()))
        checks = {(o.assets_file.name, o.path_id): o for o in verified.objects}
        for mesh in changed:
            check = Mesh(checks[(mesh.Reader.assets_file.name, mesh.Reader.path_id)])
            if check.Triangles() != mesh.Triangles() or len(check.Positions) != mesh.Vertices():
                raise ValueError('Export verification failed: mesh counts do not match.')
            used = np.unique(np.concatenate(mesh.Current))
            if not np.array_equal(check.Positions, mesh.Positions[used]) or not np.array_equal(check.UV, mesh.UV[used]):
                raise ValueError('Export verification failed: vertex attributes changed.')
            if mesh.Flip is not None:
                expected = [np.searchsorted(used, mesh.Oriented(part)) for part in mesh.Current]
                if (not np.array_equal(check.Normals, mesh.Shown()[1][used]) or
                        any(not np.array_equal(a, b) for a, b in zip(check.Parts, expected))):
                    raise ValueError('Export verification failed: flipped normals or triangle order do not match.')
            if len(mesh.BoneData):
                for new, old in enumerate(used):
                    before = mesh.BoneData[int(mesh.BoneData[old]):int(mesh.BoneData[old + 1])]
                    after = check.BoneData[int(check.BoneData[new]):int(check.BoneData[new + 1])]
                    if not np.array_equal(before, after):
                        raise ValueError('Export verification failed: variable bone weights changed.')
        digest = hashlib.md5(result).hexdigest()
        catalogs = {}
        for path in self.Path.parent.glob('catalog*.json'):
            updated = self.Catalog(path.read_text('utf-8-sig'), self.Path.name, digest, len(result), crc)
            if updated:
                catalogs[path.name] = updated
        if not catalogs:
            raise ValueError('No matching catalog*.json beside the source bundle. Put the mod catalog there and export again.')
        staging = Path(tempfile.mkdtemp(prefix='.mesh-export-', dir=destination.parent))
        try:
            for path in self.Path.parent.iterdir():
                if path.is_file():
                    shutil.copy2(path, staging / path.name)
            (staging / self.Path.name).write_bytes(result)
            for name, content in catalogs.items():
                (staging / name).write_bytes(content)
                (staging / Path(name).with_suffix('.hash')).write_text(hashlib.md5(content).hexdigest(), encoding='ascii')
            os.rename(staging, destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return str(destination), len(result)
