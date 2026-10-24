# SPDX-License-Identifier: MIT

from functools import lru_cache

from qtpy import QtWidgets, QtCore

from ..model.util.phasesmith import resolve_space_group


@lru_cache(maxsize=1)
def _reference_groups():
    from phasesmith.io.space_groups import space_group_by_number

    return tuple((number, info.hm_symbol, info.hall_symbol, info.setting)
                 for number in range(1, 231)
                 for info in (space_group_by_number(number),))


class _SpaceGroupCompleter(QtWidgets.QCompleter):
    def splitPath(self, text):
        # Catalogue symbols are compact, but accept searches such as "F m -3 m".
        return [text.strip() if '—' in text else ''.join(text.split())]


class SpaceGroupSelector(QtWidgets.QComboBox):
    """Searchable reference groups, retaining a material's explicit setting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(16)
        self.setMaxVisibleItems(12)
        self._applied_symbol = self._applied_text = ''
        self._reference_halls = {}
        for number, symbol, hall, setting in _reference_groups():
            self.addItem(f'{number} — {symbol.replace(" ", "")}', str(number))
            self.setItemData(number - 1,
                             f'No. {number}: {symbol}\nReference setting: {setting or "standard"}'
                             f'\nHall symbol: {hall}', QtCore.Qt.ToolTipRole)
            self._reference_halls[number] = hall
        completer = _SpaceGroupCompleter(self.model(), self)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self.setCompleter(completer)
        self.lineEdit().setPlaceholderText('Search symbol or number…')
        self.setCurrentIndex(-1)

    def value(self):
        text = self.currentText().strip()
        if text == self._applied_text:
            return self._applied_symbol
        index = self.findText(text)
        return self.itemData(index) if index >= 0 else text

    def set_applied_group(self, symbol, number=None):
        symbol = str(symbol or '')
        blocker = QtCore.QSignalBlocker(self)
        index = -1
        if symbol:
            try:
                _, info = resolve_space_group(symbol)
            except ValueError:
                info = None
            if info is not None and self._reference_halls.get(info.number) == info.hall_symbol:
                index = info.number - 1
            else:
                setting = f' [{info.setting}]' if info is not None and info.setting else ''
                label = f'{number or (info.number if info else "?")} — {symbol.replace(" ", "")}{setting}'
                index = self.findText(label)
                if index < 0:
                    self.addItem(label, symbol)
                    index = self.count() - 1
                    self.setItemData(index, f'Material setting: {symbol}', QtCore.Qt.ToolTipRole)
        self.setCurrentIndex(index)
        if index < 0:
            self.setEditText('')
        self._applied_symbol = symbol
        self._applied_text = self.currentText().strip()
        del blocker
