import re

import pytest
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from pywisp.visualization import MplVisualizer, Visualizer


class LineVisualizer(MplVisualizer):
    """ minimal visualizer as users write them """

    def __init__(self, qWidget, qLayout):
        super().__init__(qWidget, qLayout)
        self.line, = self.axes.plot([], [])

    def update(self, dataPoints):
        self.line.set_data([0, 1], [0, dataPoints['y']])
        self.canvas.draw_idle()
        self.saveIfChecked()


@pytest.fixture
def visu(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    return LineVisualizer(widget, QVBoxLayout())


def test_base_class_is_abstract():
    with pytest.raises(TypeError):
        Visualizer()

    class Incomplete(Visualizer):
        def update(self, dataPoints):
            pass

    with pytest.raises(TypeError):
        Incomplete()


def test_canvas_is_embedded(visu):
    assert visu.qWidget.layout() is visu.qLayout
    assert visu.qLayout.indexOf(visu.canvas) == 0
    assert visu.canvas.parent() is visu.qWidget


def test_no_pictures_by_default(visu, tmp_path):
    visu.setExpName('exp')
    visu.startAnimation()
    visu.update({'y': 1.0})
    assert visu.fileNameCounter == 0
    # the directory is only created when pictures are saved
    assert list(tmp_path.iterdir()) == []


def test_save_animation(visu, tmp_path):
    visu.setExpName('my exp/1')
    visu.checkSaveAnimation(True)
    picDir = tmp_path / 'ani_my_exp_1'
    assert visu.picturePath == str(picDir)
    assert picDir.is_dir()

    visu.startAnimation()
    assert re.fullmatch(r"\d{2}_\d{2}_\d{4}_\d{2}_\d{2}_\d{2}_", visu.timeStamp)
    for y in (1.0, 2.0):
        visu.update({'y': y})
    files = sorted(p.name for p in picDir.iterdir())
    assert files == [visu.timeStamp + '0000.png', visu.timeStamp + '0001.png']
    assert (picDir / files[0]).read_bytes()[:4] == b'\x89PNG'
    assert visu.fileNameCounter == visu.frameCounter == 2

    # a new run starts counting again
    visu.startAnimation()
    assert visu.fileNameCounter == visu.frameCounter == 0


def test_save_without_experiment_name(visu, tmp_path):
    visu.checkSaveAnimation(True)
    visu.startAnimation()
    visu.update({'y': 1.0})
    assert visu.picturePath is None
    assert list(tmp_path.iterdir()) == []


def test_changing_experiment_changes_directory(visu, tmp_path):
    visu.setExpName('first')
    visu.checkSaveAnimation(True)
    visu.setExpName('second')
    visu.startAnimation()
    visu.update({'y': 1.0})
    assert len(list((tmp_path / 'ani_second').iterdir())) == 1
    assert list((tmp_path / 'ani_first').iterdir()) == []


class TestVtk:
    @pytest.fixture
    def renderer(self):
        vtk = pytest.importorskip("vtk")
        return vtk.vtkRenderer()

    @pytest.fixture
    def visuClass(self, renderer):
        from pywisp.visualization import VtkVisualizer

        class Visu(VtkVisualizer):
            def update(self, dataPoints):
                pass

            def saveIfChecked(self):
                return False

        return Visu

    @pytest.fixture
    def visu(self, visuClass, renderer):
        return visuClass(renderer)

    def test_requires_renderer(self, visuClass):
        with pytest.raises(AssertionError):
            visuClass(object())

    def test_reset_camera_restores_pose(self, visu, renderer):
        camera = renderer.GetActiveCamera()
        camera.SetPosition(1, 2, 3)
        camera.SetFocalPoint(0, 0, 0)
        visu.saveCameraPose()
        assert visu.canResetView

        camera.SetPosition(10, 10, 10)
        visu.resetCamera()
        assert camera.GetPosition() == pytest.approx((1, 2, 3))

    def test_reset_camera_without_pose(self, visu, renderer):
        assert not visu.canResetView
        visu.resetCamera()
