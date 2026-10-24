# SPDX-License-Identifier: MIT

from qtpy import QtWidgets

from .ElementPickerDialog import ElementPickerDialog


class AtomicSiteDialog(QtWidgets.QDialog):
    def __init__(self, element='', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Add atomic site')
        self.element = element
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.element_button = QtWidgets.QPushButton(element or 'Choose element…')
        self.element_button.clicked.connect(self.choose_element)
        form.addRow('Element', self.element_button)
        self.coordinates = {}
        for key in ('x', 'y', 'z'):
            field = QtWidgets.QDoubleSpinBox()
            field.setRange(-100000, 100000)
            field.setDecimals(6)
            field.setSingleStep(.01)
            self.coordinates[key] = field
            form.addRow(f'{key} (fractional)', field)
        self.occupancy = QtWidgets.QDoubleSpinBox()
        self.occupancy.setRange(0, 1)
        self.occupancy.setDecimals(4)
        self.occupancy.setSingleStep(.1)
        self.occupancy.setValue(1.)
        form.addRow('Occupancy', self.occupancy)
        layout.addLayout(form)
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setText('Add site')
        self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(bool(element))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.setMinimumWidth(300)

    def choose_element(self):
        dialog = ElementPickerDialog(self.element, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.element = dialog.element
            self.element_button.setText(self.element)
            self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(True)

    def site(self):
        return {'element': self.element, 'occupancy': self.occupancy.value(),
                **{key: field.value() for key, field in self.coordinates.items()}}
