# SPDX-License-Identifier: MIT

from qtpy import QtWidgets, QtCore

from .CustomWidgets import FlatButton, HorizontalLine, VerticalSpacerItem


class EosDatabaseWidget(QtWidgets.QWidget):
    """Panel for browsing the EoS materials database and loading phases."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_widgets()
        self._create_layout()
        self._style_widgets()

    def _create_widgets(self):
        # --- Connection row ---
        self.api_url_input = QtWidgets.QLineEdit("http://localhost:8000")
        self.api_url_input.setPlaceholderText("API base URL")
        self.connect_btn = FlatButton("Connect")

        self.status_lbl = QtWidgets.QLabel("Not connected")
        self.status_lbl.setAlignment(QtCore.Qt.AlignCenter)

        # --- Search row ---
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Search by name or formula (e.g. Au, MgO)...")
        self.search_btn = FlatButton("Search")
        self.load_all_btn = FlatButton("Load All")

        # --- Materials table ---
        self.materials_table = QtWidgets.QTableWidget()
        self.materials_table.setColumnCount(6)
        self.materials_table.setHorizontalHeaderLabels(
            ["Name", "Chemistry", "Space Group", "α (°)", "β (°)", "γ (°)"]
        )
        self.materials_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.materials_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.materials_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.materials_table.verticalHeader().setVisible(False)
        self.materials_table.horizontalHeader().setStretchLastSection(True)

        # --- EOS table ---
        self.eos_table = QtWidgets.QTableWidget()
        self.eos_table.setColumnCount(5)
        self.eos_table.setHorizontalHeaderLabels(["Type", "Reference", "K0 (GPa)", "K0'", "V0 (Å³)"])
        self.eos_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.eos_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.eos_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.eos_table.verticalHeader().setVisible(False)
        self.eos_table.horizontalHeader().setStretchLastSection(True)

        # --- Detail label ---
        self.detail_lbl = QtWidgets.QLabel("")
        self.detail_lbl.setWordWrap(True)

        # --- Action buttons ---
        self.load_phase_btn = FlatButton("Load as Phase")
        self.load_phase_btn.setEnabled(False)
        self.load_phase_btn.setToolTip("Load selected material into the Phase list")
        self.clear_btn = FlatButton("Clear")

    def _create_layout(self):
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)
        self.setLayout(main_layout)

        # Connection row
        conn_layout = QtWidgets.QHBoxLayout()
        conn_layout.addWidget(QtWidgets.QLabel("API URL:"))
        conn_layout.addWidget(self.api_url_input)
        conn_layout.addWidget(self.connect_btn)
        main_layout.addLayout(conn_layout)

        main_layout.addWidget(self.status_lbl)
        main_layout.addWidget(HorizontalLine())

        # Search row
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)
        search_layout.addWidget(self.load_all_btn)
        main_layout.addLayout(search_layout)

        # Materials table
        main_layout.addWidget(QtWidgets.QLabel("Materials:"))
        main_layout.addWidget(self.materials_table, 3)

        # EOS table
        main_layout.addWidget(QtWidgets.QLabel("Equation of State Parameters:"))
        main_layout.addWidget(self.eos_table, 2)

        # Detail label
        main_layout.addWidget(self.detail_lbl)

        main_layout.addWidget(HorizontalLine())

        # Action buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.load_phase_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addSpacerItem(
            QtWidgets.QSpacerItem(
                0, 0,
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Minimum
            )
        )
        main_layout.addLayout(btn_layout)

    def _style_widgets(self):
        self.materials_table.setMinimumHeight(160)
        self.eos_table.setMinimumHeight(100)
        self.status_lbl.setStyleSheet("color: gray; font-style: italic;")
