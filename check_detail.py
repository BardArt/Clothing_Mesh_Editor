import sys
import numpy as np
from core import Mesh, Bundle


def Sphere(Radius, Center):
    longitude, latitude = 24, 12
    points = [[0, Radius, 0]]
    for row in range(1, latitude):
        phi = np.pi * row / latitude
        for col in range(longitude):
            theta = 2 * np.pi * col / longitude
            points.append([Radius * np.sin(phi) * np.cos(theta), Radius * np.cos(phi), Radius * np.sin(phi) * np.sin(theta)])
    points.append([0, -Radius, 0])
    faces = []
    for col in range(longitude):
        following = (col + 1) % longitude
        faces.append([0, 1 + following, 1 + col])
        for row in range(latitude - 2):
            a, b = 1 + row * longitude + col, 1 + row * longitude + following
            faces.extend([[a, b, a + longitude], [b, b + longitude, a + longitude]])
        a = 1 + (latitude - 2) * longitude
        faces.append([len(points) - 1, a + col, a + following])
    return np.asarray(points, np.float32) + Center, np.asarray(faces, np.uint32).ravel()


large, a = Sphere(1, np.array([0, 0, 0], np.float32))
small, b = Sphere(.025, np.array([1.2, 0, 0], np.float32))
mesh = Mesh.__new__(Mesh)
mesh.Positions = np.concatenate((large, small))
mesh.Parts = [np.concatenate((a, b + len(large)))]
mesh.DetailScores = None
assert mesh.DetailLocks(0) is None
locks = mesh.DetailLocks(50)
assert locks[:len(large)].mean() < .1
assert locks[len(large):].mean() > .9
previous = np.zeros(len(locks), np.uint8)
for strength in (1, 25, 50, 75, 100):
    current = mesh.DetailLocks(strength)
    assert np.all(current >= previous)
    previous = current
mesh.Positions *= 100
mesh.DetailScores = None
assert np.array_equal(locks, mesh.DetailLocks(50))
flat = Mesh.__new__(Mesh)
flat.Positions = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], np.float32)
flat.Parts = [np.array([0, 1, 2, 0, 2, 3], np.uint32)]
flat.DetailScores = None
assert not flat.DetailLocks(100).any()
print('PASS: tiny curved feature protected, broad surface free, flat surface free, monotonic protection, scale independence.', flush=True)

if len(sys.argv) > 1:
    bundle = Bundle(sys.argv[1])
    for mesh in bundle.Meshes:
        for level in (0, 25, 50, 75, 100):
            result, _ = mesh.Simplify(mesh.Triangles(True) // 2, .01, 0, level)
            locks = mesh.DetailLocks(level)
            if locks is not None:
                protected = np.unique(mesh.Canonical[np.flatnonzero(locks)])
                positions = np.ascontiguousarray(mesh.Positions[protected]).view('V12').ravel()
                kept = np.ascontiguousarray(mesh.Positions[np.unique(np.concatenate(result))]).view('V12').ravel()
                assert not len(np.setdiff1d(positions, kept)), 'Protected geometric points were removed'
            print(mesh.Name, 'protection', level, 'triangles', sum(len(p) for p in result) // 3,
                  'locked', int(locks.sum()) if locks is not None else 0, flush=True)
    print('PASS: protected geometric points survive simplification.', flush=True)
