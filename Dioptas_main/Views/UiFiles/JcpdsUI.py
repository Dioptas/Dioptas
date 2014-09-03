# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Jcpds.ui'
#
# Created: Wed Sep  3 12:42:21 2014
#      by: PyQt4 UI code generator 4.10.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_JcpdsEditorWidget(object):
    def setupUi(self, JcpdsEditorWidget):
        JcpdsEditorWidget.setObjectName(_fromUtf8("JcpdsEditorWidget"))
        JcpdsEditorWidget.resize(603, 618)
        JcpdsEditorWidget.setStyleSheet(_fromUtf8("#mainView, #calibration_tab, #mask_tab, #integration_tab {  \n"
"     background: #3C3C3C;      \n"
"    border: 5px solid #3C3C3C;\n"
" }  \n"
"\n"
"QTabWidget::tab-bar{ \n"
"    alignment: center;\n"
"}\n"
"\n"
"QWidget{\n"
"    color: #F1F1F1;\n"
"}\n"
"\n"
"\n"
"QTabBar::tab:left, QTabBar::tab:right {  \n"
"     background: qlineargradient(spread:pad, x1:1, y1:0, x2:0, y2:0, stop:0 #3C3C3C, stop:1 #505050);\n"
"     border: 1px solid  #5B5B5B;  \n"
"    font: normal 14px;\n"
"    color: #F1F1F1;\n"
"     border-radius:2px;\n"
"    \n"
"    padding: 0px;\n"
"     width: 20px;  \n"
"    min-height:140px;\n"
" }  \n"
"\n"
"\n"
"QTabBar::tab::top, QTabBar::tab::bottom {  \n"
"     background: qlineargradient(spread:pad, x1:0, y1:1, x2:0, y2:0, stop:0 #3C3C3C, stop:1 #505050);\n"
"     border: 1px solid  #5B5B5B;  \n"
"    border-right: 0px solid white;\n"
"      color: #F1F1F1; \n"
"    font: normal 11px;\n"
"     border-radius:2px;\n"
"     min-width: 80px;  \n"
"    height: 19px;\n"
"    padding: 0px;\n"
"     margin-top: 1px ;\n"
"    margin-right: 1px;\n"
" }  \n"
"QTabBar::tab::left:last, QTabBar::tab::right:last{\n"
"    border-bottom-left-radius: 10px;\n"
"    border-bottom-right-radius: 10px;\n"
"}\n"
"QTabBar::tab:left:first, QTabBar::tab:right:first{\n"
"    border-top-left-radius: 10px;\n"
"    border-top-right-radius: 10px;\n"
"}\n"
"\n"
"QTabWidget, QTabWidget::tab-bar,  QTabWidget::panel, QWidget{  \n"
"     background: #3C3C3C;      \n"
" }  \n"
"\n"
"QTabWidget::tab-bar {\n"
"    alignment: center;\n"
"}\n"
"\n"
" QTabBar::tab:hover {  \n"
"     border: 1px solid #ADADAD;  \n"
" }  \n"
"   \n"
" QTabBar:tab:selected{  \n"
"\n"
"    background: qlineargradient(\n"
"        x1: 0, y1: 1, \n"
"        x2: 0, y2: 0,\n"
"        stop: 0 #727272, \n"
"        stop: 1 #444444\n"
"    );\n"
"     border:1px solid  rgb(255, 120,00);/*#ADADAD; */ \n"
"}\n"
"\n"
"QTabBar::tab:bottom:last, QTabBar::tab:top:last{\n"
"    border-top-right-radius: 10px;\n"
"    border-bottom-right-radius: 10px;\n"
"}\n"
"QTabBar::tab:bottom:first, QTabBar::tab:top:first{\n"
"    border-top-left-radius: 10px;\n"
"    border-bottom-left-radius: 10px;\n"
"}\n"
" QTabBar::tab:top:!selected {  \n"
"    margin-top: 1px;\n"
"    padding-top:1px;\n"
" }  \n"
"QTabBar::tab:bottom:!selected{\n"
"    margin-bottom: 1px;\n"
"    padding-bottom:1px;\n"
"}\n"
"\n"
"QGraphicsView {\n"
"    border-style: none;\n"
"}\n"
"\n"
" QLabel , QCheckBox, QGroupBox, QRadioButton, QListWidget::item, QPushButton, QToolBox::tab, QSpinBox, QDoubleSpinBox , QComboBox{  \n"
"     color: #F1F1F1; \n"
"    font-size: 12px;\n"
" }  \n"
" QCheckBox{  \n"
"     border-radius: 5px;  \n"
" }  \n"
" QRadioButton, QCheckBox {  \n"
"     font-weight: normal;  \n"
"    height: 15px;\n"
" }  \n"
" \n"
" QLineEdit  {  \n"
"     border-radius: 2px;  \n"
"     background: #F1F1F1;  \n"
"     color: black;  \n"
"    height: 18 px;\n"
" }  \n"
"\n"
"QLineEdit::focus{\n"
"    border-style: none;\n"
"     border-radius: 2px;  \n"
"     background: #F1F1F1;  \n"
"     color: black;  \n"
"}\n"
"\n"
"QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled{\n"
"    color:rgb(148, 148, 148)\n"
"}\n"
"QSpinBox, QDoubleSpinBox {\n"
"    background-color:  #F1F1F1;    \n"
"    color: black;\n"
"    margin-left: -15px;\n"
"    margin-right: -2px;\n"
"    height: 30px;\n"
"}\n"
"\n"
"QComboBox QAbstractItemView{\n"
"    background: #2D2D30;\n"
"    color: #F1F1F1;\n"
"    selection-background-color: rgba(221, 124, 40, 120);\n"
"    border-radius: 5px;\n"
"\n"
"}\n"
"\n"
"QComboBox:!editable {\n"
"    margin-left: 1px;\n"
"    padding-left: 10px;\n"
"    height: 23px;\n"
"    background-color: #3C3C3C;\n"
"}\n"
"\n"
"QComboBox::item{\n"
"    background-color: #3C3C3C;\n"
"}\n"
"\n"
"QComboBox::item::selected {\n"
"    background-color: #505050;\n"
"}\n"
"QToolBox::tab:QToolButton{\n"
"    background: qlineargradient(spread:pad, x1:0, y1:1, x2:0, y2:0, stop:0 #3C3C3C, stop:1 #505050);\n"
"     border: 1px solid  #5B5B5B;  \n"
"\n"
"     border-radius:2px;\n"
"     padding-right: 10px;  \n"
"    \n"
"      color: #F1F1F1; \n"
"    font-size: 12px;\n"
"    padding: 3px;\n"
"}\n"
"QToolBox::tab:QToolButton{\n"
"    background: qlineargradient(spread:pad, x1:0, y1:1, x2:0, y2:0, stop:0 #3C3C3C, stop:1 #505050);\n"
"     border: 1px solid  #5B5B5B;  \n"
"\n"
"     border-radius:2px;\n"
"     padding-right: 10px;  \n"
"    \n"
"      color: #F1F1F1; \n"
"    font-size: 12px;\n"
"    padding: 3px;\n"
"}\n"
"  \n"
"QPushButton{  \n"
"     color: #F1F1F1;\n"
"     background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #323232, stop:1 #505050);\n"
"     border: 1px solid #5B5B5B;\n"
"     border-radius: 5px; \n"
"     padding-left: 8px;\n"
"height: 18px;\n"
"    padding-right: 8px;   \n"
" }  \n"
"QPushButton:pressed{\n"
"        margin-top: 2px;\n"
"        margin-left: 2px;    \n"
"}\n"
"QPushButton::disabled{\n"
"}\n"
"\n"
"QPushButton::hover{  \n"
"     border:1px solid #ADADAD; \n"
" }  \n"
" \n"
"\n"
"QPushButton::checked{\n"
"    background: qlineargradient(\n"
"        x1: 0, y1: 1, \n"
"        x2: 0, y2: 0,\n"
"        stop: 0 #727272, \n"
"        stop: 1 #444444\n"
"    );\n"
"     border:1px solid  rgb(255, 120,00);\n"
"}\n"
"\n"
"QPushButton::focus {\n"
"    outline: None;\n"
"}\n"
" QGroupBox {  \n"
"     border: 1px solid #ADADAD;  \n"
"     border-radius: 4px;  \n"
"     margin-top: 7px;  \n"
"     padding: 0px  \n"
" }  \n"
" QGroupBox::title {  \n"
"      subcontrol-origin: margin;  \n"
"      left: 20px  \n"
"  }\n"
"\n"
"QSplitter::handle:hover {\n"
"    background: #3C3C3C;\n"
" }\n"
"\n"
"\n"
"QGraphicsView{\n"
"    border-style: none;\n"
"}\n"
"\n"
" QScrollBar:vertical {\n"
"      border: 2px solid #3C3C3C;\n"
"      background: qlineargradient(spread:pad, x1:1, y1:0, x2:0, y2:0, stop:0 #323232, stop:1 #505050);\n"
"      width: 12px;\n"
"      margin: 0px 0px 0px 0px;\n"
"  }\n"
"  QScrollBar::handle:vertical {\n"
"      background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #969696, stop:1 #CACACA);\n"
"     border-radius: 3px;\n"
"      min-height: 20px;\n"
"    padding: 15px;\n"
"  }\n"
"  QScrollBar::add-line:vertical {\n"
"      border: 0px solid grey;\n"
"      height: 0px;\n"
"  }\n"
"\n"
"  QScrollBar::sub-line:vertical {\n"
"      border: 0px solid grey;\n"
"      height: 0px;\n"
"  }\n"
"  QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {\n"
"      background: none;\n"
"  }\n"
"\n"
"QScrollBar:horizontal {\n"
"    border: 2px solid #3C3C3C;\n"
"    background: qlineargradient(spread:pad, x1:0, y1:1, x2:0, y2:0, stop:0 #323232, stop:1 #505050);\n"
"    height: 12 px;\n"
"    margin: 0px 0px 0px 0px;\n"
"}\n"
"\n"
"QScrollBar::handle:horizontal {\n"
"    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #969696, stop:1 #CACACA);\n"
"   border-radius: 3px;\n"
"    min-width: 20px;\n"
"  padding: 15px;\n"
"}\n"
"QScrollBar::add-line:horizontal {\n"
"    border: 0px solid grey;\n"
"    height: 0px;\n"
"}\n"
"\n"
"QScrollBar::sub-line:horizontal {\n"
"    border: 0px solid grey;\n"
"    height: 0px;\n"
"}\n"
"QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {\n"
"    background: none;\n"
"}\n"
"\n"
"#click_x_lbl, #click_y_lbl, #click_int_lbl, #click_azi_lbl, #click_d_lbl, #click_tth_lbl, #click_q_lbl {\n"
"    color: #00DD00;\n"
"}\n"
"\n"
"QHeaderView::section\n"
"{\n"
"    spacing: 10px;\n"
"    color: #F1F1F1;\n"
"     background: qlineargradient(spread:pad, x1:0, y1:1, x2:0, y2:0, stop:0 #323232, stop:1 #505050);\n"
"    border: None;\n"
"    font-size: 12px;\n"
"}\n"
"\n"
"QTableWidget {\n"
"    font-size: 12px;\n"
"    text-align: center;\n"
"}\n"
"\n"
""))
        self.verticalLayout_3 = QtGui.QVBoxLayout(JcpdsEditorWidget)
        self.verticalLayout_3.setObjectName(_fromUtf8("verticalLayout_3"))
        self.gridLayout_3 = QtGui.QGridLayout()
        self.gridLayout_3.setObjectName(_fromUtf8("gridLayout_3"))
        self.label_6 = QtGui.QLabel(JcpdsEditorWidget)
        self.label_6.setObjectName(_fromUtf8("label_6"))
        self.gridLayout_3.addWidget(self.label_6, 0, 0, 1, 1)
        self.filename_txt = QtGui.QLineEdit(JcpdsEditorWidget)
        self.filename_txt.setReadOnly(True)
        self.filename_txt.setObjectName(_fromUtf8("filename_txt"))
        self.gridLayout_3.addWidget(self.filename_txt, 0, 1, 1, 1)
        self.label_8 = QtGui.QLabel(JcpdsEditorWidget)
        self.label_8.setObjectName(_fromUtf8("label_8"))
        self.gridLayout_3.addWidget(self.label_8, 1, 0, 1, 1)
        self.comments_txt = QtGui.QLineEdit(JcpdsEditorWidget)
        self.comments_txt.setFrame(True)
        self.comments_txt.setCursorMoveStyle(QtCore.Qt.VisualMoveStyle)
        self.comments_txt.setObjectName(_fromUtf8("comments_txt"))
        self.gridLayout_3.addWidget(self.comments_txt, 1, 1, 1, 1)
        self.verticalLayout_3.addLayout(self.gridLayout_3)
        spacerItem = QtGui.QSpacerItem(20, 15, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.MinimumExpanding)
        self.verticalLayout_3.addItem(spacerItem)
        spacerItem1 = QtGui.QSpacerItem(0, 10, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout_3.addItem(spacerItem1)
        self.groupBox_4 = QtGui.QGroupBox(JcpdsEditorWidget)
        self.groupBox_4.setObjectName(_fromUtf8("groupBox_4"))
        self.verticalLayout_5 = QtGui.QVBoxLayout(self.groupBox_4)
        self.verticalLayout_5.setObjectName(_fromUtf8("verticalLayout_5"))
        self.horizontalLayout_4 = QtGui.QHBoxLayout()
        self.horizontalLayout_4.setObjectName(_fromUtf8("horizontalLayout_4"))
        self.label_50 = QtGui.QLabel(self.groupBox_4)
        self.label_50.setObjectName(_fromUtf8("label_50"))
        self.horizontalLayout_4.addWidget(self.label_50)
        self.symmetry_cb = QtGui.QComboBox(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.symmetry_cb.sizePolicy().hasHeightForWidth())
        self.symmetry_cb.setSizePolicy(sizePolicy)
        self.symmetry_cb.setMinimumSize(QtCore.QSize(120, 0))
        self.symmetry_cb.setMaximumSize(QtCore.QSize(120, 16777215))
        self.symmetry_cb.setBaseSize(QtCore.QSize(120, 0))
        self.symmetry_cb.setFocusPolicy(QtCore.Qt.NoFocus)
        self.symmetry_cb.setObjectName(_fromUtf8("symmetry_cb"))
        self.symmetry_cb.addItem(_fromUtf8(""))
        self.symmetry_cb.addItem(_fromUtf8(""))
        self.symmetry_cb.addItem(_fromUtf8(""))
        self.symmetry_cb.addItem(_fromUtf8(""))
        self.symmetry_cb.addItem(_fromUtf8(""))
        self.symmetry_cb.addItem(_fromUtf8(""))
        self.horizontalLayout_4.addWidget(self.symmetry_cb)
        spacerItem2 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_4.addItem(spacerItem2)
        self.verticalLayout_5.addLayout(self.horizontalLayout_4)
        self.gridLayout_5 = QtGui.QGridLayout()
        self.gridLayout_5.setSizeConstraint(QtGui.QLayout.SetDefaultConstraint)
        self.gridLayout_5.setHorizontalSpacing(5)
        self.gridLayout_5.setObjectName(_fromUtf8("gridLayout_5"))
        self.lattice_eos_volume_txt = QtGui.QLineEdit(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_eos_volume_txt.sizePolicy().hasHeightForWidth())
        self.lattice_eos_volume_txt.setSizePolicy(sizePolicy)
        self.lattice_eos_volume_txt.setMinimumSize(QtCore.QSize(30, 0))
        self.lattice_eos_volume_txt.setBaseSize(QtCore.QSize(80, 0))
        self.lattice_eos_volume_txt.setAutoFillBackground(False)
        self.lattice_eos_volume_txt.setFrame(True)
        self.lattice_eos_volume_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_eos_volume_txt.setReadOnly(True)
        self.lattice_eos_volume_txt.setObjectName(_fromUtf8("lattice_eos_volume_txt"))
        self.gridLayout_5.addWidget(self.lattice_eos_volume_txt, 4, 7, 1, 1)
        self.label_66 = QtGui.QLabel(self.groupBox_4)
        self.label_66.setObjectName(_fromUtf8("label_66"))
        self.gridLayout_5.addWidget(self.label_66, 1, 2, 1, 1)
        self.lattice_volume_txt = QtGui.QLineEdit(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_volume_txt.sizePolicy().hasHeightForWidth())
        self.lattice_volume_txt.setSizePolicy(sizePolicy)
        self.lattice_volume_txt.setMinimumSize(QtCore.QSize(30, 0))
        self.lattice_volume_txt.setBaseSize(QtCore.QSize(80, 0))
        self.lattice_volume_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_volume_txt.setReadOnly(True)
        self.lattice_volume_txt.setObjectName(_fromUtf8("lattice_volume_txt"))
        self.gridLayout_5.addWidget(self.lattice_volume_txt, 4, 4, 1, 1)
        self.label_5 = QtGui.QLabel(self.groupBox_4)
        self.label_5.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_5.setObjectName(_fromUtf8("label_5"))
        self.gridLayout_5.addWidget(self.label_5, 1, 3, 1, 1)
        self.label_4 = QtGui.QLabel(self.groupBox_4)
        self.label_4.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_4.setObjectName(_fromUtf8("label_4"))
        self.gridLayout_5.addWidget(self.label_4, 1, 0, 1, 1)
        self.label_7 = QtGui.QLabel(self.groupBox_4)
        self.label_7.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_7.setObjectName(_fromUtf8("label_7"))
        self.gridLayout_5.addWidget(self.label_7, 1, 6, 1, 1)
        self.label_65 = QtGui.QLabel(self.groupBox_4)
        self.label_65.setObjectName(_fromUtf8("label_65"))
        self.gridLayout_5.addWidget(self.label_65, 4, 8, 1, 1)
        self.lattice_cb_sb = QtGui.QDoubleSpinBox(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_cb_sb.sizePolicy().hasHeightForWidth())
        self.lattice_cb_sb.setSizePolicy(sizePolicy)
        self.lattice_cb_sb.setBaseSize(QtCore.QSize(80, 0))
        self.lattice_cb_sb.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_cb_sb.setDecimals(4)
        self.lattice_cb_sb.setMaximum(999999999.0)
        self.lattice_cb_sb.setSingleStep(0.01)
        self.lattice_cb_sb.setObjectName(_fromUtf8("lattice_cb_sb"))
        self.gridLayout_5.addWidget(self.lattice_cb_sb, 6, 7, 1, 1)
        self.lattice_a_sb = QtGui.QDoubleSpinBox(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_a_sb.sizePolicy().hasHeightForWidth())
        self.lattice_a_sb.setSizePolicy(sizePolicy)
        self.lattice_a_sb.setBaseSize(QtCore.QSize(80, 0))
        self.lattice_a_sb.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_a_sb.setDecimals(4)
        self.lattice_a_sb.setMaximum(999999999.0)
        self.lattice_a_sb.setSingleStep(0.01)
        self.lattice_a_sb.setObjectName(_fromUtf8("lattice_a_sb"))
        self.gridLayout_5.addWidget(self.lattice_a_sb, 0, 1, 1, 1)
        self.label_60 = QtGui.QLabel(self.groupBox_4)
        self.label_60.setObjectName(_fromUtf8("label_60"))
        self.gridLayout_5.addWidget(self.label_60, 2, 5, 1, 1)
        self.label_59 = QtGui.QLabel(self.groupBox_4)
        self.label_59.setObjectName(_fromUtf8("label_59"))
        self.gridLayout_5.addWidget(self.label_59, 2, 2, 1, 1)
        self.lattice_alpha_sb = QtGui.QDoubleSpinBox(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_alpha_sb.sizePolicy().hasHeightForWidth())
        self.lattice_alpha_sb.setSizePolicy(sizePolicy)
        self.lattice_alpha_sb.setBaseSize(QtCore.QSize(80, 0))
        self.lattice_alpha_sb.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_alpha_sb.setDecimals(3)
        self.lattice_alpha_sb.setMaximum(360.0)
        self.lattice_alpha_sb.setObjectName(_fromUtf8("lattice_alpha_sb"))
        self.gridLayout_5.addWidget(self.lattice_alpha_sb, 2, 1, 1, 1)
        self.lattice_ab_sb = QtGui.QDoubleSpinBox(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_ab_sb.sizePolicy().hasHeightForWidth())
        self.lattice_ab_sb.setSizePolicy(sizePolicy)
        self.lattice_ab_sb.setBaseSize(QtCore.QSize(80, 0))
        self.lattice_ab_sb.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_ab_sb.setDecimals(4)
        self.lattice_ab_sb.setMaximum(999999999.0)
        self.lattice_ab_sb.setSingleStep(0.01)
        self.lattice_ab_sb.setObjectName(_fromUtf8("lattice_ab_sb"))
        self.gridLayout_5.addWidget(self.lattice_ab_sb, 6, 1, 1, 1)
        self.lattice_angle_step_txt = QtGui.QLineEdit(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_angle_step_txt.sizePolicy().hasHeightForWidth())
        self.lattice_angle_step_txt.setSizePolicy(sizePolicy)
        self.lattice_angle_step_txt.setMaximumSize(QtCore.QSize(60, 16777215))
        self.lattice_angle_step_txt.setBaseSize(QtCore.QSize(40, 0))
        self.lattice_angle_step_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_angle_step_txt.setObjectName(_fromUtf8("lattice_angle_step_txt"))
        self.gridLayout_5.addWidget(self.lattice_angle_step_txt, 2, 10, 1, 1)
        self.lattice_ca_sb = QtGui.QDoubleSpinBox(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_ca_sb.sizePolicy().hasHeightForWidth())
        self.lattice_ca_sb.setSizePolicy(sizePolicy)
        self.lattice_ca_sb.setBaseSize(QtCore.QSize(80, 0))
        self.lattice_ca_sb.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_ca_sb.setDecimals(4)
        self.lattice_ca_sb.setMaximum(999999999.0)
        self.lattice_ca_sb.setSingleStep(0.01)
        self.lattice_ca_sb.setObjectName(_fromUtf8("lattice_ca_sb"))
        self.gridLayout_5.addWidget(self.lattice_ca_sb, 6, 4, 1, 1)
        self.label_54 = QtGui.QLabel(self.groupBox_4)
        self.label_54.setObjectName(_fromUtf8("label_54"))
        self.gridLayout_5.addWidget(self.label_54, 0, 2, 1, 1)
        self.label_62 = QtGui.QLabel(self.groupBox_4)
        self.label_62.setObjectName(_fromUtf8("label_62"))
        self.gridLayout_5.addWidget(self.label_62, 0, 5, 1, 1)
        self.label_43 = QtGui.QLabel(self.groupBox_4)
        self.label_43.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_43.setObjectName(_fromUtf8("label_43"))
        self.gridLayout_5.addWidget(self.label_43, 6, 3, 1, 1)
        self.lattice_b_sb = QtGui.QDoubleSpinBox(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_b_sb.sizePolicy().hasHeightForWidth())
        self.lattice_b_sb.setSizePolicy(sizePolicy)
        self.lattice_b_sb.setBaseSize(QtCore.QSize(80, 0))
        self.lattice_b_sb.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_b_sb.setDecimals(4)
        self.lattice_b_sb.setMaximum(999999999.0)
        self.lattice_b_sb.setSingleStep(0.01)
        self.lattice_b_sb.setObjectName(_fromUtf8("lattice_b_sb"))
        self.gridLayout_5.addWidget(self.lattice_b_sb, 0, 4, 1, 1)
        self.line_4 = QtGui.QFrame(self.groupBox_4)
        self.line_4.setFrameShape(QtGui.QFrame.HLine)
        self.line_4.setFrameShadow(QtGui.QFrame.Sunken)
        self.line_4.setObjectName(_fromUtf8("line_4"))
        self.gridLayout_5.addWidget(self.line_4, 5, 0, 1, 9)
        self.lattice_gamma_sb = QtGui.QDoubleSpinBox(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_gamma_sb.sizePolicy().hasHeightForWidth())
        self.lattice_gamma_sb.setSizePolicy(sizePolicy)
        self.lattice_gamma_sb.setBaseSize(QtCore.QSize(80, 0))
        self.lattice_gamma_sb.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_gamma_sb.setDecimals(3)
        self.lattice_gamma_sb.setMaximum(360.0)
        self.lattice_gamma_sb.setObjectName(_fromUtf8("lattice_gamma_sb"))
        self.gridLayout_5.addWidget(self.lattice_gamma_sb, 2, 7, 1, 1)
        self.label = QtGui.QLabel(self.groupBox_4)
        self.label.setObjectName(_fromUtf8("label"))
        self.gridLayout_5.addWidget(self.label, 0, 9, 1, 1)
        self.line_5 = QtGui.QFrame(self.groupBox_4)
        self.line_5.setFrameShape(QtGui.QFrame.HLine)
        self.line_5.setFrameShadow(QtGui.QFrame.Sunken)
        self.line_5.setObjectName(_fromUtf8("line_5"))
        self.gridLayout_5.addWidget(self.line_5, 3, 0, 1, 9)
        self.label_57 = QtGui.QLabel(self.groupBox_4)
        self.label_57.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.label_57.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_57.setObjectName(_fromUtf8("label_57"))
        self.gridLayout_5.addWidget(self.label_57, 0, 6, 1, 1)
        self.lattice_length_step_txt = QtGui.QLineEdit(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_length_step_txt.sizePolicy().hasHeightForWidth())
        self.lattice_length_step_txt.setSizePolicy(sizePolicy)
        self.lattice_length_step_txt.setMaximumSize(QtCore.QSize(60, 16777215))
        self.lattice_length_step_txt.setBaseSize(QtCore.QSize(40, 0))
        self.lattice_length_step_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_length_step_txt.setObjectName(_fromUtf8("lattice_length_step_txt"))
        self.gridLayout_5.addWidget(self.lattice_length_step_txt, 0, 10, 1, 1)
        self.label_2 = QtGui.QLabel(self.groupBox_4)
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.gridLayout_5.addWidget(self.label_2, 2, 9, 1, 1)
        self.lattice_c_sb = QtGui.QDoubleSpinBox(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_c_sb.sizePolicy().hasHeightForWidth())
        self.lattice_c_sb.setSizePolicy(sizePolicy)
        self.lattice_c_sb.setBaseSize(QtCore.QSize(80, 0))
        self.lattice_c_sb.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_c_sb.setDecimals(4)
        self.lattice_c_sb.setMaximum(999999999.0)
        self.lattice_c_sb.setSingleStep(0.01)
        self.lattice_c_sb.setObjectName(_fromUtf8("lattice_c_sb"))
        self.gridLayout_5.addWidget(self.lattice_c_sb, 0, 7, 1, 1)
        self.label_44 = QtGui.QLabel(self.groupBox_4)
        self.label_44.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_44.setObjectName(_fromUtf8("label_44"))
        self.gridLayout_5.addWidget(self.label_44, 2, 0, 1, 1)
        self.label_51 = QtGui.QLabel(self.groupBox_4)
        self.label_51.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_51.setObjectName(_fromUtf8("label_51"))
        self.gridLayout_5.addWidget(self.label_51, 6, 0, 1, 1)
        self.label_3 = QtGui.QLabel(self.groupBox_4)
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.gridLayout_5.addWidget(self.label_3, 6, 9, 1, 1)
        self.label_45 = QtGui.QLabel(self.groupBox_4)
        self.label_45.setObjectName(_fromUtf8("label_45"))
        self.gridLayout_5.addWidget(self.label_45, 2, 8, 1, 1)
        self.label_58 = QtGui.QLabel(self.groupBox_4)
        self.label_58.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.label_58.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_58.setObjectName(_fromUtf8("label_58"))
        self.gridLayout_5.addWidget(self.label_58, 2, 6, 1, 1)
        self.label_42 = QtGui.QLabel(self.groupBox_4)
        self.label_42.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_42.setObjectName(_fromUtf8("label_42"))
        self.gridLayout_5.addWidget(self.label_42, 0, 0, 1, 1)
        self.lattice_ratio_step_txt = QtGui.QLineEdit(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_ratio_step_txt.sizePolicy().hasHeightForWidth())
        self.lattice_ratio_step_txt.setSizePolicy(sizePolicy)
        self.lattice_ratio_step_txt.setMaximumSize(QtCore.QSize(60, 16777215))
        self.lattice_ratio_step_txt.setBaseSize(QtCore.QSize(40, 0))
        self.lattice_ratio_step_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_ratio_step_txt.setObjectName(_fromUtf8("lattice_ratio_step_txt"))
        self.gridLayout_5.addWidget(self.lattice_ratio_step_txt, 6, 10, 1, 1)
        self.label_52 = QtGui.QLabel(self.groupBox_4)
        self.label_52.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_52.setObjectName(_fromUtf8("label_52"))
        self.gridLayout_5.addWidget(self.label_52, 6, 6, 1, 1)
        self.label_63 = QtGui.QLabel(self.groupBox_4)
        self.label_63.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_63.setObjectName(_fromUtf8("label_63"))
        self.gridLayout_5.addWidget(self.label_63, 2, 3, 1, 1)
        self.lattice_beta_sb = QtGui.QDoubleSpinBox(self.groupBox_4)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lattice_beta_sb.sizePolicy().hasHeightForWidth())
        self.lattice_beta_sb.setSizePolicy(sizePolicy)
        self.lattice_beta_sb.setBaseSize(QtCore.QSize(80, 0))
        self.lattice_beta_sb.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_beta_sb.setDecimals(3)
        self.lattice_beta_sb.setMaximum(360.0)
        self.lattice_beta_sb.setObjectName(_fromUtf8("lattice_beta_sb"))
        self.gridLayout_5.addWidget(self.lattice_beta_sb, 2, 4, 1, 1)
        self.label_53 = QtGui.QLabel(self.groupBox_4)
        self.label_53.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_53.setObjectName(_fromUtf8("label_53"))
        self.gridLayout_5.addWidget(self.label_53, 0, 3, 1, 1)
        self.label_61 = QtGui.QLabel(self.groupBox_4)
        self.label_61.setObjectName(_fromUtf8("label_61"))
        self.gridLayout_5.addWidget(self.label_61, 0, 8, 1, 1)
        self.label_64 = QtGui.QLabel(self.groupBox_4)
        self.label_64.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_64.setObjectName(_fromUtf8("label_64"))
        self.gridLayout_5.addWidget(self.label_64, 4, 3, 1, 1)
        self.label_67 = QtGui.QLabel(self.groupBox_4)
        self.label_67.setObjectName(_fromUtf8("label_67"))
        self.gridLayout_5.addWidget(self.label_67, 1, 5, 1, 1)
        self.label_68 = QtGui.QLabel(self.groupBox_4)
        self.label_68.setObjectName(_fromUtf8("label_68"))
        self.gridLayout_5.addWidget(self.label_68, 1, 8, 1, 1)
        self.label_56 = QtGui.QLabel(self.groupBox_4)
        self.label_56.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_56.setObjectName(_fromUtf8("label_56"))
        self.gridLayout_5.addWidget(self.label_56, 4, 6, 1, 1)
        self.label_55 = QtGui.QLabel(self.groupBox_4)
        self.label_55.setObjectName(_fromUtf8("label_55"))
        self.gridLayout_5.addWidget(self.label_55, 4, 5, 1, 1)
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        self.lattice_eos_a_txt = QtGui.QLineEdit(self.groupBox_4)
        self.lattice_eos_a_txt.setAutoFillBackground(False)
        self.lattice_eos_a_txt.setFrame(True)
        self.lattice_eos_a_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_eos_a_txt.setReadOnly(True)
        self.lattice_eos_a_txt.setObjectName(_fromUtf8("lattice_eos_a_txt"))
        self.horizontalLayout_2.addWidget(self.lattice_eos_a_txt)
        spacerItem3 = QtGui.QSpacerItem(20, 20, QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem3)
        self.gridLayout_5.addLayout(self.horizontalLayout_2, 1, 1, 1, 1)
        self.horizontalLayout_3 = QtGui.QHBoxLayout()
        self.horizontalLayout_3.setObjectName(_fromUtf8("horizontalLayout_3"))
        self.lattice_eos_b_txt = QtGui.QLineEdit(self.groupBox_4)
        self.lattice_eos_b_txt.setAutoFillBackground(False)
        self.lattice_eos_b_txt.setFrame(True)
        self.lattice_eos_b_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_eos_b_txt.setReadOnly(True)
        self.lattice_eos_b_txt.setObjectName(_fromUtf8("lattice_eos_b_txt"))
        self.horizontalLayout_3.addWidget(self.lattice_eos_b_txt)
        spacerItem4 = QtGui.QSpacerItem(20, 20, QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_3.addItem(spacerItem4)
        self.gridLayout_5.addLayout(self.horizontalLayout_3, 1, 4, 1, 1)
        self.horizontalLayout_6 = QtGui.QHBoxLayout()
        self.horizontalLayout_6.setObjectName(_fromUtf8("horizontalLayout_6"))
        self.lattice_eos_c_txt = QtGui.QLineEdit(self.groupBox_4)
        self.lattice_eos_c_txt.setAutoFillBackground(False)
        self.lattice_eos_c_txt.setFrame(True)
        self.lattice_eos_c_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lattice_eos_c_txt.setReadOnly(True)
        self.lattice_eos_c_txt.setObjectName(_fromUtf8("lattice_eos_c_txt"))
        self.horizontalLayout_6.addWidget(self.lattice_eos_c_txt)
        spacerItem5 = QtGui.QSpacerItem(20, 20, QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_6.addItem(spacerItem5)
        self.gridLayout_5.addLayout(self.horizontalLayout_6, 1, 7, 1, 1)
        self.verticalLayout_5.addLayout(self.gridLayout_5)
        self.verticalLayout_3.addWidget(self.groupBox_4)
        self.gridLayout_4 = QtGui.QGridLayout()
        self.gridLayout_4.setObjectName(_fromUtf8("gridLayout_4"))
        spacerItem6 = QtGui.QSpacerItem(197, 24, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.gridLayout_4.addItem(spacerItem6, 1, 0, 1, 1)
        self.groupBox_3 = QtGui.QGroupBox(JcpdsEditorWidget)
        self.groupBox_3.setObjectName(_fromUtf8("groupBox_3"))
        self.verticalLayout = QtGui.QVBoxLayout(self.groupBox_3)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.reflection_table = QtGui.QTableWidget(self.groupBox_3)
        self.reflection_table.setFrameShape(QtGui.QFrame.NoFrame)
        self.reflection_table.setFrameShadow(QtGui.QFrame.Raised)
        self.reflection_table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.reflection_table.setShowGrid(False)
        self.reflection_table.setGridStyle(QtCore.Qt.NoPen)
        self.reflection_table.setCornerButtonEnabled(False)
        self.reflection_table.setObjectName(_fromUtf8("reflection_table"))
        self.reflection_table.setColumnCount(8)
        self.reflection_table.setRowCount(0)
        item = QtGui.QTableWidgetItem()
        self.reflection_table.setHorizontalHeaderItem(0, item)
        item = QtGui.QTableWidgetItem()
        self.reflection_table.setHorizontalHeaderItem(1, item)
        item = QtGui.QTableWidgetItem()
        self.reflection_table.setHorizontalHeaderItem(2, item)
        item = QtGui.QTableWidgetItem()
        self.reflection_table.setHorizontalHeaderItem(3, item)
        item = QtGui.QTableWidgetItem()
        self.reflection_table.setHorizontalHeaderItem(4, item)
        item = QtGui.QTableWidgetItem()
        self.reflection_table.setHorizontalHeaderItem(5, item)
        item = QtGui.QTableWidgetItem()
        self.reflection_table.setHorizontalHeaderItem(6, item)
        item = QtGui.QTableWidgetItem()
        self.reflection_table.setHorizontalHeaderItem(7, item)
        self.reflection_table.horizontalHeader().setCascadingSectionResizes(False)
        self.reflection_table.horizontalHeader().setDefaultSectionSize(40)
        self.reflection_table.verticalHeader().setVisible(False)
        self.reflection_table.verticalHeader().setSortIndicatorShown(False)
        self.verticalLayout.addWidget(self.reflection_table)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.reflections_add_btn = QtGui.QPushButton(self.groupBox_3)
        self.reflections_add_btn.setObjectName(_fromUtf8("reflections_add_btn"))
        self.horizontalLayout.addWidget(self.reflections_add_btn)
        self.reflections_delete_btn = QtGui.QPushButton(self.groupBox_3)
        self.reflections_delete_btn.setObjectName(_fromUtf8("reflections_delete_btn"))
        self.horizontalLayout.addWidget(self.reflections_delete_btn)
        self.reflections_clear_btn = QtGui.QPushButton(self.groupBox_3)
        self.reflections_clear_btn.setObjectName(_fromUtf8("reflections_clear_btn"))
        self.horizontalLayout.addWidget(self.reflections_clear_btn)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.gridLayout_4.addWidget(self.groupBox_3, 0, 1, 2, 1)
        self.groupBox_2 = QtGui.QGroupBox(JcpdsEditorWidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy)
        self.groupBox_2.setMinimumSize(QtCore.QSize(200, 0))
        self.groupBox_2.setMaximumSize(QtCore.QSize(200, 16777215))
        self.groupBox_2.setObjectName(_fromUtf8("groupBox_2"))
        self.gridLayout_2 = QtGui.QGridLayout(self.groupBox_2)
        self.gridLayout_2.setObjectName(_fromUtf8("gridLayout_2"))
        self.label_20 = QtGui.QLabel(self.groupBox_2)
        self.label_20.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_20.setObjectName(_fromUtf8("label_20"))
        self.gridLayout_2.addWidget(self.label_20, 5, 0, 1, 1)
        self.label_21 = QtGui.QLabel(self.groupBox_2)
        self.label_21.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_21.setObjectName(_fromUtf8("label_21"))
        self.gridLayout_2.addWidget(self.label_21, 2, 0, 1, 1)
        self.eos_K_txt = QtGui.QLineEdit(self.groupBox_2)
        self.eos_K_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.eos_K_txt.setObjectName(_fromUtf8("eos_K_txt"))
        self.gridLayout_2.addWidget(self.eos_K_txt, 0, 1, 1, 1)
        self.eos_alphaT_txt = QtGui.QLineEdit(self.groupBox_2)
        self.eos_alphaT_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.eos_alphaT_txt.setObjectName(_fromUtf8("eos_alphaT_txt"))
        self.gridLayout_2.addWidget(self.eos_alphaT_txt, 2, 1, 1, 1)
        self.label_23 = QtGui.QLabel(self.groupBox_2)
        self.label_23.setObjectName(_fromUtf8("label_23"))
        self.gridLayout_2.addWidget(self.label_23, 0, 2, 1, 1)
        self.label_18 = QtGui.QLabel(self.groupBox_2)
        self.label_18.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_18.setObjectName(_fromUtf8("label_18"))
        self.gridLayout_2.addWidget(self.label_18, 1, 0, 1, 1)
        self.label_25 = QtGui.QLabel(self.groupBox_2)
        self.label_25.setObjectName(_fromUtf8("label_25"))
        self.gridLayout_2.addWidget(self.label_25, 3, 2, 1, 1)
        self.label_24 = QtGui.QLabel(self.groupBox_2)
        self.label_24.setObjectName(_fromUtf8("label_24"))
        self.gridLayout_2.addWidget(self.label_24, 2, 2, 1, 1)
        self.label_17 = QtGui.QLabel(self.groupBox_2)
        self.label_17.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_17.setObjectName(_fromUtf8("label_17"))
        self.gridLayout_2.addWidget(self.label_17, 0, 0, 1, 1)
        self.label_22 = QtGui.QLabel(self.groupBox_2)
        self.label_22.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_22.setObjectName(_fromUtf8("label_22"))
        self.gridLayout_2.addWidget(self.label_22, 3, 0, 1, 1)
        self.label_19 = QtGui.QLabel(self.groupBox_2)
        self.label_19.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_19.setObjectName(_fromUtf8("label_19"))
        self.gridLayout_2.addWidget(self.label_19, 4, 0, 1, 1)
        self.eos_dalphadT_txt = QtGui.QLineEdit(self.groupBox_2)
        self.eos_dalphadT_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.eos_dalphadT_txt.setObjectName(_fromUtf8("eos_dalphadT_txt"))
        self.gridLayout_2.addWidget(self.eos_dalphadT_txt, 3, 1, 1, 1)
        self.label_26 = QtGui.QLabel(self.groupBox_2)
        self.label_26.setObjectName(_fromUtf8("label_26"))
        self.gridLayout_2.addWidget(self.label_26, 4, 2, 1, 1)
        self.eos_dKpdT_txt = QtGui.QLineEdit(self.groupBox_2)
        self.eos_dKpdT_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.eos_dKpdT_txt.setObjectName(_fromUtf8("eos_dKpdT_txt"))
        self.gridLayout_2.addWidget(self.eos_dKpdT_txt, 5, 1, 1, 1)
        self.eos_dKdT_txt = QtGui.QLineEdit(self.groupBox_2)
        self.eos_dKdT_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.eos_dKdT_txt.setObjectName(_fromUtf8("eos_dKdT_txt"))
        self.gridLayout_2.addWidget(self.eos_dKdT_txt, 4, 1, 1, 1)
        self.label_27 = QtGui.QLabel(self.groupBox_2)
        self.label_27.setObjectName(_fromUtf8("label_27"))
        self.gridLayout_2.addWidget(self.label_27, 5, 2, 1, 1)
        self.eos_Kp_txt = QtGui.QLineEdit(self.groupBox_2)
        self.eos_Kp_txt.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.eos_Kp_txt.setObjectName(_fromUtf8("eos_Kp_txt"))
        self.gridLayout_2.addWidget(self.eos_Kp_txt, 1, 1, 1, 1)
        self.gridLayout_4.addWidget(self.groupBox_2, 0, 0, 1, 1)
        self.verticalLayout_3.addLayout(self.gridLayout_4)
        self.horizontalLayout_5 = QtGui.QHBoxLayout()
        self.horizontalLayout_5.setObjectName(_fromUtf8("horizontalLayout_5"))
        self.save_as_btn = QtGui.QPushButton(JcpdsEditorWidget)
        self.save_as_btn.setObjectName(_fromUtf8("save_as_btn"))
        self.horizontalLayout_5.addWidget(self.save_as_btn)
        self.reload_file_btn = QtGui.QPushButton(JcpdsEditorWidget)
        self.reload_file_btn.setObjectName(_fromUtf8("reload_file_btn"))
        self.horizontalLayout_5.addWidget(self.reload_file_btn)
        spacerItem7 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_5.addItem(spacerItem7)
        self.ok_btn = QtGui.QPushButton(JcpdsEditorWidget)
        self.ok_btn.setObjectName(_fromUtf8("ok_btn"))
        self.horizontalLayout_5.addWidget(self.ok_btn)
        self.cancel_btn = QtGui.QPushButton(JcpdsEditorWidget)
        self.cancel_btn.setObjectName(_fromUtf8("cancel_btn"))
        self.horizontalLayout_5.addWidget(self.cancel_btn)
        self.verticalLayout_3.addLayout(self.horizontalLayout_5)
        self.verticalLayout_3.setStretch(4, 1)

        self.retranslateUi(JcpdsEditorWidget)
        QtCore.QMetaObject.connectSlotsByName(JcpdsEditorWidget)

    def retranslateUi(self, JcpdsEditorWidget):
        JcpdsEditorWidget.setWindowTitle(_translate("JcpdsEditorWidget", "JCPDS - Editor", None))
        self.label_6.setText(_translate("JcpdsEditorWidget", "Filename:", None))
        self.label_8.setText(_translate("JcpdsEditorWidget", "Comment:", None))
        self.groupBox_4.setTitle(_translate("JcpdsEditorWidget", "Lattice Parameters", None))
        self.label_50.setText(_translate("JcpdsEditorWidget", "Symmetry: ", None))
        self.symmetry_cb.setItemText(0, _translate("JcpdsEditorWidget", "cubic", None))
        self.symmetry_cb.setItemText(1, _translate("JcpdsEditorWidget", "tetragonal", None))
        self.symmetry_cb.setItemText(2, _translate("JcpdsEditorWidget", "rhombohedral", None))
        self.symmetry_cb.setItemText(3, _translate("JcpdsEditorWidget", "orthorhombic", None))
        self.symmetry_cb.setItemText(4, _translate("JcpdsEditorWidget", "monoclinic", None))
        self.symmetry_cb.setItemText(5, _translate("JcpdsEditorWidget", "triclinic", None))
        self.label_66.setText(_translate("JcpdsEditorWidget", "Å", None))
        self.label_5.setText(_translate("JcpdsEditorWidget", "b:", None))
        self.label_4.setText(_translate("JcpdsEditorWidget", "a:", None))
        self.label_7.setText(_translate("JcpdsEditorWidget", "c:", None))
        self.label_65.setText(_translate("JcpdsEditorWidget", "Å<sup>3</sup>", None))
        self.label_60.setText(_translate("JcpdsEditorWidget", "°", None))
        self.label_59.setText(_translate("JcpdsEditorWidget", "°", None))
        self.lattice_angle_step_txt.setText(_translate("JcpdsEditorWidget", "1", None))
        self.label_54.setText(_translate("JcpdsEditorWidget", "Å", None))
        self.label_62.setText(_translate("JcpdsEditorWidget", "Å", None))
        self.label_43.setText(_translate("JcpdsEditorWidget", "c/a:", None))
        self.label.setText(_translate("JcpdsEditorWidget", "st:", None))
        self.label_57.setText(_translate("JcpdsEditorWidget", "c0:", None))
        self.lattice_length_step_txt.setText(_translate("JcpdsEditorWidget", "0.01", None))
        self.label_2.setText(_translate("JcpdsEditorWidget", "st:", None))
        self.label_44.setText(_translate("JcpdsEditorWidget", "α:", None))
        self.label_51.setText(_translate("JcpdsEditorWidget", "a/b:", None))
        self.label_3.setText(_translate("JcpdsEditorWidget", "st:", None))
        self.label_45.setText(_translate("JcpdsEditorWidget", "°", None))
        self.label_58.setText(_translate("JcpdsEditorWidget", "γ:", None))
        self.label_42.setText(_translate("JcpdsEditorWidget", "a0:", None))
        self.lattice_ratio_step_txt.setText(_translate("JcpdsEditorWidget", "0.01", None))
        self.label_52.setText(_translate("JcpdsEditorWidget", "c/b:", None))
        self.label_63.setText(_translate("JcpdsEditorWidget", "β:", None))
        self.label_53.setText(_translate("JcpdsEditorWidget", "b0:", None))
        self.label_61.setText(_translate("JcpdsEditorWidget", "Å", None))
        self.label_64.setText(_translate("JcpdsEditorWidget", "V0:", None))
        self.label_67.setText(_translate("JcpdsEditorWidget", "Å", None))
        self.label_68.setText(_translate("JcpdsEditorWidget", "Å", None))
        self.label_56.setText(_translate("JcpdsEditorWidget", "V:", None))
        self.label_55.setText(_translate("JcpdsEditorWidget", "Å<sup>3</sup>", None))
        self.groupBox_3.setTitle(_translate("JcpdsEditorWidget", "Reflections", None))
        self.reflection_table.setSortingEnabled(False)
        item = self.reflection_table.horizontalHeaderItem(0)
        item.setText(_translate("JcpdsEditorWidget", "h", None))
        item = self.reflection_table.horizontalHeaderItem(1)
        item.setText(_translate("JcpdsEditorWidget", "k", None))
        item = self.reflection_table.horizontalHeaderItem(2)
        item.setText(_translate("JcpdsEditorWidget", "l", None))
        item = self.reflection_table.horizontalHeaderItem(3)
        item.setText(_translate("JcpdsEditorWidget", "Intensity", None))
        item = self.reflection_table.horizontalHeaderItem(4)
        item.setText(_translate("JcpdsEditorWidget", "d0", None))
        item = self.reflection_table.horizontalHeaderItem(5)
        item.setText(_translate("JcpdsEditorWidget", "2θ_0", None))
        item = self.reflection_table.horizontalHeaderItem(6)
        item.setText(_translate("JcpdsEditorWidget", "d", None))
        item = self.reflection_table.horizontalHeaderItem(7)
        item.setText(_translate("JcpdsEditorWidget", "2θ", None))
        self.reflections_add_btn.setText(_translate("JcpdsEditorWidget", "Add", None))
        self.reflections_delete_btn.setText(_translate("JcpdsEditorWidget", "Delete", None))
        self.reflections_clear_btn.setText(_translate("JcpdsEditorWidget", "Clear", None))
        self.groupBox_2.setTitle(_translate("JcpdsEditorWidget", "Equation of State", None))
        self.label_20.setText(_translate("JcpdsEditorWidget", "dK\'/dT:", None))
        self.label_21.setText(_translate("JcpdsEditorWidget", "<html><head/><body><p>α<span style=\" vertical-align:sub;\">T</span>:</p></body></html>", None))
        self.label_23.setText(_translate("JcpdsEditorWidget", "GPa", None))
        self.label_18.setText(_translate("JcpdsEditorWidget", "K\':", None))
        self.label_25.setText(_translate("JcpdsEditorWidget", "1/K<sup>2</sup>", None))
        self.label_24.setText(_translate("JcpdsEditorWidget", "1/K", None))
        self.label_17.setText(_translate("JcpdsEditorWidget", "K:", None))
        self.label_22.setText(_translate("JcpdsEditorWidget", "dα<sub>T</sub>/dT:", None))
        self.label_19.setText(_translate("JcpdsEditorWidget", "dK/dT:", None))
        self.label_26.setText(_translate("JcpdsEditorWidget", "<html><head/><body><p>GPa/K</p></body></html>", None))
        self.label_27.setText(_translate("JcpdsEditorWidget", "<html><head/><body><p>1/K</p></body></html>", None))
        self.save_as_btn.setText(_translate("JcpdsEditorWidget", "Save As", None))
        self.reload_file_btn.setText(_translate("JcpdsEditorWidget", " Reload File", None))
        self.ok_btn.setText(_translate("JcpdsEditorWidget", "Ok", None))
        self.cancel_btn.setText(_translate("JcpdsEditorWidget", "Cancel", None))

