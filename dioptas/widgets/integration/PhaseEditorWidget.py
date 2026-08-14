# SPDX-License-Identifier: MIT

from qtpy import QtWidgets, QtCore, QtGui
import numpy as np

from ...widgets.CustomWidgets import NumberTextField, LabelAlignRight, DoubleSpinBoxAlignRight, HorizontalSpacerItem, \
    VerticalSpacerItem

from ...model.util.HelperModule import convert_d_to_two_theta


class PhaseEditorWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle('Dioptas - Phase Editor')

        self._layout = QtWidgets.QVBoxLayout()

        self._file_layout = QtWidgets.QGridLayout()
        self._file_layout.addWidget(LabelAlignRight('Filename:'), 0, 0)

        self.filename_txt = QtWidgets.QLineEdit('')
        self.filename_txt.setReadOnly(True)
        # Retained off-layout for legacy controller/API compatibility. The
        # editor no longer exposes comments because EoS provenance is shown by
        # the material-record selector and its metadata dialog.
        self.comments_txt = QtWidgets.QLineEdit(self)
        self.comments_txt.hide()
        self._file_layout.addWidget(self.filename_txt, 0, 1)
        self._layout.addLayout((self._file_layout))

        self.lattice_parameters_gb = QtWidgets.QGroupBox('Lattice Parameters')
        self._lattice_parameters_layout = QtWidgets.QVBoxLayout()

        self._symmetry_layout = QtWidgets.QHBoxLayout()
        self._symmetry_layout.addWidget(LabelAlignRight('Symmetry'))
        self.symmetry_cb = QtWidgets.QComboBox()
        self.symmetries = ['cubic', 'tetragonal', 'hexagonal', 'trigonal', 'rhombohedral',
                           'orthorhombic', 'monoclinic', 'triclinic']
        self.symmetry_cb.addItems(self.symmetries)
        self._symmetry_layout.addWidget(self.symmetry_cb)
        self._symmetry_layout.addSpacerItem(HorizontalSpacerItem())
        self._lattice_parameters_layout.addLayout(self._symmetry_layout)

        self._parameters_layout = QtWidgets.QGridLayout()

        self.lattice_a_sb = DoubleSpinBoxAlignRight()
        self.lattice_a_sb.setSingleStep(0.01)
        self.lattice_a_sb.setMinimum(0)
        self.lattice_a_sb.setMaximum(99999)
        self.lattice_a_sb.setDecimals(4)
        self.lattice_b_sb = DoubleSpinBoxAlignRight()
        self.lattice_b_sb.setMinimum(0)
        self.lattice_b_sb.setMaximum(99999)
        self.lattice_b_sb.setDecimals(4)
        self.lattice_b_sb.setSingleStep(0.01)
        self.lattice_c_sb = DoubleSpinBoxAlignRight()
        self.lattice_c_sb.setMinimum(0)
        self.lattice_c_sb.setMaximum(99999)
        self.lattice_c_sb.setDecimals(4)
        self.lattice_c_sb.setSingleStep(0.01)
        self.lattice_length_step_txt = NumberTextField('0.01')

        self.add_field(self._parameters_layout, self.lattice_a_sb, 'a0:', u"Å", 0, 0)
        self.add_field(self._parameters_layout, self.lattice_b_sb, 'b0:', u"Å", 0, 3)
        self.add_field(self._parameters_layout, self.lattice_c_sb, 'c0:', u"Å", 0, 6)
        self.add_field(self._parameters_layout, self.lattice_length_step_txt, 'st:', u"Å", 0, 9)

        self.lattice_eos_a_txt = NumberTextField()
        self.lattice_eos_b_txt = NumberTextField()
        self.lattice_eos_c_txt = NumberTextField()

        self.add_field(self._parameters_layout, self.lattice_eos_a_txt, 'a:', u"Å", 1, 0)
        self.add_field(self._parameters_layout, self.lattice_eos_b_txt, 'b:', u"Å", 1, 3)
        self.add_field(self._parameters_layout, self.lattice_eos_c_txt, 'c:', u"Å", 1, 6)

        self.lattice_alpha_sb = DoubleSpinBoxAlignRight()
        self.lattice_alpha_sb.setMaximum(180)
        self.lattice_beta_sb = DoubleSpinBoxAlignRight()
        self.lattice_beta_sb.setMaximum(180)
        self.lattice_gamma_sb = DoubleSpinBoxAlignRight()
        self.lattice_gamma_sb.setMaximum(180)
        self.lattice_angle_step_txt = NumberTextField('1')

        self.add_field(self._parameters_layout, self.lattice_alpha_sb, u'α:', u"°", 2, 0)
        self.add_field(self._parameters_layout, self.lattice_beta_sb, u'β:', u"°", 2, 3)
        self.add_field(self._parameters_layout, self.lattice_gamma_sb, u'γ:', u"°", 2, 6)
        self.add_field(self._parameters_layout, self.lattice_angle_step_txt, u'st:', u"°", 2, 9)

        self.lattice_volume_txt = NumberTextField()
        self.lattice_eos_volume_txt = NumberTextField()

        self.add_field(self._parameters_layout, self.lattice_volume_txt, 'V0:', u'Å³', 3, 3)
        self.add_field(self._parameters_layout, self.lattice_eos_volume_txt, 'V:', u'Å³', 3, 6)

        self.lattice_ab_sb = DoubleSpinBoxAlignRight()
        self.lattice_ab_sb.setDecimals(4)
        self.lattice_ca_sb = DoubleSpinBoxAlignRight()
        self.lattice_ca_sb.setDecimals(4)
        self.lattice_cb_sb = DoubleSpinBoxAlignRight()
        self.lattice_cb_sb.setDecimals(4)
        self.lattice_ratio_step_txt = NumberTextField('0.01')

        self.add_field(self._parameters_layout, self.lattice_ab_sb, 'a/b:', None, 4, 0)
        self.add_field(self._parameters_layout, self.lattice_ca_sb, 'c/a:', None, 4, 3)
        self.add_field(self._parameters_layout, self.lattice_cb_sb, 'c/b:', None, 4, 6)
        self.add_field(self._parameters_layout, self.lattice_ratio_step_txt, 'st:', None, 4, 9)

        self._lattice_parameters_layout.addLayout(self._parameters_layout)
        self.lattice_parameters_gb.setLayout(self._lattice_parameters_layout)

        self.eos_gb = QtWidgets.QGroupBox('Equation of State')
        self.eos_record_cb = QtWidgets.QComboBox()
        self.eos_record_status_lbl = QtWidgets.QLabel()
        self.eos_record_status_lbl.setWordWrap(True)
        self.eos_record_add_btn = QtWidgets.QPushButton('Add…')
        self.eos_record_duplicate_btn = QtWidgets.QPushButton('Duplicate…')
        self.eos_record_edit_btn = QtWidgets.QPushButton('Edit…')
        self.eos_record_delete_btn = QtWidgets.QPushButton('Delete')
        self.eos_record_default_btn = QtWidgets.QPushButton('Set Default')
        self._eos_record_widget = QtWidgets.QWidget()
        record_layout = QtWidgets.QGridLayout(self._eos_record_widget)
        record_layout.setContentsMargins(4, 4, 4, 2)
        record_layout.setHorizontalSpacing(6)
        record_layout.setVerticalSpacing(4)
        record_layout.addWidget(QtWidgets.QLabel('Material record:'), 0, 0)
        record_layout.addWidget(self.eos_record_cb, 0, 1)
        record_layout.addWidget(self.eos_record_status_lbl, 1, 0, 1, 2)

        # Keep actions grouped at their natural widths. Putting each button
        # in a separate grid column made the row expand across the panel.
        self._eos_record_button_layout = QtWidgets.QHBoxLayout()
        self._eos_record_button_layout.setContentsMargins(0, 0, 0, 0)
        self._eos_record_button_layout.setSpacing(4)
        for button in (
                self.eos_record_add_btn, self.eos_record_duplicate_btn,
                self.eos_record_edit_btn, self.eos_record_delete_btn,
                self.eos_record_default_btn):
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
            self._eos_record_button_layout.addWidget(button)
        self._eos_record_button_layout.addStretch()
        record_layout.addLayout(self._eos_record_button_layout, 2, 0, 1, 2)
        record_layout.setColumnStretch(1, 1)
        # Thermal equations can have substantially more parameters than a
        # room-temperature EoS. Keep that column usable without letting the
        # complete editor grow beyond the screen.
        self.eos_scroll_area = QtWidgets.QScrollArea()
        self.eos_scroll_area.setWidgetResizable(True)
        self.eos_scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        self.eos_scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._eos_contents = QtWidgets.QWidget()
        self._eos_layout = QtWidgets.QGridLayout(self._eos_contents)
        self._eos_layout.setContentsMargins(4, 2, 4, 4)
        self._eos_layout.setHorizontalSpacing(6)
        self._eos_layout.setVerticalSpacing(4)
        self._eos_layout.setAlignment(QtCore.Qt.AlignTop)

        # the equation itself is selectable; the parameter rows below are
        # shown or hidden per equation (see set_eos_parameter_names). The
        # combobox entries are configured by the controller
        # (configure_eos_types) from what Peritheos supports.
        self.eos_type_cb = QtWidgets.QComboBox()
        self.eos_type_lbl = LabelAlignRight('EoS:')
        self._eos_layout.addWidget(self.eos_type_lbl, 0, 0)
        self._eos_layout.addWidget(self.eos_type_cb, 0, 1, 1, 2)

        self.eos_K_txt = NumberTextField()
        self.eos_Kp_txt = NumberTextField()
        self.eos_Kpp_txt = NumberTextField()
        self.eos_n_txt = NumberTextField()
        self.eos_z_txt = NumberTextField()
        self.eos_zc_txt = NumberTextField()
        self.eos_alphaT_txt = NumberTextField()
        self.eos_dalphadT_txt = NumberTextField()
        self.eos_dKdT_txt = NumberTextField()
        self.eos_dKpdT_txt = NumberTextField()

        # per-equation parameter rows, keyed by the peritheos constructor
        # parameter name (plus the Holzapfel material data n/Z/Zc)
        self._eos_param_rows = {}
        self._add_eos_param_row('K0', self.eos_K_txt, 'K:', 'GPa', 1)
        self._add_eos_param_row('K0_prime', self.eos_Kp_txt, "K':", None, 2)
        self._add_eos_param_row('K0_double_prime', self.eos_Kpp_txt,
                                "K'':", '1/GPa', 3)
        self._add_eos_param_row('n', self.eos_n_txt, 'n:', 'atoms/formula', 4)
        self._add_eos_param_row('Z', self.eos_z_txt, 'Z:', 'e per formula', 5)
        self._add_eos_param_row('Zc', self.eos_zc_txt, 'Z<sub>cell</sub>:',
                                'formula/cell', 6)

        # thermal model on top of the equation above: the classic
        # constant-coefficient correction, or a peritheos thermal engine
        self.thermal_type_cb = QtWidgets.QComboBox()
        self.thermal_type_cb.addItem('None', 'none')
        self.thermal_type_cb.addItem('Constant α, dK/dT', 'alphakt')
        self.thermal_type_cb.addItem('Mie-Grüneisen-Debye', 'MieGruneisenDebye')
        self.thermal_type_cb.addItem('Mie-Grüneisen-Einstein', 'MieGruneisenEinstein')
        self.thermal_type_cb.addItem('Sokolova et al. (2016)', 'Sokolova2016')
        self.thermal_type_lbl = LabelAlignRight('Thermal:')
        self._eos_layout.addWidget(self.thermal_type_lbl, 7, 0)
        self._eos_layout.addWidget(self.thermal_type_cb, 7, 1, 1, 2)

        self.eos_theta_txt = NumberTextField()
        self.eos_gamma_txt = NumberTextField()
        self.eos_qt_txt = NumberTextField()
        self.eos_tref_txt = NumberTextField()

        self._thermal_param_rows = {}
        self._add_thermal_param_row('alpha_t0', self.eos_alphaT_txt, u'α<sub>T</sub>:', '1/K', 8)
        self._add_thermal_param_row('d_alpha_dt', self.eos_dalphadT_txt, u'dα<sub>T</sub>/dT:', u'1/K²', 9)
        self._add_thermal_param_row('dk0dt', self.eos_dKdT_txt, 'dK/dT:', 'GPa/K', 10)
        self._add_thermal_param_row('dk0pdt', self.eos_dKpdT_txt, "dK'/dT", '1/K', 11)
        self._add_thermal_param_row('theta_t0', self.eos_theta_txt, u'θ<sub>0</sub>:', 'K', 12)
        self._add_thermal_param_row('gamma_t0', self.eos_gamma_txt, u'γ<sub>0</sub>:', None, 13)
        self._add_thermal_param_row('q_t0', self.eos_qt_txt, 'q:', None, 14)
        self._add_thermal_param_row('t_ref', self.eos_tref_txt, u'T<sub>ref</sub>:', 'K', 15)

        # Native Sokolova coefficients. These live in the phase's
        # thermal_parameters dictionary rather than in legacy scalar state.
        self.sokolova_parameter_fields = {}
        sokolova_rows = (
            ('QE1o', u'Θ<sub>E1,0</sub>:', 'K'),
            ('mE1', u'm<sub>E1</sub>:', None),
            ('QE2o', u'Θ<sub>E2,0</sub>:', 'K'),
            ('mE2', u'm<sub>E2</sub>:', None),
            ('delta', u'δ:', None),
            ('t', 't:', None),
            ('a_0', u'a<sub>0</sub>:', u'10⁻⁶/K'),
            ('m', 'm:', None),
            ('g', 'g:', None),
            ('e_0', u'e<sub>0</sub>:', u'10⁻⁶/K'),
        )
        for row, (parameter, label, unit) in enumerate(
                sokolova_rows, start=16):
            field = NumberTextField()
            self.sokolova_parameter_fields[parameter] = field
            self._add_thermal_param_row(
                'sokolova_' + parameter, field, label, unit, row)

        self.eos_scroll_area.setWidget(self._eos_contents)
        self._eos_group_layout = QtWidgets.QVBoxLayout()
        self._eos_group_layout.setContentsMargins(0, 0, 0, 0)
        self._eos_group_layout.addWidget(self._eos_record_widget)
        self._eos_group_layout.addWidget(self.eos_scroll_area)
        self.eos_gb.setLayout(self._eos_group_layout)

        self.reflections_gb = QtWidgets.QGroupBox('Reflections')
        self._reflection_layout = QtWidgets.QGridLayout()
        self.reflection_table_view = QtWidgets.QTableView()
        self.reflection_table_model = ReflectionTableModel()
        self.reflection_table_view.setModel(self.reflection_table_model)
        # self.reflection_table.setColumnCount(10)
        self.reflections_add_btn = QtWidgets.QPushButton('Add')
        self.reflections_delete_btn = QtWidgets.QPushButton('Delete')
        self.reflections_clear_btn = QtWidgets.QPushButton('Clear')

        self._reflection_layout.addWidget(self.reflection_table_view, 0, 0, 1, 3)
        self._reflection_layout.addWidget(self.reflections_add_btn, 1, 0)
        self._reflection_layout.addWidget(self.reflections_delete_btn, 1, 1)
        self._reflection_layout.addWidget(self.reflections_clear_btn, 1, 2)

        self.reflections_gb.setLayout(self._reflection_layout)

        self._body_layout = QtWidgets.QGridLayout()
        self._body_layout.addWidget(self.eos_gb, 0, 0)
        self._body_layout.addItem(VerticalSpacerItem(), 1, 0)
        self._body_layout.addWidget(self.reflections_gb, 0, 1, 2, 1)

        self._button_layout = QtWidgets.QHBoxLayout()
        self.save_as_btn = QtWidgets.QPushButton('Save As…')
        self.reload_file_btn = QtWidgets.QPushButton('Reload File')

        self._button_layout.addWidget(self.save_as_btn)
        self._button_layout.addWidget(self.reload_file_btn)
        self._button_layout.addSpacerItem(HorizontalSpacerItem())

        self._layout.addWidget(self.lattice_parameters_gb)
        self._layout.addLayout(self._body_layout)
        self._layout.addLayout(self._button_layout)
        self.setLayout(self._layout)

        self.style_widgets()

    def style_widgets(self):
        self.lattice_angle_step_txt.setMaximumWidth(60)
        self.lattice_length_step_txt.setMaximumWidth(60)
        self.lattice_ratio_step_txt.setMaximumWidth(60)

        self.reflection_table_view.setShowGrid(False)
        self.reflection_table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.reflection_table_view.setItemDelegate(TextDoubleDelegate())
        self.reflection_table_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

        # wide enough for the EoS/thermal display names ("Birch-Murnaghan
        # (3rd order)", "Constant α, dK/dT") and the unit labels
        self.eos_gb.setMinimumWidth(380)
        self.eos_gb.setMaximumWidth(430)
        self.eos_gb.setMinimumHeight(240)
        self.eos_gb.setMaximumHeight(480)
        self.eos_gb.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        self.eos_gb.setStyleSheet("""
            QLineEdit {
                max-width: 80;
            }
        """)

        self.reflection_table_view.verticalHeader().setDefaultSectionSize(20)
        self.reflection_table_view.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)

        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()

    def add_field(self, layout, widget, label_str, unit, x, y):
        layout.addWidget(LabelAlignRight(label_str), x, y)
        layout.addWidget(widget, x, y + 1)
        if unit:
            layout.addWidget(QtWidgets.QLabel(unit), x, y + 2)

    #: which parameter rows each thermal model shows
    THERMAL_PARAM_SETS = {
        'none': (),
        'alphakt': ('alpha_t0', 'd_alpha_dt', 'dk0dt', 'dk0pdt'),
        'MieGruneisenDebye': ('theta_t0', 'gamma_t0', 'q_t0', 't_ref'),
        'MieGruneisenEinstein': ('theta_t0', 'gamma_t0', 'q_t0', 't_ref'),
        'Sokolova2016': (
            't_ref', 'sokolova_QE1o', 'sokolova_mE1',
            'sokolova_QE2o', 'sokolova_mE2', 'sokolova_delta',
            'sokolova_t', 'sokolova_a_0', 'sokolova_m',
            'sokolova_g', 'sokolova_e_0',
        ),
    }
    #: peritheos thermal models additionally need the material data for
    #: the molar conversion — union'd into the EoS parameter rows
    THERMAL_MATERIAL_KEYS = {
        'MieGruneisenDebye': ('n', 'Zc'),
        'MieGruneisenEinstein': ('n', 'Zc'),
        'Sokolova2016': ('n', 'Z', 'Zc'),
    }

    def _add_thermal_param_row(self, key, widget, label_str, unit, row):
        """One thermal parameter row, shown per selected thermal model
        (see update_thermal_parameter_visibility)."""
        label = LabelAlignRight(label_str)
        self._eos_layout.addWidget(label, row, 0)
        self._eos_layout.addWidget(widget, row, 1)
        row_widgets = [label, widget]
        if unit:
            unit_label = QtWidgets.QLabel(unit)
            self._eos_layout.addWidget(unit_label, row, 2)
            row_widgets.append(unit_label)
        self._thermal_param_rows[key] = row_widgets

    def set_thermal_type(self, key):
        """Select the thermal model without emitting: 'none', 'alphakt',
        or a peritheos thermal class name."""
        index = self.thermal_type_cb.findData(key)
        self.thermal_type_cb.blockSignals(True)
        self.thermal_type_cb.setCurrentIndex(max(0, index))
        self.thermal_type_cb.blockSignals(False)
        self.update_thermal_parameter_visibility()
        self.update_eos_parameter_visibility()

    def get_thermal_type(self):
        return self.thermal_type_cb.currentData()

    def update_thermal_parameter_visibility(self):
        """Show only the parameter rows of the selected thermal model."""
        names = self.THERMAL_PARAM_SETS.get(self.get_thermal_type(), ())
        for key, row_widgets in self._thermal_param_rows.items():
            visible = key in names
            for widget in row_widgets:
                widget.setVisible(visible)
        self._compact_eos_layout()

    def _add_eos_param_row(self, key, widget, label_str, unit, row):
        """One EoS parameter row whose visibility follows the selected
        equation (see set_eos_parameter_names)."""
        label = LabelAlignRight(label_str)
        self._eos_layout.addWidget(label, row, 0)
        self._eos_layout.addWidget(widget, row, 1)
        row_widgets = [label, widget]
        if unit:
            unit_label = QtWidgets.QLabel(unit)
            self._eos_layout.addWidget(unit_label, row, 2)
            row_widgets.append(unit_label)
        self._eos_param_rows[key] = row_widgets

    def configure_eos_types(self, eos_types):
        """
        Fill the EoS combobox. *eos_types*: list of (key, display_name,
        parameter_names) — key is the peritheos class name, and
        parameter_names decides which rows show when it is selected.
        """
        self._eos_parameter_names = {key: list(names)
                                     for key, _, names in eos_types}
        self.eos_type_cb.blockSignals(True)
        self.eos_type_cb.clear()
        for key, display_name, _ in eos_types:
            self.eos_type_cb.addItem(display_name, key)
        self.eos_type_cb.blockSignals(False)

    def set_eos_type(self, key):
        """Select the equation with the given key, without emitting."""
        index = self.eos_type_cb.findData(key)
        self.eos_type_cb.blockSignals(True)
        self.eos_type_cb.setCurrentIndex(max(0, index))
        self.eos_type_cb.blockSignals(False)
        self.update_eos_parameter_visibility()

    def get_eos_type(self):
        """The peritheos class name of the selected equation."""
        return self.eos_type_cb.currentData()

    def update_eos_records(self, labels, current_index=0, *, origins=None,
                           default_index=0, material_origin='legacy',
                           reloadable=None):
        """Refresh the material-record selector without emitting a change."""
        origins = origins or []
        self.eos_record_cb.blockSignals(True)
        self.eos_record_cb.clear()
        if labels:
            for index, label in enumerate(labels):
                prefix = '★ ' if index == default_index else ''
                self.eos_record_cb.addItem(prefix + label)
            self.eos_record_cb.setCurrentIndex(
                max(0, min(current_index, len(labels) - 1)))
            self.eos_record_cb.setEnabled(True)
        else:
            self.eos_record_cb.addItem('No saved EoS record')
            self.eos_record_cb.setEnabled(False)
        self.eos_record_cb.blockSignals(False)

        origin = origins[current_index] if (
            labels and 0 <= current_index < len(origins)) else ''
        if origin == 'bundled':
            status = ('Published database record — read-only. Duplicate it '
                      'to make a custom record.')
        elif labels:
            status = 'User-owned record — parameters and metadata are editable.'
        else:
            status = ('These are unsaved phase parameters. Add a record to '
                      'attach reference and fit provenance.')
        self.eos_record_status_lbl.setText(status)
        editable = origin != 'bundled'
        self.eos_record_duplicate_btn.setEnabled(bool(labels))
        self.eos_record_edit_btn.setEnabled(bool(labels) and editable)
        self.eos_record_delete_btn.setEnabled(bool(labels) and editable)
        self.eos_record_default_btn.setEnabled(bool(labels) and editable
                                               and current_index != default_index)
        self.set_eos_parameter_editable(editable)
        self.comments_txt.setEnabled(not labels and material_origin != 'bundled')
        self.set_material_editable(material_origin != 'bundled')
        if reloadable is None:
            reloadable = material_origin in ('legacy', 'file', 'cif')
        self.reload_file_btn.setEnabled(reloadable)
        self.reload_file_btn.setToolTip(
            'Discard local changes and reload the source file.' if reloadable
            else 'This material was loaded from the built-in database and '
                 'has no source file to reload.')

    def set_eos_parameter_editable(self, editable):
        """Lock the calculation fields when a bundled record is active."""
        widgets = [
            self.eos_type_cb, self.thermal_type_cb,
            self.eos_K_txt, self.eos_Kp_txt, self.eos_Kpp_txt,
            self.eos_n_txt, self.eos_z_txt, self.eos_zc_txt,
            self.eos_alphaT_txt, self.eos_dalphadT_txt,
            self.eos_dKdT_txt, self.eos_dKpdT_txt,
            self.eos_theta_txt, self.eos_gamma_txt, self.eos_qt_txt,
            self.eos_tref_txt, *self.sokolova_parameter_fields.values(),
        ]
        for widget in widgets:
            widget.setEnabled(editable)

    def set_material_editable(self, editable):
        """Lock the curated structure and reflection table of DB materials."""
        widgets = [
            self.symmetry_cb,
            self.lattice_a_sb, self.lattice_b_sb, self.lattice_c_sb,
            self.lattice_alpha_sb, self.lattice_beta_sb,
            self.lattice_gamma_sb, self.lattice_ab_sb,
            self.lattice_ca_sb, self.lattice_cb_sb,
            self.reflections_add_btn, self.reflections_delete_btn,
            self.reflections_clear_btn, self.reflection_table_view,
        ]
        if editable:
            self.symmetry_cb.setEnabled(True)
            self.update_spinbox_enable(self.symmetry_cb.currentText().upper())
            for widget in (
                    self.reflections_add_btn, self.reflections_delete_btn,
                    self.reflections_clear_btn, self.reflection_table_view):
                widget.setEnabled(True)
        else:
            for widget in widgets:
                widget.setEnabled(False)

    def update_eos_parameter_visibility(self):
        """Show the parameter rows of the selected equation, plus the
        material data a selected peritheos thermal model needs."""
        names = set(getattr(self, '_eos_parameter_names', {}).get(
            self.get_eos_type(), ['K0', 'K0_prime']))
        names |= set(self.THERMAL_MATERIAL_KEYS.get(
            self.get_thermal_type(), ()))
        for key, row_widgets in self._eos_param_rows.items():
            visible = key in names
            for widget in row_widgets:
                widget.setVisible(visible)
        self._compact_eos_layout()

    def _compact_eos_layout(self):
        """Pack visible EoS and thermal controls into consecutive rows."""
        for grid_row in range(self._eos_layout.rowCount()):
            self._eos_layout.setRowStretch(grid_row, 0)

        grid_row = 0
        self._eos_layout.addWidget(self.eos_type_lbl, grid_row, 0)
        self._eos_layout.addWidget(self.eos_type_cb, grid_row, 1, 1, 2)
        grid_row += 1

        for row_widgets in self._eos_param_rows.values():
            if row_widgets[0].isHidden():
                continue
            for column, widget in enumerate(row_widgets):
                self._eos_layout.addWidget(widget, grid_row, column)
            grid_row += 1

        self._eos_layout.addWidget(self.thermal_type_lbl, grid_row, 0)
        self._eos_layout.addWidget(self.thermal_type_cb, grid_row, 1, 1, 2)
        grid_row += 1

        for row_widgets in self._thermal_param_rows.values():
            if row_widgets[0].isHidden():
                continue
            for column, widget in enumerate(row_widgets):
                self._eos_layout.addWidget(widget, grid_row, column)
            grid_row += 1

        # Any extra height belongs below the form, never between fields.
        self._eos_layout.setRowStretch(grid_row, 1)

    def show_jcpds(self, jcpds_phase, wavelength=None):
        self.update_name(jcpds_phase)
        self.update_lattice_parameters(jcpds_phase)
        self.update_eos_parameters(jcpds_phase)
        self.reflection_table_model.update_reflection_data(jcpds_phase.reflections,
                                                           wavelength)

    def update_eos_parameters(self, jcpds_phase):
        self.set_eos_type(str(jcpds_phase.params.get('eos_type') or 'BM3'))
        self.eos_K_txt.setText(str(jcpds_phase.params['k0']))
        self.eos_Kp_txt.setText(str(jcpds_phase.params['k0p']))
        self.eos_Kpp_txt.setText(str(jcpds_phase.params.get('k0pp0') or 0.0))
        for field, key in ((self.eos_n_txt, 'n'), (self.eos_z_txt, 'z'),
                           (self.eos_zc_txt, 'zc')):
            value = jcpds_phase.params.get(key)
            field.setText('' if value is None else str(value))
        self.eos_alphaT_txt.setText(str(jcpds_phase.params['alpha_t0']))
        self.eos_dalphadT_txt.setText(str(jcpds_phase.params['d_alpha_dt']))
        self.eos_dKdT_txt.setText(str(jcpds_phase.params['dk0dt']))
        self.eos_dKpdT_txt.setText(str(jcpds_phase.params['dk0pdt']))
        thermal_parameters = jcpds_phase.params.get(
            'thermal_parameters') or {}
        self.eos_theta_txt.setText(str(thermal_parameters.get(
            'theta0', jcpds_phase.params['theta_t0'])))
        self.eos_gamma_txt.setText(str(thermal_parameters.get(
            'gamma0', jcpds_phase.params['gamma_t0'])))
        self.eos_qt_txt.setText(str(thermal_parameters.get(
            'q', jcpds_phase.params['q_t0'])))
        self.eos_tref_txt.setText(str(thermal_parameters.get(
            'Tr', jcpds_phase.params['t_ref'])))
        for parameter, field in self.sokolova_parameter_fields.items():
            value = thermal_parameters.get(parameter)
            field.setText('' if value is None else str(value))
        thermal_type = str(jcpds_phase.params.get('thermal_type') or '')
        if thermal_type:
            self.set_thermal_type(thermal_type)
        else:
            has_thermal = any(jcpds_phase.params[key] for key in
                              ('alpha_t0', 'd_alpha_dt', 'dk0dt', 'dk0pdt'))
            self.set_thermal_type('alphakt' if has_thermal else 'none')

    def update_name(self, jcpds_phase):
        self.filename_txt.setText(jcpds_phase.filename)
        self.comments_txt.setText("/n".join(jcpds_phase.params['comments']))

    def update_lattice_parameters(self, jcpds_phase):
        self.blockAllSignals(True)
        self.symmetry_cb.setCurrentIndex(self.symmetries.index(jcpds_phase.params['symmetry'].lower()))
        self.update_spinbox_enable(jcpds_phase.params['symmetry'])

        if not self.lattice_a_sb.hasFocus():
            self.lattice_a_sb.setValue(jcpds_phase.params['a0'])
        if not self.lattice_b_sb.hasFocus():
            self.lattice_b_sb.setValue(jcpds_phase.params['b0'])
        if not self.lattice_c_sb.hasFocus():
            self.lattice_c_sb.setValue(jcpds_phase.params['c0'])

        self.lattice_eos_a_txt.setText('{0:.4f}'.format(jcpds_phase.params['a']))
        self.lattice_eos_b_txt.setText('{0:.4f}'.format(jcpds_phase.params['b']))
        self.lattice_eos_c_txt.setText('{0:.4f}'.format(jcpds_phase.params['c']))

        self.lattice_eos_volume_txt.setText('{0:.4f}'.format(jcpds_phase.params['v']))

        try:
            if not self.lattice_ab_sb.hasFocus():
                self.lattice_ab_sb.setValue(jcpds_phase.params['a0'] / float(jcpds_phase.params['b0']))
        except ZeroDivisionError:
            self.lattice_ab_sb.setSpecialValueText('Inf')

        try:
            if not self.lattice_ca_sb.hasFocus():
                self.lattice_ca_sb.setValue(jcpds_phase.params['c0'] / float(jcpds_phase.params['a0']))
        except ZeroDivisionError:
            self.lattice_ca_sb.setSpecialValueText('Inf')

        try:
            if not self.lattice_cb_sb.hasFocus():
                self.lattice_cb_sb.setValue(jcpds_phase.params['c0'] / float(jcpds_phase.params['b0']))
        except ZeroDivisionError:
            self.lattice_cb_sb.setSpecialValueText('Inf')

        self.lattice_volume_txt.setText(str('{0:g}'.format(jcpds_phase.params['v0'])))

        if not self.lattice_alpha_sb.hasFocus():
            self.lattice_alpha_sb.setValue(jcpds_phase.params['alpha0'])
        if not self.lattice_beta_sb.hasFocus():
            self.lattice_beta_sb.setValue(jcpds_phase.params['beta0'])
        if not self.lattice_gamma_sb.hasFocus():
            self.lattice_gamma_sb.setValue(jcpds_phase.params['gamma0'])

        self.blockAllSignals(False)

    def blockAllSignals(self, bool=True):
        self.lattice_a_sb.blockSignals(bool)
        self.lattice_b_sb.blockSignals(bool)
        self.lattice_c_sb.blockSignals(bool)

        self.lattice_alpha_sb.blockSignals(bool)
        self.lattice_beta_sb.blockSignals(bool)
        self.lattice_gamma_sb.blockSignals(bool)

        self.lattice_ab_sb.blockSignals(bool)
        self.lattice_ca_sb.blockSignals(bool)
        self.lattice_cb_sb.blockSignals(bool)

        self.symmetry_cb.blockSignals(bool)

    def update_spinbox_enable(self, symmetry):
        if symmetry == 'CUBIC':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(False)
            self.lattice_c_sb.setEnabled(False)

            self.lattice_alpha_sb.setEnabled(False)
            self.lattice_beta_sb.setEnabled(False)
            self.lattice_gamma_sb.setEnabled(False)

            self.lattice_ab_sb.setEnabled(False)
            self.lattice_ca_sb.setEnabled(False)
            self.lattice_cb_sb.setEnabled(False)

        elif symmetry == 'TETRAGONAL':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(False)
            self.lattice_c_sb.setEnabled(True)

            self.lattice_alpha_sb.setEnabled(False)
            self.lattice_beta_sb.setEnabled(False)
            self.lattice_gamma_sb.setEnabled(False)

            self.lattice_ab_sb.setEnabled(False)
            self.lattice_ca_sb.setEnabled(True)
            self.lattice_cb_sb.setEnabled(False)

        elif symmetry == 'ORTHORHOMBIC':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(True)
            self.lattice_c_sb.setEnabled(True)

            self.lattice_alpha_sb.setEnabled(False)
            self.lattice_beta_sb.setEnabled(False)
            self.lattice_gamma_sb.setEnabled(False)

            self.lattice_ab_sb.setEnabled(True)
            self.lattice_ca_sb.setEnabled(True)
            self.lattice_cb_sb.setEnabled(True)

        elif symmetry == 'HEXAGONAL' or symmetry == 'TRIGONAL':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(False)
            self.lattice_c_sb.setEnabled(True)

            self.lattice_alpha_sb.setEnabled(False)
            self.lattice_beta_sb.setEnabled(False)
            self.lattice_gamma_sb.setEnabled(False)

            self.lattice_ab_sb.setEnabled(False)
            self.lattice_ca_sb.setEnabled(True)
            self.lattice_cb_sb.setEnabled(False)

        elif symmetry == 'RHOMBOHEDRAL':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(False)
            self.lattice_c_sb.setEnabled(False)

            self.lattice_alpha_sb.setEnabled(True)
            self.lattice_beta_sb.setEnabled(False)
            self.lattice_gamma_sb.setEnabled(False)

            self.lattice_ab_sb.setEnabled(False)
            self.lattice_ca_sb.setEnabled(False)
            self.lattice_cb_sb.setEnabled(False)

        elif symmetry == 'MONOCLINIC':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(True)
            self.lattice_c_sb.setEnabled(True)

            self.lattice_alpha_sb.setEnabled(False)
            self.lattice_beta_sb.setEnabled(True)
            self.lattice_gamma_sb.setEnabled(False)

            self.lattice_ab_sb.setEnabled(True)
            self.lattice_ca_sb.setEnabled(True)
            self.lattice_cb_sb.setEnabled(True)

        elif symmetry == 'TRICLINIC':
            self.lattice_a_sb.setEnabled(True)
            self.lattice_b_sb.setEnabled(True)
            self.lattice_c_sb.setEnabled(True)

            self.lattice_alpha_sb.setEnabled(True)
            self.lattice_beta_sb.setEnabled(True)
            self.lattice_gamma_sb.setEnabled(True)

            self.lattice_ab_sb.setEnabled(True)
            self.lattice_ca_sb.setEnabled(True)
            self.lattice_cb_sb.setEnabled(True)

        else:
            print('Unknown symmetry: {0}.'.format(symmetry))

    def get_selected_reflections(self):
        selected = self.reflection_table_view.selectionModel().selectedRows()
        try:
            row = []
            for element in selected:
                row.append(int(element.row()))
        except IndexError:
            row = None
        return row


class NoRectDelegate(QtWidgets.QItemDelegate):
    def drawFocus(self, painter, option, rect):
        option.state &= ~QtWidgets.QStyle.State_HasFocus
        QtWidgets.QItemDelegate.drawFocus(self, painter, option, rect)


class TextDoubleDelegate(NoRectDelegate):
    def createEditor(self, parent, _, model):
        self.editor = QtWidgets.QLineEdit(parent)
        self.editor.setFrame(False)
        self.editor.setValidator(QtGui.QDoubleValidator())
        self.editor.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        return self.editor


class ReflectionTableModel(QtCore.QAbstractTableModel):
    reflection_edited = QtCore.Signal(int, int, str)  # row, column, value

    def __init__(self, reflections=None, wavelength=None):
        super().__init__()
        self.wavelength = wavelength
        if reflections is not None:
            self.reflections = reflections
            self.update_reflection_data(reflections)
        else:
            self.reflections = []
        self.header_labels = ['h', 'k', 'l', 'Intensity', 'd0', 'd', u"2θ_0", u"2θ", 'Q0', 'Q']

    def rowCount(self, *_):
        return len(self.reflections)

    def columnCount(self, *_):
        return 10

    def data(self, index, role=QtCore.Qt.DisplayRole):
        col = index.column()
        if role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignCenter
        if role == QtCore.Qt.DisplayRole:
            if col < 4:
                format_str = '{0:g}'
            else:
                format_str = '{0:.4f}'
            return format_str.format(self.reflection_data[index.row(), index.column()])
        else:
            return QtCore.QVariant()

    def setData(self, index, value, role):
        self.reflection_edited.emit(index.row(), index.column(), value)
        return True

    def update_reflection_data(self, reflections, wavelength=None):
        if wavelength is None:
            wavelength = self.wavelength
        else:
            self.wavelength = wavelength

        cur_row_num = self.rowCount()
        row_diff = len(reflections) - cur_row_num
        if row_diff < 0:
            self.beginRemoveRows(QtCore.QModelIndex(), cur_row_num + row_diff, cur_row_num - 1)
        elif row_diff > 0:
            self.beginInsertRows(QtCore.QModelIndex(), cur_row_num, cur_row_num + row_diff - 1)

        self.reflections = reflections
        self.reflection_data = np.zeros((len(reflections), self.columnCount()))
        for i, refl in enumerate(reflections):
            self.reflection_data[i, 0] = refl.h
            self.reflection_data[i, 1] = refl.k
            self.reflection_data[i, 2] = refl.l
            self.reflection_data[i, 3] = refl.intensity
            self.reflection_data[i, 4] = refl.d0
            self.reflection_data[i, 5] = refl.d

        if wavelength is not None:
            self.reflection_data[:, 6] = convert_d_to_two_theta(self.reflection_data[:, 4], wavelength)  # two_theta0
            self.reflection_data[:, 7] = convert_d_to_two_theta(self.reflection_data[:, 5], wavelength)  # two_theta
            valid_ind = np.where(self.reflection_data[:, 4] > 0)
            self.reflection_data[valid_ind, 8] = 2.0 * np.pi / self.reflection_data[valid_ind, 4]  # q0
            self.reflection_data[valid_ind, 9] = 2.0 * np.pi / self.reflection_data[valid_ind, 5]  # q

        if row_diff < 0:
            self.endRemoveRows()
        elif row_diff > 0:
            self.endInsertRows()

        self.modelReset.emit()

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.header_labels[section]
        if orientation == QtCore.Qt.Vertical and role == QtCore.Qt.DisplayRole:
            return section + 1

    def flags(self, index):
        col = index.column()
        ans = QtCore.QAbstractTableModel.flags(self, index)
        if col <= 3:
            return QtCore.Qt.ItemIsEditable | ans
        else:
            return ans
