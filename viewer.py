import ctypes as ct
import math

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtOpenGLWidgets import QOpenGLWidget


def QuadEdges(Positions, Indices):
    triangles = Indices.reshape(-1, 3)
    edges = np.sort(triangles[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
    unique, inverse, counts = np.unique(edges, axis=0, return_inverse=True, return_counts=True)
    order = np.argsort(inverse, kind='stable')
    starts = np.cumsum(counts) - counts
    candidates = np.flatnonzero(counts == 2)
    if not len(candidates):
        return np.ascontiguousarray(unique.ravel(), dtype=np.uint32)
    first = order[starts[candidates]] // 3
    second = order[starts[candidates] + 1] // 3
    shared = unique[candidates]
    a = triangles[first].sum(axis=1, dtype=np.int64) - shared.sum(axis=1, dtype=np.int64)
    b = triangles[second].sum(axis=1, dtype=np.int64) - shared.sum(axis=1, dtype=np.int64)
    corners = Positions[np.column_stack((a, shared[:, 0], b, shared[:, 1]))]
    sides = np.roll(corners, -1, axis=1) - corners
    lengths = np.linalg.norm(sides, axis=2)
    crosses = np.cross(sides, np.roll(sides, -1, axis=1))
    normal = crosses.sum(axis=1)
    convex = np.all(np.einsum('ijk,ik->ij', crosses, normal) > 1e-16, axis=1)
    face = Positions[triangles]
    normals = np.cross(face[:, 1] - face[:, 0], face[:, 2] - face[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-20)
    flat = np.einsum('ij,ij->i', normals[first], normals[second])
    cosine = np.sum(sides * np.roll(sides, -1, axis=1), axis=2) / np.maximum(lengths * np.roll(lengths, -1, axis=1), 1e-20)
    valid = convex & (flat > 0.95) & (a != b) & np.all(lengths > 1e-10, axis=1)
    score = np.abs(cosine).mean(axis=1) + (1 - flat) * 4
    used = np.zeros(len(triangles), dtype=bool)
    hidden = np.zeros(len(unique), dtype=bool)
    for i in np.flatnonzero(valid)[np.argsort(score[valid], kind='stable')]:
        if not used[first[i]] and not used[second[i]]:
            used[first[i]] = used[second[i]] = True
            hidden[candidates[i]] = True
    return np.ascontiguousarray(unique[~hidden].ravel(), dtype=np.uint32)


class View(QOpenGLWidget):
    def __init__(self):
        super().__init__()
        self.Mesh = None
        self.Original = False
        self.Wire = False
        self.Quads = False
        self.EdgeSource = None
        self.Edges = []
        self.Textured = True
        self.Orientation = False
        self.List = 0
        self.Plain = 0
        self.TextureIds = []
        self.Dirty = True
        self.Yaw = -25.0
        self.Pitch = 15.0
        self.Zoom = 3.2
        self.Pan = [0.0, 0.0]
        self.Last = None
        self.Gl = ct.WinDLL('opengl32.dll')
        signatures = {
            'glClearColor': [ct.c_float] * 4, 'glClear': [ct.c_uint],
            'glEnable': [ct.c_uint], 'glDisable': [ct.c_uint],
            'glViewport': [ct.c_int] * 4, 'glMatrixMode': [ct.c_uint],
            'glLoadIdentity': [], 'glFrustum': [ct.c_double] * 6,
            'glTranslatef': [ct.c_float] * 3, 'glRotatef': [ct.c_float] * 4,
            'glScalef': [ct.c_float] * 3, 'glBegin': [ct.c_uint], 'glEnd': [],
            'glColor4f': [ct.c_float] * 4, 'glNormal3f': [ct.c_float] * 3,
            'glVertex3f': [ct.c_float] * 3, 'glTexCoord2f': [ct.c_float] * 2,
            'glGenLists': [ct.c_int], 'glNewList': [ct.c_uint, ct.c_uint],
            'glEndList': [], 'glCallList': [ct.c_uint], 'glDeleteLists': [ct.c_uint, ct.c_int],
            'glGenTextures': [ct.c_int, ct.POINTER(ct.c_uint)],
            'glDeleteTextures': [ct.c_int, ct.POINTER(ct.c_uint)],
            'glBindTexture': [ct.c_uint, ct.c_uint],
            'glTexParameteri': [ct.c_uint, ct.c_uint, ct.c_int],
            'glTexImage2D': [ct.c_uint, ct.c_int, ct.c_int, ct.c_int, ct.c_int, ct.c_int, ct.c_uint, ct.c_uint, ct.c_void_p],
            'glLightfv': [ct.c_uint, ct.c_uint, ct.POINTER(ct.c_float)],
            'glLightModeli': [ct.c_uint, ct.c_int],
            'glPolygonMode': [ct.c_uint, ct.c_uint],
            'glCullFace': [ct.c_uint], 'glPolygonOffset': [ct.c_float] * 2,
            'glEnableClientState': [ct.c_uint], 'glDisableClientState': [ct.c_uint],
            'glVertexPointer': [ct.c_int, ct.c_uint, ct.c_int, ct.c_void_p],
            'glNormalPointer': [ct.c_uint, ct.c_int, ct.c_void_p],
            'glTexCoordPointer': [ct.c_int, ct.c_uint, ct.c_int, ct.c_void_p],
            'glDrawElements': [ct.c_uint, ct.c_int, ct.c_uint, ct.c_void_p],
        }
        for name, args in signatures.items():
            function = getattr(self.Gl, name)
            function.argtypes = args
            function.restype = ct.c_uint if name == 'glGenLists' else None
        self.setMinimumSize(500, 400)

    def SetMesh(self, Mesh):
        self.Mesh = Mesh
        self.Dirty = True
        self.update()

    def Home(self):
        self.Yaw, self.Pitch, self.Zoom = -25.0, 15.0, 3.2
        self.Pan = [0.0, 0.0]
        self.update()

    def initializeGL(self):
        gl = self.Gl
        gl.glClearColor(0.065, 0.08, 0.1, 1.0)
        gl.glEnable(0x0B71)
        gl.glEnable(0x0BA1)
        gl.glEnable(0x0B57)
        gl.glEnable(0x4000)
        gl.glLightfv(0x4000, 0x1201, (ct.c_float * 4)(0.8, 0.8, 0.8, 1))
        gl.glLightfv(0x4000, 0x1200, (ct.c_float * 4)(0.4, 0.4, 0.4, 1))
        gl.glLightModeli(0x0B52, 1)
        self.Dirty = True
        self.List = 0
        self.Plain = 0
        self.TextureIds = []

    def Compile(self):
        gl = self.Gl
        if self.List:
            gl.glDeleteLists(self.List, 1)
        if self.Plain:
            gl.glDeleteLists(self.Plain, 1)
            self.Plain = 0
        if self.TextureIds:
            gl.glDeleteTextures(len(self.TextureIds), (ct.c_uint * len(self.TextureIds))(*self.TextureIds))
        self.TextureIds = []
        mesh = self.Mesh
        parts = mesh.Parts if self.Original else mesh.Current
        drawn, normals = mesh.Shown(self.Original)
        if self.Wire and self.Quads and self.EdgeSource is not parts:
            self.Edges = [QuadEdges(mesh.Positions, part) for part in parts]
            self.EdgeSource = parts
        textures = []
        for material in mesh.Materials:
            texture = 0
            if material['Texture'] is not None and self.Textured and not self.Wire:
                pic = material['Texture'].copy()
                pic.thumbnail((2048, 2048))
                data = pic.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
                tid = ct.c_uint()
                gl.glGenTextures(1, ct.byref(tid))
                texture = tid.value
                self.TextureIds.append(texture)
                gl.glBindTexture(0x0DE1, texture)
                gl.glTexParameteri(0x0DE1, 0x2801, 0x2601)
                gl.glTexParameteri(0x0DE1, 0x2800, 0x2601)
                gl.glTexImage2D(0x0DE1, 0, 0x1908, pic.width, pic.height, 0, 0x1908, 0x1401, data)
            textures.append(texture)
        self.List = gl.glGenLists(1)
        gl.glNewList(self.List, 0x1300)
        gl.glEnableClientState(0x8074)
        gl.glEnableClientState(0x8075)
        gl.glEnableClientState(0x8078)
        positions = np.ascontiguousarray(mesh.Positions)
        normals = np.ascontiguousarray(normals)
        gl.glVertexPointer(3, 0x1406, 0, positions.ctypes.data)
        gl.glNormalPointer(0x1406, 0, normals.ctypes.data)
        for i, part in enumerate(drawn):
            material = mesh.Materials[i] if i < len(mesh.Materials) else None
            texture = textures[i] if i < len(textures) else 0
            if texture:
                gl.glEnable(0x0DE1)
                gl.glBindTexture(0x0DE1, texture)
            else:
                gl.glDisable(0x0DE1)
            gl.glColor4f(*((0.65, 0.9, 0.76, 1) if self.Wire else material['Color'] if material else (0.75, 0.78, 0.85, 1)))
            uv = np.ascontiguousarray(mesh.UV * np.array(material['Scale'] if material else (1, 1), np.float32) + np.array(material['Offset'] if material else (0, 0), np.float32))
            gl.glTexCoordPointer(2, 0x1406, 0, uv.ctypes.data)
            if self.Wire and self.Quads:
                edges = self.Edges[i]
                gl.glDrawElements(1, len(edges), 0x1405, edges.ctypes.data)
            else:
                gl.glDrawElements(4, len(part), 0x1405, part.ctypes.data)
        gl.glDisableClientState(0x8074)
        gl.glDisableClientState(0x8075)
        gl.glDisableClientState(0x8078)
        gl.glDisable(0x0DE1)
        gl.glEndList()
        if self.Orientation:
            # Untextured triangles; paintGL colours their front and back sides.
            self.Plain = gl.glGenLists(1)
            gl.glNewList(self.Plain, 0x1300)
            gl.glEnableClientState(0x8074)
            gl.glEnableClientState(0x8075)
            gl.glVertexPointer(3, 0x1406, 0, positions.ctypes.data)
            gl.glNormalPointer(0x1406, 0, normals.ctypes.data)
            for part in drawn:
                gl.glDrawElements(4, len(part), 0x1405, part.ctypes.data)
            gl.glDisableClientState(0x8074)
            gl.glDisableClientState(0x8075)
            gl.glEndList()
        self.Dirty = False

    def paintGL(self):
        gl = self.Gl
        ratio = self.devicePixelRatioF()
        gl.glViewport(0, 0, int(self.width() * ratio), int(self.height() * ratio))
        gl.glClear(0x4000 | 0x0100)
        if self.Mesh is None:
            return
        if self.Dirty:
            self.Compile()
        gl.glMatrixMode(0x1701)
        gl.glLoadIdentity()
        aspect = self.width() / max(1, self.height())
        near = 0.01
        half = near * math.tan(math.radians(22.5))
        gl.glFrustum(-half * aspect, half * aspect, -half, half, near, 100.0)
        gl.glMatrixMode(0x1700)
        gl.glLoadIdentity()
        gl.glLightfv(0x4000, 0x1203, (ct.c_float * 4)(-1, 2, 3, 0))
        gl.glTranslatef(self.Pan[0], self.Pan[1], -self.Zoom)
        gl.glRotatef(self.Pitch, 1, 0, 0)
        gl.glRotatef(self.Yaw, 0, 1, 0)
        lo = self.Mesh.Positions.min(axis=0)
        hi = self.Mesh.Positions.max(axis=0)
        scale = 2.0 / max(float((hi - lo).max()), 1e-6)
        gl.glScalef(scale, scale, scale)
        gl.glTranslatef(*(-(lo + hi) * 0.5))
        if self.Plain:
            # Face orientation: front sides blue, back sides red; the wireframe, if on, is drawn over them.
            gl.glEnable(0x0B50)
            gl.glDisable(0x0DE1)
            gl.glPolygonMode(0x0408, 0x1B02)
            gl.glEnable(0x8037)
            gl.glPolygonOffset(1, 1)
            gl.glEnable(0x0B44)
            for side, color in ((0x0405, (0.25, 0.45, 1.0, 1)), (0x0404, (0.95, 0.25, 0.25, 1))):
                gl.glCullFace(side)
                gl.glColor4f(*color)
                gl.glCallList(self.Plain)
            gl.glDisable(0x0B44)
            gl.glDisable(0x8037)
            if not self.Wire:
                return
        if self.Wire:
            gl.glDisable(0x0B50)
        else:
            gl.glEnable(0x0B50)
        gl.glPolygonMode(0x0408, 0x1B01 if self.Wire else 0x1B02)
        gl.glCallList(self.List)
        gl.glPolygonMode(0x0408, 0x1B02)

    def mousePressEvent(self, Event):
        self.Last = Event.position()

    def mouseMoveEvent(self, Event):
        if self.Last is None:
            return
        delta = Event.position() - self.Last
        self.Last = Event.position()
        if Event.buttons() & Qt.MouseButton.LeftButton:
            self.Yaw += delta.x() * 0.5
            self.Pitch = max(-89, min(89, self.Pitch + delta.y() * 0.5))
        elif Event.buttons() & (Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton):
            self.Pan[0] += delta.x() * self.Zoom / max(1, self.height())
            self.Pan[1] -= delta.y() * self.Zoom / max(1, self.height())
        self.update()

    def wheelEvent(self, Event):
        self.Zoom = max(0.2, min(30, self.Zoom * math.exp(-Event.angleDelta().y() / 1200)))
        self.update()

    def mouseDoubleClickEvent(self, Event):
        self.Home()
