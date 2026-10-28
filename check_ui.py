import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtCore import QTimer
from app import Window
from core import Bundle

surface = QSurfaceFormat()
surface.setVersion(2, 1)
surface.setDepthBufferSize(24)
surface.setSamples(4)
surface.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
QSurfaceFormat.setDefaultFormat(surface)
app = QApplication([])
app.setStyle('Fusion')
app.setStyleSheet('QWidget { background: #1b222c; color: #e0e7ef; font-size: 13px; } QPushButton, QComboBox, QSpinBox, QDoubleSpinBox { background: #303c4d; padding: 7px; border: 1px solid #465469; border-radius: 4px; } QGroupBox { border: 1px solid #465469; margin-top: 15px; padding-top: 15px; }')
window = Window()
assert not window.Aggressive.isChecked()
window.Loaded(Bundle(sys.argv[1]))
window.Idle()
window.show()

def capture():
    print('OpenGL valid:', window.View.isValid(), 'version:', window.View.context().format().majorVersion(), flush=True)
    window.grab().save(str(Path(__file__).with_name('preview.png')))
    window.Target.setValue(36477)
    window.Detail.setValue(75)
    window.Aggressive.setChecked(True)
    assert '75 / 100' in window.DetailLabel.text()
    window.Simplify()
    QTimer.singleShot(1500, after)

def after():
    if window.Busy:
        QTimer.singleShot(300, after)
        return
    assert window.View.Mesh.Triangles() < window.View.Mesh.Triangles(True)
    assert window.View.Mesh.DetailLevel == 75
    assert window.View.Mesh.Aggressive
    window.grab().save(str(Path(__file__).with_name('preview_optimized.png')))
    window.Original.setChecked(True)
    window.Wire.setChecked(True)
    QTimer.singleShot(500, finish)

def finish():
    window.grab().save(str(Path(__file__).with_name('preview_wire.png')))
    window.Topology.setCurrentIndex(1)
    QTimer.singleShot(500, quads)

def quads():
    assert window.View.Quads and window.View.Wire
    window.grab().save(str(Path(__file__).with_name('preview_quads.png')))
    assert sum(len(e) for e in window.View.Edges) > 0
    window.Topology.setCurrentIndex(0)
    assert not window.View.Quads
    window.ResetMesh()
    assert window.View.Mesh.Current is window.View.Mesh.Parts
    assert window.View.Mesh.DetailLevel == 0
    assert not window.View.Mesh.Aggressive
    print('UI apply / compare / triangle-quads switch / reset: PASS', flush=True)
    app.quit()

QTimer.singleShot(1500, capture)
QTimer.singleShot(20000, app.quit)
app.exec()
