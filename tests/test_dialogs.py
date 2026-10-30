import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QValidator
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog, QFileDialog

from pywisp.config import REMOTE_KEYS, REMOTE_MULTI_TYPES, validateExperiments
from pywisp.experimentModules import ExperimentModule
from pywisp.settings import Settings
from pywisp.widgets.dialogs import DataIntDialog, DataTcpIpDialog, RemoteWidgetEdit, ShortcutCreator
from pywisp.widgets.fileselector import FileSelector

EXP = {
    'Model': {'gain': 2.5, 'offset': 0.0},
    'Trajectory': {'start': 1.0},
}


class Model(ExperimentModule):
    publicSettings = {'gain': 1.0, 'offset': 0.0}
    dataPoints = []


class Trajectory(ExperimentModule):
    publicSettings = {'start': 0.0}
    dataPoints = []


def acceptDialogs(monkeypatch, result=QDialog.DialogCode.Accepted):
    """ replace the modal event loop of the dialogs """
    monkeypatch.setattr(QDialog, 'exec', lambda self: result)


def isValid(lineEdit, text):
    return lineEdit.validator().validate(text, 0)[0] == QValidator.State.Acceptable


def test_int_dialog(qtbot):
    dialog = DataIntDialog(min=40, max=1000, current=100, unit='ms', title='Timer')
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == 'Timer'
    assert dialog._getData() == '100'
    assert isValid(dialog.data, '40') and isValid(dialog.data, '1000')
    assert not isValid(dialog.data, '1001')
    assert not isValid(dialog.data, 'abc')


@pytest.mark.parametrize("result, ok", [(QDialog.DialogCode.Accepted, True), (QDialog.DialogCode.Rejected, False)])
def test_int_dialog_get_data(monkeypatch, result, ok):
    acceptDialogs(monkeypatch, result)
    assert DataIntDialog.getData(current=42) == ('42', ok)


def test_tcp_dialog(qtbot):
    dialog = DataTcpIpDialog(ip='192.168.0.1', port=50007)
    qtbot.addWidget(dialog)
    assert dialog._getData() == ('192.168.0.1', '50007')
    assert isValid(dialog.ipData, '10.0.255.1')
    assert not isValid(dialog.ipData, '256.0.0.1')
    assert not isValid(dialog.ipData, '1.2.3')
    assert isValid(dialog.portData, '65535')
    assert not isValid(dialog.portData, '65536')


def test_tcp_dialog_get_data(monkeypatch):
    acceptDialogs(monkeypatch)
    assert DataTcpIpDialog.getData(ip='127.0.0.1', port=1234) == ('127.0.0.1', '1234', True)


def test_remote_edit_modules_and_parameters(qtbot):
    dialog = RemoteWidgetEdit(exp=EXP)
    qtbot.addWidget(dialog)
    modules = [dialog.moduleList.itemText(i) for i in range(dialog.moduleList.count())]
    assert modules == ['Model', 'Trajectory']

    def params():
        return [dialog.paramList.itemText(i) for i in range(dialog.paramList.count())]

    assert params() == ['gain', 'offset']
    dialog.moduleList.setCurrentText('Trajectory')
    assert params() == ['start']


def test_remote_edit_without_experiment(qtbot):
    dialog = RemoteWidgetEdit(exp=None)
    qtbot.addWidget(dialog)
    assert dialog.moduleList.count() == 0
    assert dialog._getData()['Module'] == ''


@pytest.mark.parametrize("widgetType", [t for t in REMOTE_KEYS if t not in REMOTE_MULTI_TYPES])
def test_remote_edit_creates_valid_widgets(qtbot, monkeypatch, widgetType):
    """ the dialog output must pass the validation of the config files """
    acceptDialogs(monkeypatch)
    msg, ok = RemoteWidgetEdit.getData(exp=EXP, widgetType=widgetType, name='w', Module='Model',
                                       Parameter='gain')
    assert ok
    assert msg['widgetType'] == widgetType
    assert (msg['Module'], msg['Parameter']) == ('Model', 'gain')
    for key in REMOTE_KEYS[widgetType]['required']:
        assert key in msg

    exp = dict(EXP, Name='exp', Remote={'w': msg})
    valid = validateExperiments([exp], {'Model': Model, 'Trajectory': Trajectory}, {})
    assert valid and 'w' in valid[0]['Remote']


def test_remote_edit_slider_start_value(monkeypatch):
    acceptDialogs(monkeypatch)
    msg, _ = RemoteWidgetEdit.getData(exp=EXP, widgetType='Slider', Module='Model', Parameter='gain')
    assert msg['startValue'] == 2.5
    msg, _ = RemoteWidgetEdit.getData(exp=None, widgetType='Slider')
    assert msg['startValue'] == 0


def test_remote_edit_existing_widget(qtbot):
    dialog = RemoteWidgetEdit(editWidget=True, exp=EXP, widgetType='Switch', name='sw',
                              valueOn='1', valueOff='0', shortcut='S', Module='Model', Parameter='offset')
    qtbot.addWidget(dialog)
    # the type of an existing widget cannot be changed
    assert not dialog.typeList.isEnabled()
    msg = dialog._getData()
    assert msg['name'] == 'sw'
    assert (msg['valueOn'], msg['valueOff'], msg['shortcut']) == ('1', '0', 'S')
    assert (msg['Module'], msg['Parameter']) == ('Model', 'offset')


def test_remote_edit_change_type(qtbot):
    dialog = RemoteWidgetEdit(exp=EXP)
    qtbot.addWidget(dialog)
    assert dialog.typeList.isEnabled()
    dialog.typeList.setCurrentText('Slider')
    dialog.minSliderText.setText('-1')
    dialog.maxSliderText.setText('1')
    dialog.stepSliderText.setText('0.1')
    msg = dialog._getData()
    assert msg['widgetType'] == 'Slider'
    assert (msg['minSlider'], msg['maxSlider'], msg['stepSlider']) == ('-1', '1', '0.1')


def test_remote_edit_multi_button(qtbot):
    targets = [{'Module': 'Model', 'Parameter': 'gain', 'value': '0'},
               {'Module': 'Trajectory', 'Parameter': 'start', 'value': '1.5'}]
    dialog = RemoteWidgetEdit(editWidget=True, exp=EXP, widgetType='MultiButton', name='stop',
                              targets=targets, shortcut='Esc')
    qtbot.addWidget(dialog)
    # module and parameter are chosen per target
    assert not dialog.mainLayout.isRowVisible(dialog.moduleList)
    msg = dialog._getData()
    assert msg['targets'] == targets
    assert 'Module' not in msg and 'Parameter' not in msg

    dialog.addTargetRow(Module='Model', Parameter='offset', value=2)
    dialog.removeTargetRow(dialog.targetRows[0])
    assert dialog._getData()['targets'] == [targets[1], {'Module': 'Model', 'Parameter': 'offset', 'value': '2'}]

    exp = dict(EXP, Name='exp', Remote={'stop': dialog._getData()})
    valid = validateExperiments([exp], {'Model': Model, 'Trajectory': Trajectory}, {})
    assert valid and 'stop' in valid[0]['Remote']


def test_remote_edit_change_type_to_multi_button(qtbot):
    dialog = RemoteWidgetEdit(exp=EXP)
    qtbot.addWidget(dialog)
    dialog.typeList.setCurrentText('MultiButton')
    assert len(dialog.targetRows) == 1
    assert dialog._getData()['targets'] == [{'Module': 'Model', 'Parameter': 'gain', 'value': '0.0'}]
    dialog.typeList.setCurrentText('PushButton')
    assert dialog.mainLayout.isRowVisible(dialog.moduleList)


def test_shortcut_creator(qtbot):
    field = ShortcutCreator()
    qtbot.addWidget(field)
    QTest.keyClick(field, Qt.Key.Key_A)
    assert field.getKeySequence() == 'A'
    assert field.text() == 'A'
    QTest.keyClick(field, Qt.Key.Key_F5)
    assert field.getKeySequence() == 'F5'
    # modifiers alone are no shortcut
    QTest.keyClick(field, Qt.Key.Key_Shift)
    assert field.text() == ''


class TestFileSelector:
    formats = ["CSV Data (*.csv)", "PNG Image (*.png)"]

    def select(self, monkeypatch, path, flt):
        calls = []

        def fake(parent, text, file, filterStr, selected):
            calls.append((file, selected))
            return path, flt

        monkeypatch.setattr(QFileDialog, 'getSaveFileName', staticmethod(fake))
        return FileSelector(self.formats).getSaveFileName(), calls

    def test_selection_is_remembered(self, monkeypatch, tmp_path):
        path = str(tmp_path / "data.png")
        selected, calls = self.select(monkeypatch, path, self.formats[1])
        assert selected == path
        # default suggestion before anything was stored
        assert calls[0][1] == self.formats[0]

        st = Settings()
        assert st.value('path/export_dir') == str(tmp_path)
        assert st.value('path/export_ext') == '.png'

        _, calls = self.select(monkeypatch, path, self.formats[1])
        assert calls[0] == (str(tmp_path / "export.png"), self.formats[1])

    def test_extension_from_filter(self, monkeypatch, tmp_path):
        selected, _ = self.select(monkeypatch, str(tmp_path / "data"), self.formats[1])
        assert selected == str(tmp_path / "data.png")

    def test_unknown_extension(self, monkeypatch, tmp_path, caplog):
        selected, _ = self.select(monkeypatch, str(tmp_path / "data.txt"), self.formats[0])
        assert selected is None
        assert "unknown" in caplog.text

    def test_aborted(self, monkeypatch):
        selected, _ = self.select(monkeypatch, '', '')
        assert selected is None
