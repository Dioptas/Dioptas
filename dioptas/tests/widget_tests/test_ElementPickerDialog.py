from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

from ..utility import QtTest
from ...widgets.ElementPickerDialog import ElementPickerDialog
from ...widgets.AtomicSiteDialog import AtomicSiteDialog


class ElementPickerDialogTest(QtTest):
    def test_periodic_table_selection_and_current_element(self):
        dialog = ElementPickerDialog('O')
        assert len(dialog.element_buttons) == 118
        assert dialog.element_buttons['O'].isChecked()
        dialog.element_buttons['Fe'].click()
        assert dialog.result() == QtWidgets.QDialog.Accepted
        assert dialog.element == 'Fe'
        dialog.close()

    def test_keyboard_entry_and_invalid_symbol(self):
        dialog = ElementPickerDialog()
        dialog.show()
        dialog.symbol_input.setText('Xx')
        dialog.accept()
        assert dialog.result() != QtWidgets.QDialog.Accepted
        assert dialog.error_label.isVisible()
        dialog.symbol_input.setText('si')
        QTest.keyClick(dialog.symbol_input, QtCore.Qt.Key_Return)
        assert dialog.result() == QtWidgets.QDialog.Accepted
        assert dialog.element == 'Si'
        dialog.close()

    def test_add_form_requires_element_and_returns_fractional_coordinates(self):
        dialog = AtomicSiteDialog()
        assert not dialog.buttons.button(QtWidgets.QDialogButtonBox.Ok).isEnabled()
        dialog.close()
        dialog = AtomicSiteDialog('O')
        dialog.coordinates['x'].setValue(.125)
        dialog.occupancy.setValue(.5)
        assert dialog.site() == {'element': 'O', 'x': .125, 'y': 0., 'z': 0., 'occupancy': .5}
        dialog.close()
