import os
from pathlib import Path
import sys
import traceback

from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QSurfaceFormat, QFont
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QSlider, QSpinBox, QDoubleSpinBox, QCheckBox,
    QFileDialog, QMessageBox, QGroupBox, QScrollArea, QLayout)

from core import Bundle
from viewer import View


class Job(QThread):
    Done = Signal(object)
    Failed = Signal(str)

    def __init__(self, Function):
        super().__init__()
        self.Function = Function

    def run(self):
        try:
            self.Done.emit(self.Function())
        except Exception as error:
            self.Failed.emit(str(error))


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.Bundle = None
        self.Job = None
        self.Busy = False
        self.setWindowTitle('Clothing Mesh Editor 0.5')
        self.resize(1320, 900)
        self.setMinimumSize(1000, 700)
        self.setAcceptDrops(True)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        top = QHBoxLayout()
        self.OpenButton = QPushButton('Open .bundle')
        self.OpenButton.clicked.connect(self.OpenDialog)
        self.Filename = QLabel('Open a clothing bundle or drop it here')
        top.addWidget(self.OpenButton)
        top.addWidget(self.Filename, 1)
        layout.addLayout(top)
        body = QHBoxLayout()
        layout.addLayout(body, 1)
        left = QVBoxLayout()
        self.Stats = QLabel('TRIANGLES  —\nVERTICES   —')
        self.Stats.setStyleSheet('color: #69f59b; background: #10151b; padding: 12px;')
        self.Stats.setFont(QFont('Consolas', 11))
        left.addWidget(self.Stats)
        self.View = View()
        left.addWidget(self.View, 1)
        help_label = QLabel('Left drag: orbit    Right drag: pan    Wheel: zoom    Double click: frame mesh')
        help_label.setStyleSheet('color: #95a1b1; padding: 5px;')
        left.addWidget(help_label)
        body.addLayout(left, 1)
        self.Panel = QWidget()
        right = QVBoxLayout(self.Panel)
        right.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        right.setContentsMargins(8, 0, 0, 0)
        right.addWidget(QLabel('MESH'))
        self.Meshes = QComboBox()
        self.Meshes.currentIndexChanged.connect(self.Select)
        mesh_row = QHBoxLayout()
        mesh_row.addWidget(self.Meshes, 1)
        self.Topology = QComboBox()
        self.Topology.addItems(['Triangles', 'Quads'])
        self.Topology.setToolTip('Wireframe display only. Quads hide diagonals of suitable triangle pairs; unmatched triangles remain visible.')
        self.Topology.currentIndexChanged.connect(self.TopologyChanged)
        mesh_row.addWidget(self.Topology)
        right.addLayout(mesh_row)
        group = QGroupBox('Simplification')
        box = QVBoxLayout(group)
        self.Mode = QComboBox()
        self.Mode.addItems(['Preserve boundaries', 'Flexible boundaries'])
        self.Mode.setToolTip('UV seams are preserved unless Aggressive simplification is enabled.')
        box.addWidget(self.Mode)
        self.Aggressive = QCheckBox('Aggressive simplification (relax seams)')
        self.Aggressive.setChecked(False)
        self.Aggressive.setToolTip('Off = original simplifier. On = allows collapses across attribute seams; UVs and shading can change. Material partitions, detail protection, boundary mode and allowed error still apply.')
        box.addWidget(self.Aggressive)
        box.addWidget(QLabel('Triangles to keep'))
        self.Target = QSpinBox()
        self.Target.setRange(1, 100000000)
        self.Target.setGroupSeparatorShown(True)
        self.Target.valueChanged.connect(self.TargetChanged)
        box.addWidget(self.Target)
        self.Slider = QSlider(Qt.Orientation.Horizontal)
        self.Slider.setRange(1, 100)
        self.Slider.setValue(50)
        self.Slider.valueChanged.connect(self.PercentChanged)
        box.addWidget(self.Slider)
        self.Percent = QLabel('Keep 50%')
        box.addWidget(self.Percent)
        box.addWidget(QLabel('Allowed error (% of mesh size)'))
        self.Error = QDoubleSpinBox()
        self.Error.setRange(0.01, 25)
        self.Error.setDecimals(2)
        self.Error.setValue(1.0)
        self.Error.setSuffix(' %')
        box.addWidget(self.Error)
        self.DetailLabel = QLabel('Fine detail protection: 0 / 100')
        box.addWidget(self.DetailLabel)
        self.Detail = QSlider(Qt.Orientation.Horizontal)
        self.Detail.setRange(0, 100)
        self.Detail.setValue(0)
        self.Detail.setToolTip('Protects tight curves and sharp geometric details. 0 = off, reduces as before the slider existed; 100 = strongest protection. Apply to update the mesh. Texture-only details are not detected.')
        self.Detail.valueChanged.connect(lambda value: self.DetailLabel.setText(f'Fine detail protection: {value} / 100'))
        box.addWidget(self.Detail)
        detail_note = QLabel('0 = off, reduces as before. Higher = protect more small curves, keeps more triangles. Apply to update.')
        detail_note.setWordWrap(True)
        detail_note.setStyleSheet('color: #95a1b1;')
        box.addWidget(detail_note)
        self.Target.setToolTip('Target is approximate. Aggressive mode relaxes attribute seams. Material partitions are preserved. Each Apply starts from the original mesh.')
        self.Apply = QPushButton('Apply simplification')
        self.Apply.setStyleSheet('background: #276843; font-weight: bold; padding: 10px;')
        self.Apply.clicked.connect(self.Simplify)
        box.addWidget(self.Apply)
        self.Reset = QPushButton('Reset selected mesh')
        self.Reset.clicked.connect(self.ResetMesh)
        box.addWidget(self.Reset)
        right.addWidget(group)
        self.Textured = QCheckBox('Show texture')
        self.Textured.setChecked(True)
        self.Wire = QCheckBox('Wireframe')
        self.Original = QCheckBox('Compare: show original')
        self.Orientation = QCheckBox('Face orientation (front blue, back red)')
        self.Orientation.setToolTip('Front sides of the triangles blue, back sides red. Garments drawn one-sided in the game show only the blue side.')
        for checkbox in (self.Textured, self.Wire, self.Original, self.Orientation):
            checkbox.toggled.connect(self.Display)
            right.addWidget(checkbox)
        frame = QPushButton('Frame mesh')
        frame.clicked.connect(self.View.Home)
        right.addWidget(frame)
        self.Flip = QPushButton('Flip normals outward')
        self.Flip.setToolTip('Turns every piece of the selected mesh that faces inward so it faces away from the wearer, as Blender\'s Recalculate Outside: reverses its triangles and negates its normals, morph normals and tangent sign. Pieces already facing out stay. Reset selected mesh undoes it. Exported with the other changes.')
        self.Flip.clicked.connect(self.FlipNormals)
        right.addWidget(self.Flip)
        self.Result = QLabel('')
        self.Result.setWordWrap(True)
        right.addWidget(self.Result)
        right.addStretch()
        export_note = QLabel('Exports all applied mesh changes, textures and updated catalogs. Original mod files are kept intact.')
        export_note.setWordWrap(True)
        right.addWidget(export_note)
        self.ExportButton = QPushButton('Export optimized mod...')
        self.ExportButton.clicked.connect(self.Export)
        right.addWidget(self.ExportButton)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(340)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self.Panel)
        body.addWidget(scroll)
        self.Panel.setEnabled(False)
        self.Status = QLabel('Ready')
        layout.addWidget(self.Status)

    def Work(self, Function, Finished, Message):
        if self.Busy:
            return
        self.Busy = True
        self.OpenButton.setEnabled(False)
        self.Panel.setEnabled(False)
        self.Status.setText(Message)
        self.Job = Job(Function)
        self.Job.Done.connect(Finished)
        self.Job.Failed.connect(self.Failure)
        self.Job.finished.connect(self.Idle)
        self.Job.start()

    def Idle(self):
        self.Busy = False
        self.OpenButton.setEnabled(True)
        self.Panel.setEnabled(self.Bundle is not None)
        self.Refresh()

    def Failure(self, Message):
        self.Status.setText('Operation failed. Previous mesh is unchanged.')
        QMessageBox.warning(self, 'Clothing Mesh Editor', Message)

    def OpenDialog(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open clothing bundle', str(Path.home() / 'Documents'), 'Unity bundles (*.bundle);;All files (*)')
        if path:
            self.Open(path)

    def HasChanges(self):
        return self.Bundle and any(mesh.Current is not mesh.Parts or mesh.Flip is not None for mesh in self.Bundle.Meshes)

    def Open(self, Filename):
        if self.Busy:
            return
        if self.HasChanges() and QMessageBox.question(self, 'Open another bundle', 'Discard the current preview changes?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self.Work(lambda: Bundle(Filename), self.Loaded, 'Reading meshes, materials and textures...')

    def Loaded(self, Data):
        self.Bundle = Data
        self.Filename.setText(Data.Path.name)
        self.Filename.setToolTip(str(Data.Path))
        self.Meshes.blockSignals(True)
        self.Meshes.clear()
        for mesh in Data.Meshes:
            self.Meshes.addItem(f'{mesh.Name}  ({mesh.Triangles():,} tris)')
        self.Meshes.blockSignals(False)
        self.Select(0)
        self.Status.setText('Loaded. Select a target and click Apply.')
        if Data.Warnings:
            QMessageBox.warning(self, 'Loaded with warnings', '\n'.join(Data.Warnings))

    def Select(self, Index):
        if self.Bundle is None or Index < 0:
            return
        mesh = self.Bundle.Meshes[Index]
        self.Target.setMaximum(max(1, mesh.Triangles(True)))
        self.Target.setValue(max(1, mesh.Triangles(True) // 2))
        self.View.SetMesh(mesh)
        self.View.Home()
        self.Refresh()

    def TargetChanged(self, Value):
        if self.Bundle is None or self.Meshes.currentIndex() < 0:
            return
        total = self.Bundle.Meshes[self.Meshes.currentIndex()].Triangles(True)
        percent = Value * 100 / max(1, total)
        self.Slider.blockSignals(True)
        self.Slider.setValue(max(1, round(percent)))
        self.Slider.blockSignals(False)
        self.Percent.setText(f'Keep {percent:.1f}%  /  remove {100 - percent:.1f}%')

    def PercentChanged(self, Value):
        if self.View.Mesh:
            self.Target.setValue(max(1, round(self.View.Mesh.Triangles(True) * Value / 100)))

    def Simplify(self):
        mesh = self.View.Mesh
        target, error, mode = self.Target.value(), self.Error.value() / 100, self.Mode.currentIndex()
        detail = self.Detail.value()
        aggressive = self.Aggressive.isChecked()
        def finished(result):
            mesh.Current, mesh.Error = result
            mesh.DetailLevel = detail
            mesh.Aggressive = aggressive
            self.Original.setChecked(False)
            self.View.Dirty = True
            self.View.update()
            self.Refresh()
            limit = ' Target limited by detail protection, seams, topology or the error budget.' if mesh.Triangles() > target + 2 else ''
            self.Status.setText(f'Applied: {mesh.Triangles():,} triangles. Target: {target:,}.{limit}')
        self.Work(lambda: mesh.Simplify(target, error, mode, detail, aggressive), finished, 'Simplifying mesh...')

    def ResetMesh(self):
        self.View.Mesh.Current = self.View.Mesh.Parts
        self.View.Mesh.Error = 0
        self.View.Mesh.DetailLevel = 0
        self.View.Mesh.Aggressive = False
        self.View.Mesh.Flip = None
        self.View.Mesh.Turned = (0, 0)
        self.View.Dirty = True
        self.View.update()
        self.Refresh()
        self.Status.setText('Selected mesh restored to original.')

    def FlipNormals(self):
        mesh = self.View.Mesh
        def finished(result):
            inward, mesh.Turned = result
            mesh.Flip = inward if inward.any() else None
            self.Original.setChecked(False)
            self.Orientation.setChecked(True)
            self.View.Dirty = True
            self.View.update()
            self.Refresh()
            turned, pieces = mesh.Turned
            self.Status.setText(f'{mesh.Name}: {turned} of {pieces} pieces turned to face outward. Export to keep it.' if turned else
                                f'{mesh.Name}: all {pieces} pieces already face outward.')
        self.Work(mesh.Outward, finished, 'Finding the outer side of each piece...')

    def Display(self):
        self.View.Original = self.Original.isChecked()
        self.View.Wire = self.Wire.isChecked()
        self.View.Quads = self.Topology.currentIndex() == 1
        self.View.Textured = self.Textured.isChecked()
        self.View.Orientation = self.Orientation.isChecked()
        self.View.Dirty = True
        self.View.update()
        self.Refresh()

    def TopologyChanged(self):
        self.Wire.setChecked(True)
        self.Display()

    def Refresh(self):
        mesh = self.View.Mesh
        if mesh is None:
            return
        triangles = mesh.Triangles(self.Original.isChecked())
        vertices = len(mesh.Positions) if self.Original.isChecked() else mesh.Vertices()
        shapes = len(mesh.Tree.get('m_Shapes', {}).get('channels', []))
        textures = sum(m['Texture'] is not None for m in mesh.Materials)
        self.Stats.setText(f'{"ORIGINAL" if self.Original.isChecked() else "PREVIEW"}    TRIANGLES {triangles:,}    VERTICES {vertices:,}\nSUBMESHES {len(mesh.Parts)}    TEXTURED MATERIALS {textures}    MORPHS {shapes}')
        self.Result.setText(f'Original: {mesh.Triangles(True):,} triangles\nApplied: {mesh.Triangles():,} triangles\nVertices: {len(mesh.Positions):,} → {mesh.Vertices():,}\nReported simplification error: {mesh.Error * 100:.2f}%\nDetail protection applied: {mesh.DetailLevel} / 100')
        self.Result.setText(self.Result.text() + f'\nAggressive applied: {"On" if mesh.Aggressive else "Off"}\nPieces turned outward: {f"{mesh.Turned[0]} of {mesh.Turned[1]}" if mesh.Flip is not None else "none"}')
        self.ExportButton.setEnabled(bool(self.HasChanges()))

    def Export(self):
        parent = QFileDialog.getExistingDirectory(self, 'Choose output parent folder (a new mod folder will be created)', str(Path(__file__).parent / 'Exports'))
        if not parent:
            return
        destination = Path(parent) / self.Bundle.Path.parent.name
        if destination.exists():
            QMessageBox.warning(self, 'Folder already exists', f'{destination}\nChoose a different parent folder. Existing files will not be overwritten.')
            return
        def finished(result):
            self.Status.setText(f'Export verified: {result[0]}')
            QMessageBox.information(self, 'Export complete', f'Saved and reopened successfully:\n{result[0]}\n\nWith the game closed, back up the original mod folder, then replace its contents with these exported files. Keep the original folder name.\n\nAnimation and loading in the game still need an in-game check.')
        self.Work(lambda: self.Bundle.Export(destination), finished, 'Writing bundle, updating catalogs and verifying export...')

    def dragEnterEvent(self, Event):
        if not self.Busy and Event.mimeData().hasUrls():
            Event.acceptProposedAction()

    def dropEvent(self, Event):
        urls = Event.mimeData().urls()
        if urls:
            self.Open(urls[0].toLocalFile())

    def closeEvent(self, Event):
        if self.Busy:
            Event.ignore()
            return
        if self.HasChanges() and QMessageBox.question(self, 'Close editor', 'Close the editor? Any changes not exported will be lost.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            Event.ignore()
            return
        Event.accept()


def Main():
    surface = QSurfaceFormat()
    surface.setVersion(2, 1)
    surface.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    surface.setDepthBufferSize(24)
    surface.setSamples(4)
    QSurfaceFormat.setDefaultFormat(surface)
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet('QWidget { background: #1b222c; color: #e0e7ef; font-size: 13px; } QPushButton, QComboBox, QSpinBox, QDoubleSpinBox { background: #303c4d; padding: 7px; border: 1px solid #465469; border-radius: 4px; } QPushButton:hover { background: #40516a; } QPushButton:disabled { color: #738093; } QGroupBox { border: 1px solid #465469; margin-top: 15px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; } QSlider::groove:horizontal { height: 5px; background: #465469; } QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: #6ce49b; border-radius: 6px; }')
    window = Window()
    window.show()
    if len(sys.argv) > 1:
        window.Open(sys.argv[1])
    sys.exit(app.exec())


if __name__ == '__main__':
    def failure(Type, Value, Trace):
        Path(__file__).with_name('error.log').write_text(''.join(traceback.format_exception(Type, Value, Trace)), encoding='utf-8')
        if QApplication.instance():
            QMessageBox.critical(None, 'Clothing Mesh Editor', str(Value))
    sys.excepthook = failure
    Main()
