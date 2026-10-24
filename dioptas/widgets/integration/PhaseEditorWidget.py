# SPDX-License-Identifier: MIT

from qtpy import QtWidgets, QtCore, QtGui
import numpy as np
import inspect

from ...model.util.eos_phase import (
    THERMAL_EOS_TYPES, THERMAL_CONFIGURATION_CHOICES,
    thermal_parameter_signature, thermal_compatibility_error,
    NON_MOLAR_THERMAL_TYPES, EosPhase,
)

from ...widgets.CustomWidgets import (
    NumberTextField, LabelAlignRight, DoubleSpinBoxAlignRight, HorizontalSpacerItem)

from ...model.util.HelperModule import convert_d_to_two_theta
from ...model.eos.structure_composition import assess_structure_composition
from ..SpaceGroupSelector import SpaceGroupSelector


class PhaseEditorWidget(QtWidgets.QWidget):
    element_edit_requested = QtCore.Signal(int)
    EDITABLE_SITE_FIELDS = frozenset({'element', 'x', 'y', 'z', 'occupancy', 'u_iso_angstrom2'})

    def __init__(self, parent=None):
        super().__init__(parent)
        self._record_layout_timer = QtCore.QTimer(self)
        self._record_layout_timer.setSingleShot(True)
        self._record_layout_timer.timeout.connect(self._fit_record_details)

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

        self.lattice_parameters_gb = QtWidgets.QGroupBox('Lattice && structure')
        self._lattice_parameters_layout = QtWidgets.QVBoxLayout()
        self._lattice_parameters_layout.setSpacing(6)

        self._symmetry_layout = QtWidgets.QHBoxLayout()
        self._symmetry_layout.addWidget(LabelAlignRight('Symmetry'))
        self.symmetry_cb = QtWidgets.QComboBox()
        self.symmetries = ['cubic', 'tetragonal', 'hexagonal', 'trigonal', 'rhombohedral',
                           'orthorhombic', 'monoclinic', 'triclinic']
        self.symmetry_cb.addItems(self.symmetries)
        self._symmetry_layout.addWidget(self.symmetry_cb)
        self._symmetry_layout.addSpacerItem(HorizontalSpacerItem())
        self._lattice_parameters_layout.addLayout(self._symmetry_layout)

        self.space_group_widget = QtWidgets.QWidget()
        space_group_layout = QtWidgets.QHBoxLayout(self.space_group_widget)
        space_group_layout.setContentsMargins(0, 0, 0, 0)
        space_group_layout.addWidget(QtWidgets.QLabel('Space group'))
        self.space_group_cb = SpaceGroupSelector()
        self.space_group_txt = self.space_group_cb.lineEdit()
        self.space_group_cb.setToolTip(
            'Search by symbol or International Tables number. '
            'Reference settings are listed; explicit material settings are retained. '
            'Coordinates stay in the current basis and origin.')
        space_group_layout.addWidget(self.space_group_cb, 1)
        self.space_group_apply_btn = QtWidgets.QPushButton('Apply')
        space_group_layout.addWidget(self.space_group_apply_btn)
        self.space_group_widget.hide()
        self._lattice_parameters_layout.addWidget(self.space_group_widget)

        self._parameters_layout = QtWidgets.QGridLayout()
        self._parameters_layout.setVerticalSpacing(4)

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

        self._lattice_parameters_layout.addLayout(self._parameters_layout)
        steps_layout = QtWidgets.QHBoxLayout()
        steps_layout.addWidget(QtWidgets.QLabel('Steps:'))
        for label, field, unit in (
                ('Length', self.lattice_length_step_txt, 'Å'),
                ('Angle', self.lattice_angle_step_txt, '°'),
                ('Ratio', self.lattice_ratio_step_txt, None)):
            steps_layout.addWidget(QtWidgets.QLabel(label))
            steps_layout.addWidget(field)
            if unit:
                steps_layout.addWidget(QtWidgets.QLabel(unit))
        steps_layout.addStretch()
        self._lattice_parameters_layout.addLayout(steps_layout)
        self.structure_summary_widget = QtWidgets.QWidget()
        structure_layout = QtWidgets.QVBoxLayout(self.structure_summary_widget)
        structure_layout.setContentsMargins(0, 8, 0, 0)
        structure_heading = QtWidgets.QLabel('Atomic positions')
        heading_font = structure_heading.font()
        heading_font.setBold(True)
        structure_heading.setFont(heading_font)
        structure_layout.addWidget(structure_heading)
        self.structure_summary_lbl = QtWidgets.QLabel()
        self.structure_summary_lbl.setWordWrap(True)
        structure_layout.addWidget(self.structure_summary_lbl)
        self.structure_composition_lbl = QtWidgets.QLabel()
        self.structure_composition_lbl.setTextFormat(QtCore.Qt.PlainText)
        self.structure_composition_lbl.setWordWrap(True)
        structure_layout.addWidget(self.structure_composition_lbl)
        self.structure_note_lbl = QtWidgets.QLabel()
        self.structure_note_lbl.setWordWrap(True)
        structure_layout.addWidget(self.structure_note_lbl)
        self.structure_sites_caption = QtWidgets.QLabel('x, y, z: fractional coordinates')
        structure_layout.addWidget(self.structure_sites_caption)
        self.structure_sites_table = QtWidgets.QTableWidget()
        self.structure_sites_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.structure_sites_table.setShowGrid(False)
        self.structure_sites_table.setStyleSheet('QTableWidget { border: none; }')
        self.structure_sites_table.setMinimumHeight(110)
        self.structure_sites_table.cellDoubleClicked.connect(self._request_element_edit)
        self.structure_sites_table.itemSelectionChanged.connect(self._update_site_buttons)
        self.structure_sites_table.installEventFilter(self)
        self.structure_sites_table.horizontalHeader().setStyleSheet(
            'QHeaderView::section { padding: 0 4px; }')
        structure_layout.addWidget(self.structure_sites_table, 1)
        site_buttons = QtWidgets.QHBoxLayout()
        self.structure_site_add_btn = QtWidgets.QPushButton('Add site…')
        self.structure_site_remove_btn = QtWidgets.QPushButton('Remove site')
        site_buttons.addWidget(self.structure_site_add_btn)
        site_buttons.addWidget(self.structure_site_remove_btn)
        site_buttons.addStretch()
        structure_layout.addLayout(site_buttons)
        self.structure_edit_status_lbl = QtWidgets.QLabel()
        self.structure_edit_status_lbl.setWordWrap(True)
        self.structure_edit_status_lbl.hide()
        structure_layout.addWidget(self.structure_edit_status_lbl)
        self.structure_summary_widget.hide()
        self._lattice_parameters_layout.addWidget(self.structure_summary_widget, 1)
        self.lattice_parameters_gb.setLayout(self._lattice_parameters_layout)

        self.eos_gb = QtWidgets.QGroupBox('Equation of State')
        self.eos_record_cb = QtWidgets.QComboBox()
        self.eos_record_cb.setSizeAdjustPolicy(
            QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.eos_record_cb.setMinimumContentsLength(16)
        self.eos_record_cb.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.eos_record_status_lbl = QtWidgets.QLabel()
        self.eos_record_status_lbl.setWordWrap(True)
        self.eos_reproduction_lbl = QtWidgets.QLabel(self)
        self.eos_reproduction_lbl.setWordWrap(True)
        self.eos_reproduction_lbl.setVisible(False)
        self.eos_warning_lbl = QtWidgets.QLabel()
        self.eos_details_btn = QtWidgets.QToolButton()
        self.eos_details_btn.setText('Details…')
        self.eos_details_btn.setToolTip('Full source assessment and qualifications')
        self.eos_details_btn.clicked.connect(self.show_eos_details)
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
        record_layout.addWidget(self.eos_details_btn, 0, 2)
        summary = QtWidgets.QHBoxLayout()
        summary.setContentsMargins(0, 0, 0, 0)
        summary.setSpacing(12)
        summary.addWidget(self.eos_record_status_lbl)
        summary.addWidget(self.eos_warning_lbl)
        summary.addStretch()
        record_layout.addLayout(summary, 1, 0, 1, 3)

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
        record_layout.addLayout(self._eos_record_button_layout, 2, 0, 1, 3)
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
        # Model selectors span the value/unit columns. Extra width belongs
        # after the units, keeping each unit beside its 80 px value field.
        self._eos_layout.setColumnMinimumWidth(0, 120)
        self._eos_layout.setColumnMinimumWidth(1, 80)
        self._eos_layout.setColumnStretch(2, 1)

        # the equation itself is selectable; the parameter rows below are
        # shown or hidden per equation (see set_eos_parameter_names). The
        # combobox entries are configured by the controller
        # (configure_eos_types) from what Peritheos supports.
        self.eos_type_cb = QtWidgets.QComboBox()
        self.eos_type_lbl = LabelAlignRight('EoS:')
        self._eos_layout.addWidget(self.eos_type_lbl, 0, 0)
        self._eos_layout.addWidget(self.eos_type_cb, 0, 1, 1, 2)

        self.eos_K_txt = NumberTextField()
        self.eos_P0_txt = NumberTextField()
        self.eos_P0_txt.setToolTip(
            'Reference pressure: V0 and K0 are defined at this pressure. '
            "BM2Reference fixes K' at the reference state to 4.")
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
        self.eos_z_txt.setToolTip('Electrons per chemical formula, initialized from the formula or record. '
                                 'Not recalculated by atomic-site or space-group edits.')
        self.eos_zc_txt.setToolTip('Formula units per cell, imported or explicitly set. '
                                  'Compared with the independently calculated Z in Volume & structure; '
                                  'retained after structural edits.')

        # thermal model on top of the equation above: the classic
        # constant-coefficient correction, or a peritheos thermal engine
        self.thermal_type_cb = QtWidgets.QComboBox()
        self.thermal_type_cb.addItem('None', 'none')
        self.thermal_type_cb.addItem('Legacy α, dK/dT correction', 'alphakt')
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

        self._add_eos_param_row('P0', self.eos_P0_txt, 'P<sub>ref</sub>:',
                                'GPa', self._eos_layout.rowCount())
        self._configure_thermal_fields()
        self.eos_calculation_status_lbl = QtWidgets.QLabel()
        self.eos_calculation_status_lbl.setWordWrap(True)
        self.eos_calculation_status_lbl.hide()
        self.eos_scroll_area.setWidget(self._eos_contents)
        self._eos_group_layout = QtWidgets.QVBoxLayout()
        self._eos_group_layout.setContentsMargins(0, 0, 0, 0)
        self._eos_group_layout.addWidget(self._eos_record_widget)
        self._eos_group_layout.addWidget(self.eos_calculation_status_lbl)
        self._eos_group_layout.addWidget(self.eos_scroll_area)
        self.eos_gb.setLayout(self._eos_group_layout)

        self.reflections_gb = QtWidgets.QGroupBox('HKL reflections')
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

        self.parameter_tabs = QtWidgets.QTabWidget()
        self.parameter_tabs.addTab(self.lattice_parameters_gb, 'Volume && structure')
        self.parameter_tabs.addTab(self.eos_gb, 'Equation of state')
        self.parameter_tabs.currentChanged.connect(
            lambda _index: self._record_layout_timer.start(0))
        self._body_layout = QtWidgets.QGridLayout()
        self._body_layout.addWidget(self.parameter_tabs, 0, 0)
        self._body_layout.addWidget(self.reflections_gb, 0, 1)
        self._body_layout.setColumnStretch(1, 1)
        self._body_layout.setRowStretch(0, 1)

        self._button_layout = QtWidgets.QHBoxLayout()
        self.save_as_btn = QtWidgets.QPushButton('Save As…')
        self.reload_file_btn = QtWidgets.QPushButton('Reload File')

        self._button_layout.addWidget(self.save_as_btn)
        self._button_layout.addWidget(self.reload_file_btn)
        self._button_layout.addSpacerItem(HorizontalSpacerItem())

        self._layout.addLayout(self._body_layout)
        self._layout.addLayout(self._button_layout)
        self.setLayout(self._layout)

        self.style_widgets()
        self.resize(1200, 740)

    def style_widgets(self):
        for field in (
                self.lattice_a_sb, self.lattice_b_sb, self.lattice_c_sb,
                self.lattice_eos_a_txt, self.lattice_eos_b_txt, self.lattice_eos_c_txt,
                self.lattice_alpha_sb, self.lattice_beta_sb, self.lattice_gamma_sb,
                self.lattice_volume_txt, self.lattice_eos_volume_txt,
                self.lattice_ab_sb, self.lattice_ca_sb, self.lattice_cb_sb):
            field.setFixedWidth(88)
        for field in (self.lattice_angle_step_txt, self.lattice_length_step_txt,
                      self.lattice_ratio_step_txt):
            field.setFixedWidth(48)

        # Tab labels identify the pages; keep the content free of duplicate
        # headings and leave spare lattice-page space below the compact form.
        for page in (self.lattice_parameters_gb, self.eos_gb):
            page.setTitle('')
            page.setFlat(True)
        self._lattice_parameters_layout.setAlignment(QtCore.Qt.AlignTop)
        self.parameter_tabs.setMinimumWidth(520)
        self.parameter_tabs.setMaximumWidth(560)

        self.reflection_table_view.setShowGrid(False)
        self.reflection_table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.reflection_table_view.setItemDelegate(TextDoubleDelegate())
        self.reflection_table_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

        # wide enough for the EoS/thermal display names ("Birch-Murnaghan
        # (3rd order)", "Constant α, dK/dT") and the unit labels
        self.eos_gb.setMinimumHeight(300)
        for combo in (self.eos_type_cb, self.thermal_type_cb,
                      *self.thermal_configuration_fields.values()):
            combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(12)
            combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.eos_gb.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._record_layout_timer.start(0)

    def _fit_record_details(self):
        # QLabel's wrapped height can change after the grid is laid out.
        # Reserve that height before allocating the remaining space to the
        # scrollable coefficients, so status and assessment lines never overlap.
        height = self._eos_record_widget.heightForWidth(self._eos_record_widget.width())
        if height >= 0:
            self._eos_record_widget.setMinimumHeight(height)

    def show_eos_details(self):
        """Keep the complete scientific assessment available on demand."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle('EoS record details')
        dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        layout = QtWidgets.QVBoxLayout(dialog)
        title = QtWidgets.QLabel(self.eos_record_cb.currentText())
        title.setWordWrap(True)
        layout.addWidget(title)
        details = QtWidgets.QPlainTextEdit()
        details.setReadOnly(True)
        details.setPlainText(self.eos_record_status_lbl.toolTip() + '\n\n'
                             + self.eos_reproduction_lbl.toolTip())
        layout.addWidget(details)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(640, 440)
        self._eos_details_dialog = dialog
        dialog.open()

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
        'Sokolova2016': ('n', 'Zc'),
    }

    def _configure_thermal_fields(self):
        """Expose complete thermal constructors, preserving the familiar fields."""
        self.THERMAL_PARAM_SETS = dict(self.THERMAL_PARAM_SETS)
        self.THERMAL_MATERIAL_KEYS = dict(self.THERMAL_MATERIAL_KEYS)
        self.thermal_parameter_fields = {}
        self.thermal_configuration_fields = {}
        familiar = {
            'MieGruneisenDebye': {'Tr', 'theta0', 'gamma0', 'q', 'n'},
            'MieGruneisenEinstein': {'Tr', 'theta0', 'gamma0', 'q', 'n'},
            'Sokolova2016': {'Tr', 'n', *self.sokolova_parameter_fields},
        }
        labels = {
            'AlphaKT': 'AlphaKT (thermal reference state)',
            'DoubleDebyeHelmholtz': 'Double-Debye Helmholtz',
            'DoubleDebyeLogMomentHelmholtz': 'Double-Debye (log moment)',
            'MultiOscillatorGruneisen': 'Multi-oscillator Grüneisen',
            'ThermalModifiedTait': 'Thermal Modified Tait',
            'HollandPowellThermalPressure': 'Holland–Powell thermal pressure',
        }
        for model in THERMAL_EOS_TYPES:
            if self.thermal_type_cb.findData(model) < 0:
                self.thermal_type_cb.addItem(labels.get(model, model), model)
            names = list(self.THERMAL_PARAM_SETS.get(model, ()))
            if model not in NON_MOLAR_THERMAL_TYPES:
                self.THERMAL_MATERIAL_KEYS[model] = ('n', 'Zc')
            for name, parameter in thermal_parameter_signature(model).items():
                if name in familiar.get(model, ()) or name == 'n':
                    continue
                key = model + '_' + name
                if name in THERMAL_CONFIGURATION_CHOICES:
                    field = QtWidgets.QComboBox()
                    for choice in THERMAL_CONFIGURATION_CHOICES[name]:
                        field.addItem(choice.replace('_', ' '), choice)
                    self.thermal_configuration_fields[model, name] = field
                else:
                    field = NumberTextField()
                    self.thermal_parameter_fields[model, name] = field
                default = parameter.default
                field.setToolTip(
                    f'{name}: required' if default is inspect.Parameter.empty
                    else f'{name}: default {default}; leave blank to use the default')
                unit = 'K' if name == 'Tr' or name.startswith(('theta', 'QE', 'QB')) else None
                if name in ('Vp', 'Ve'):
                    unit = 'J/bar/mol'
                elif name == 'dK_dT':
                    unit = 'GPa/K'
                elif model == 'AlphaKT' and name == 'alpha0':
                    unit = '1/K'
                parameter_label = {
                    'Tr': 'T ref', 'alpha0': 'α₀', 'alpha1': 'α₁',
                    'dK_dT': 'dK/dT', 'kprime_log_coefficient': 'K′ log coefficient',
                }.get(name, name.replace('_', ' '))
                if name == 'Tr' and default is None:
                    field.setToolTip('Reference temperature in K. Blank uses the absolute 0 K cold curve, including zero-point pressure.')
                self._add_thermal_param_row(key, field, parameter_label + ':',
                                            unit, len(self._thermal_param_rows) + 8)
                label = self._thermal_param_rows[key][0]
                label.setWordWrap(True)
                label.setMinimumWidth(120)
                label.setMaximumWidth(130)
                names.append(key)
            self.THERMAL_PARAM_SETS[model] = names

    def update_thermal_compatibility(self, phase):
        parameters = phase.params.get('thermal_parameters') or {}
        thermal_type = phase.params.get('thermal_type') or ''
        eos_type = phase.params.get('eos_type') or 'BM3'
        for index in range(self.eos_type_cb.count()):
            key = self.eos_type_cb.itemData(index)
            error = thermal_compatibility_error(key, thermal_type, parameters)
            item = self.eos_type_cb.model().item(index)
            item.setEnabled(not error)
            item.setToolTip(error or self.eos_type_cb.itemText(index))
        for index in range(self.thermal_type_cb.count()):
            key = self.thermal_type_cb.itemData(index)
            error = thermal_compatibility_error(
                eos_type, key, parameters if key == thermal_type else {})
            item = self.thermal_type_cb.model().item(index)
            item.setEnabled(not error)
            item.setToolTip(error or self.thermal_type_cb.itemText(index))
        error = ''
        if thermal_type:
            try:
                EosPhase.from_jcpds(phase, with_thermal=True)
            except (ValueError, RuntimeError) as exception:
                error = f'Cannot evaluate selected thermal model: {exception}'
        self.show_eos_error(error)

    def show_eos_error(self, message):
        self.eos_calculation_status_lbl.setText(message)
        self.eos_calculation_status_lbl.setVisible(bool(message))

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
        if index < 0:
            # Published Peritheos records may use a model that Dioptas does
            # not offer for hand-authored records. Show its real name in the
            # disabled selector instead of misrepresenting it as "None".
            self.thermal_type_cb.addItem(str(key), key)
            index = self.thermal_type_cb.count() - 1
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
        if index < 0:
            # Keep published models visible even if the editor has no form
            # for creating them (for example RydbergStacey and Vinet3).
            self.eos_type_cb.addItem(str(key), key)
            index = self.eos_type_cb.count() - 1
        self.eos_type_cb.setCurrentIndex(max(0, index))
        self.eos_type_cb.blockSignals(False)
        self.update_eos_parameter_visibility()

    def get_eos_type(self):
        """The peritheos class name of the selected equation."""
        return self.eos_type_cb.currentData()

    def update_eos_records(self, labels, current_index=0, *, origins=None,
                           default_index=0, material_origin='legacy',
                           reloadable=None, reproduction_details=None,
                           record_warnings=None):
        """Refresh the material-record selector without emitting a change."""
        origins = origins or []
        reproduction_details = reproduction_details or []
        self.eos_record_cb.blockSignals(True)
        self.eos_record_cb.clear()
        if labels:
            for index, label in enumerate(labels):
                prefix = '★ ' if index == default_index else ''
                self.eos_record_cb.addItem(prefix + label)
                if index < len(reproduction_details):
                    self.eos_record_cb.setItemData(
                        index, label + '\n\n' + reproduction_details[index],
                        QtCore.Qt.ToolTipRole)
            self.eos_record_cb.setCurrentIndex(
                max(0, min(current_index, len(labels) - 1)))
            self.eos_record_cb.setEnabled(True)
        else:
            self.eos_record_cb.addItem('No saved EoS record')
            self.eos_record_cb.setEnabled(False)
        self.eos_record_cb.blockSignals(False)
        detail = (reproduction_details[current_index] if
                  labels and 0 <= current_index < len(reproduction_details) else '')
        self.eos_record_cb.setToolTip(
            self.eos_record_cb.currentText() + '\n\n' + detail if labels else '')
        self.eos_reproduction_lbl.setText(detail.split('\n\n', 1)[0])
        self.eos_reproduction_lbl.setToolTip(detail)
        self.eos_reproduction_lbl.hide()
        self.eos_details_btn.setEnabled(bool(labels and detail))
        warning = ((record_warnings or [])[current_index] if
                   labels and 0 <= current_index < len(record_warnings or []) else '')
        self.eos_warning_lbl.setText('⚠ ' + warning if warning else '')
        self.eos_warning_lbl.setToolTip(detail)
        self.eos_warning_lbl.setVisible(bool(warning))

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
        short_status = ('Published · read-only' if origin == 'bundled' else
                        'Custom record' if origin == 'custom' else
                        'User record' if labels else 'Unsaved parameters')
        self.eos_record_status_lbl.setText(short_status)
        self.eos_record_status_lbl.setToolTip(status)
        self.eos_record_duplicate_btn.setToolTip(
            'Make an editable copy of the selected record.')
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
            else 'This material was loaded from the Peritheos library and '
                 'has no source file to reload.')
        self._record_layout_timer.start(0)

    def set_eos_parameter_editable(self, editable):
        """Lock the calculation fields when a bundled record is active."""
        widgets = [
            self.eos_type_cb, self.thermal_type_cb,
            self.eos_K_txt, self.eos_Kp_txt, self.eos_Kpp_txt, self.eos_P0_txt,
            self.eos_n_txt, self.eos_z_txt, self.eos_zc_txt,
            self.eos_alphaT_txt, self.eos_dalphadT_txt,
            self.eos_dKdT_txt, self.eos_dKpdT_txt,
            self.eos_theta_txt, self.eos_gamma_txt, self.eos_qt_txt,
            self.eos_tref_txt, *self.sokolova_parameter_fields.values(),
            *self.thermal_parameter_fields.values(),
            *self.thermal_configuration_fields.values(),
        ]
        for widget in widgets:
            widget.setEnabled(editable)

    def set_material_editable(self, editable):
        """Lock the curated structure and reflection table of DB materials."""
        self._set_atomic_positions_editable(editable)
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
                if column == 1 and isinstance(widget, QtWidgets.QComboBox):
                    self._eos_layout.addWidget(widget, grid_row, column, 1, 2)
                else:
                    self._eos_layout.addWidget(widget, grid_row, column)
            grid_row += 1

        # Any extra height belongs below the form, never between fields.
        self._eos_layout.setRowStretch(grid_row, 1)

    def show_jcpds(self, jcpds_phase, wavelength=None):
        self.update_name(jcpds_phase)
        self.update_structure_information(jcpds_phase)
        self.update_lattice_parameters(jcpds_phase)
        self.update_eos_parameters(jcpds_phase)
        self.reflection_table_model.update_reflection_data(jcpds_phase.reflections,
                                                           wavelength)

    def _update_structure_composition(self, document, stored_z):
        label = self.structure_composition_lbl
        label.setVisible(bool(document.get('atom_sites')))
        if not document.get('atom_sites'):
            return
        result = assess_structure_composition(document)
        tooltip = f"Chemical formula: {document.get('formula') or 'not available'}\n" + result.details()
        warning = result.status != 'consistent'
        if result.z is not None:
            text = f'Calculated Z = {result.z:.6g} · formula matches'
            if stored_z is not None and not np.isclose(
                    float(stored_z), result.z, rtol=1e-4, atol=1e-8):
                text = f'Calculated Z = {result.z:.6g} · differs from stored Z'
                tooltip += f'\nStored Z = {stored_z}; calculated Z = {result.z:.6g}.'
                warning = True
        elif result.status == 'mismatch':
            text = 'Formula mismatch · no common Z'
        else:
            text = 'Calculated Z unavailable'
        label.setText(text)
        label.setToolTip(tooltip)
        label.setStyleSheet('color: #e6ab50;' if warning else '')

    def update_structure_information(self, jcpds_phase):
        document = jcpds_phase.params.get('material_document') or {}
        self._structure_can_add = bool(document.get('space_group'))
        self._structure_sites = document.get('atom_sites') or []
        parts = []
        symbol = document.get('space_group')
        number = document.get('space_group_number')
        self.space_group_cb.set_applied_group(symbol, number)
        self.space_group_widget.setVisible(bool(symbol or number or self._structure_sites))
        z = jcpds_phase.params.get('zc')
        if z is None:
            z = document.get('formula_units_per_cell')
        if z is not None:
            parts.append(f'Stored Z = {z}')
        assumed = (document.get('source') or {}).get('assumed_structure') or {}
        if assumed:
            parts.insert(0, 'Assumed structure')
        if (document.get('source') or {}).get('structure_modified'):
            parts.insert(0, 'Edited structure')
        self._structure_note = assumed.get('note', '')
        self.structure_summary_lbl.setText(' · '.join(parts))
        self.structure_summary_lbl.setToolTip(
            (self._structure_note + '\n\n' if self._structure_note else '')
            + 'Stored Z: formula units per cell used by the EoS, imported or explicitly set. '
              'The calculated Z below is checked independently after structural edits.')
        self.structure_summary_lbl.setVisible(bool(parts))
        self._update_structure_composition(document, z)
        self.structure_note_lbl.setText(self._structure_note)
        self.structure_note_lbl.setVisible(bool(self._structure_note))
        self.structure_sites_caption.setVisible(bool(self._structure_sites))
        self.structure_sites_table.setVisible(bool(self._structure_sites))
        self.structure_summary_widget.setVisible(bool(parts or self._structure_sites or symbol or number))
        self.structure_edit_status_lbl.hide()
        # Keep optional source fields, including displacement parameters, rather
        # than silently reducing sites to position and element alone.
        keys = dict.fromkeys(key for site in self._structure_sites for key in site)
        preferred = ('label', '_label', 'element', 'x', 'y', 'z', 'occupancy', 'wyckoff')
        columns = [key for key in preferred if key in keys]
        columns.extend(key for key in keys if key not in columns)
        table = self.structure_sites_table
        blocker = QtCore.QSignalBlocker(table)
        selected_row = table.currentRow()
        selected_key = (table.currentItem().data(QtCore.Qt.UserRole)
                        if table.currentItem() else None)
        table.clear()
        table.setRowCount(len(self._structure_sites))
        table.setColumnCount(len(columns))
        headings = {'occupancy': 'Occ.', 'wyckoff': 'Site', 'u_iso_angstrom2': 'Uiso (Å²)'}
        table.setHorizontalHeaderLabels([
            headings.get(key, key.lstrip('_').replace('_', ' ').title()) for key in columns])
        for column, key in enumerate(columns):
            table.horizontalHeaderItem(column).setToolTip(
                {'wyckoff': 'Wyckoff site',
                 'u_iso_angstrom2': 'Isotropic mean-square displacement (Å²)'}.get(
                    key, key.lstrip('_').replace('_', ' ').title()))
        for row, site in enumerate(self._structure_sites):
            for column, key in enumerate(columns):
                value = site.get(key)
                item = QtWidgets.QTableWidgetItem('' if value is None else str(value))
                item.setData(QtCore.Qt.UserRole, key)
                item.setToolTip(item.text())
                if isinstance(value, (int, float)):
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                table.setItem(row, column, item)
        table.resizeColumnsToContents()
        header = table.horizontalHeader()
        for column in range(len(columns)):
            label = table.horizontalHeaderItem(column).text()
            # Allow for capitalization and this table's compact header padding.
            width = header.fontMetrics().horizontalAdvance(label.upper()) + 12
            table.setColumnWidth(column, max(table.columnWidth(column), width))
        self._set_atomic_positions_editable(jcpds_phase.params.get('material_origin') != 'bundled')
        if 0 <= selected_row < table.rowCount() and selected_key in columns:
            table.setCurrentCell(selected_row, columns.index(selected_key))
        del blocker
        self._update_site_buttons()

    def _request_element_edit(self, row, column):
        item = self.structure_sites_table.item(row, column)
        if (getattr(self, '_atomic_sites_editable', False) and item is not None
                and item.data(QtCore.Qt.UserRole) == 'element'):
            self.element_edit_requested.emit(row)

    def eventFilter(self, watched, event):
        if (watched is self.structure_sites_table and event.type() == QtCore.QEvent.KeyPress
                and event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_F2)):
            item = self.structure_sites_table.currentItem()
            if (getattr(self, '_atomic_sites_editable', False) and item is not None
                    and item.data(QtCore.Qt.UserRole) == 'element'):
                self.element_edit_requested.emit(item.row())
                return True
        return super().eventFilter(watched, event)

    def selected_atomic_site_rows(self):
        return sorted({index.row() for index in self.structure_sites_table.selectedIndexes()})

    def _update_site_buttons(self):
        editable = getattr(self, '_atomic_sites_editable', False)
        self.structure_site_add_btn.setEnabled(editable and getattr(self, '_structure_can_add', False))
        rows = self.selected_atomic_site_rows()
        self.structure_site_remove_btn.setEnabled(
            editable and bool(rows) and len(rows) < self.structure_sites_table.rowCount())
        self.structure_site_remove_btn.setToolTip(
            'Remove selected sites and recalculate reflections. Keep at least one atomic site.')

    def _set_atomic_positions_editable(self, editable):
        self._atomic_sites_editable = editable
        can_edit_group = editable and bool(getattr(self, '_structure_sites', []))
        self.space_group_txt.setReadOnly(not can_edit_group)
        self.space_group_cb.setEnabled(can_edit_group)
        self.space_group_apply_btn.setEnabled(can_edit_group)
        table = self.structure_sites_table
        table.setEditTriggers(
            (QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.EditKeyPressed)
            if editable else QtWidgets.QAbstractItemView.NoEditTriggers)
        blocker = QtCore.QSignalBlocker(table)
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                item = table.item(row, column)
                flags = item.flags() & ~QtCore.Qt.ItemIsEditable
                key = item.data(QtCore.Qt.UserRole)
                if editable and key in self.EDITABLE_SITE_FIELDS and key != 'element':
                    flags |= QtCore.Qt.ItemIsEditable
                item.setFlags(flags)
        table.setToolTip(
            'Double-click an element to open the periodic table, or edit a coordinate, '
            'occupancy or isotropic displacement. '
            'Reflections are recalculated after each valid edit.' if editable else
            'Published structure — read-only. Export and reload an .eosmat file to edit it.')
        del blocker
        self._update_site_buttons()

    def update_eos_parameters(self, jcpds_phase):
        self.set_eos_type(str(jcpds_phase.params.get('eos_type') or 'BM3'))
        self.eos_K_txt.setText(str(jcpds_phase.params['k0']))
        self.eos_P0_txt.setText(str(jcpds_phase.params.get('p0', 0.0)))
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
        for (model, parameter), field in self.thermal_parameter_fields.items():
            default = thermal_parameter_signature(model)[parameter].default
            value = thermal_parameters.get(parameter, default)
            field.setText('' if value is None or value is inspect.Parameter.empty else str(value))
        for (model, parameter), field in self.thermal_configuration_fields.items():
            value = thermal_parameters.get(
                parameter, thermal_parameter_signature(model)[parameter].default)
            field.blockSignals(True)
            field.setCurrentIndex(max(0, field.findData(value)))
            field.blockSignals(False)
        thermal_type = str(jcpds_phase.params.get('thermal_type') or '')
        if thermal_type:
            self.set_thermal_type(thermal_type)
        else:
            has_thermal = any(jcpds_phase.params[key] for key in
                              ('alpha_t0', 'd_alpha_dt', 'dk0dt', 'dk0pdt'))
            self.set_thermal_type('alphakt' if has_thermal else 'none')
        self.update_thermal_compatibility(jcpds_phase)

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
