# SPDX-License-Identifier: MIT
"""Compact element selection shared by the atomic-site table and add form."""

from qtpy import QtWidgets, QtCore

from ..model.util.phasesmith import normalize_element_symbol


class ElementPickerDialog(QtWidgets.QDialog):
    def __init__(self, element='', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Choose element')
        self.setStyleSheet('''
            QToolButton {
                padding: 0; margin: 0; min-width: 0; min-height: 0;
                border: 1px solid palette(mid); border-radius: 3px;
                font-size: 11px;
            }
            QToolButton:disabled { color: palette(mid); border-color: palette(dark); }
        ''')
        self.element = element
        layout = QtWidgets.QVBoxLayout(self)
        self.symbol_input = QtWidgets.QLineEdit(element)
        self.symbol_input.setPlaceholderText('Type an element symbol, e.g. Fe or O')
        self.symbol_input.selectAll()
        self.symbol_input.returnPressed.connect(self.accept)
        layout.addWidget(self.symbol_input)
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(3)
        rows = [
            [(0, 'H'), (17, 'He')],
            list(enumerate('Li Be'.split())) + list(enumerate('B C N O F Ne'.split(), 12)),
            list(enumerate('Na Mg'.split())) + list(enumerate('Al Si P S Cl Ar'.split(), 12)),
            list(enumerate('K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr'.split())),
            list(enumerate('Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe'.split())),
            [(0, 'Cs'), (1, 'Ba')] + list(enumerate('Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn'.split(), 3)),
            [(0, 'Fr'), (1, 'Ra')] + list(enumerate('Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og'.split(), 3)),
            list(enumerate('La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu'.split(), 2)),
            list(enumerate('Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr'.split(), 2)),
        ]
        self.element_buttons = {}
        import xraydb

        for row, entries in enumerate(rows):
            for column, symbol in entries:
                button = QtWidgets.QToolButton()
                button.setText(symbol)
                button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
                button.setFixedSize(29, 29)
                button.setToolTip(xraydb.atomic_name(symbol).capitalize())
                button.setCheckable(True)
                button.setChecked(symbol == element)
                try:
                    normalize_element_symbol(symbol)
                except ValueError:
                    button.setEnabled(False)
                    button.setToolTip(button.toolTip() + ' — no X-ray scattering data available')
                button.clicked.connect(lambda _checked=False, selected=symbol: self.choose(selected))
                grid.addWidget(button, row + (1 if row >= 7 else 0), column)
                self.element_buttons[symbol] = button
        for row, text in ((5, '57–71'), (6, '89–103')):
            label = QtWidgets.QLabel(text)
            label.setAlignment(QtCore.Qt.AlignCenter)
            grid.addWidget(label, row, 2)
        layout.addLayout(grid)
        self.error_label = QtWidgets.QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose(self, symbol):
        self.symbol_input.setText(symbol)
        self.accept()

    def accept(self):
        try:
            self.element = normalize_element_symbol(self.symbol_input.text())
        except ValueError as error:
            self.error_label.setText(str(error))
            self.error_label.show()
            return
        super().accept()
