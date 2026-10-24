from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

from ..utility import QtTest
from ...widgets.SpaceGroupSelector import SpaceGroupSelector


class SpaceGroupSelectorTest(QtTest):
    def test_reference_catalogue_shows_both_number_and_symbol(self):
        selector = SpaceGroupSelector()
        assert selector.count() == 230
        assert selector.itemText(0) == '1 — P1'
        assert selector.itemText(224) == '225 — Fm-3m'
        selector.set_applied_group('Fm-3m', 225)
        assert selector.value() == 'Fm-3m'
        assert selector.currentText() == '225 — Fm-3m'
        selector.close()

    def test_search_matches_number_and_spaced_or_compact_symbol(self):
        selector = SpaceGroupSelector()
        for query, expected in [('225', '225 — Fm-3m'),
                                ('P21/c', '14 — P21/c'),
                                ('p 21 / c', '14 — P21/c')]:
            selector.completer().setCompletionPrefix(query)
            model = selector.completer().completionModel()
            matches = [model.index(row, 0).data() for row in range(model.rowCount())]
            assert expected in matches, (query, matches)
        selector.close()

    def test_current_non_reference_setting_is_preserved(self):
        selector = SpaceGroupSelector()
        selector.set_applied_group('P21/n', 14)
        assert selector.currentText() == '14 — P21/n [b2]'
        assert selector.value() == 'P21/n'
        selector.setCurrentIndex(13)
        assert selector.currentText() == '14 — P21/c'
        assert selector.value() == '14'
        selector.close()

    def test_keyboard_completion_selects_a_catalogue_entry(self):
        selector = SpaceGroupSelector()
        selector.show()
        selector.lineEdit().setFocus()
        QTest.keyClicks(selector.lineEdit(), 'Pm-3m')
        QtWidgets.QApplication.processEvents()
        completer = selector.completer()
        completer.setCompletionPrefix('Pm-3m')
        completer.complete()
        QtWidgets.QApplication.processEvents()
        completer.popup().setCurrentIndex(completer.completionModel().index(0, 0))
        QTest.keyClick(completer.popup(), QtCore.Qt.Key_Return)
        assert selector.currentText() == '221 — Pm-3m'
        assert selector.value() == '221'
        selector.close()
