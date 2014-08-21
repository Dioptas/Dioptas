# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Jcpds.ui'
#
# Created: Thu Aug 21 12:33:39 2014
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
        JcpdsEditorWidget.resize(583, 600)
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
        self.filename_txt.setObjectName(_fromUtf8("filename_txt"))
        self.gridLayout_3.addWidget(self.filename_txt, 0, 1, 1, 1)
        self.label_8 = QtGui.QLabel(JcpdsEditorWidget)
        self.label_8.setObjectName(_fromUtf8("label_8"))
        self.gridLayout_3.addWidget(self.label_8, 1, 0, 1, 1)
        self.comments_txt = QtGui.QLineEdit(JcpdsEditorWidget)
        self.comments_txt.setObjectName(_fromUtf8("comments_txt"))
        self.gridLayout_3.addWidget(self.comments_txt, 1, 1, 1, 1)
        self.verticalLayout_3.addLayout(self.gridLayout_3)
        spacerItem = QtGui.QSpacerItem(0, 6, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout_3.addItem(spacerItem)
        self.groupBox = QtGui.QGroupBox(JcpdsEditorWidget)
        self.groupBox.setObjectName(_fromUtf8("groupBox"))
        self.verticalLayout_2 = QtGui.QVBoxLayout(self.groupBox)
        self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        self.label_42 = QtGui.QLabel(self.groupBox)
        self.label_42.setObjectName(_fromUtf8("label_42"))
        self.horizontalLayout_2.addWidget(self.label_42)
        self.symmetry_cb = QtGui.QComboBox(self.groupBox)
        self.symmetry_cb.setFocusPolicy(QtCore.Qt.NoFocus)
        self.symmetry_cb.setObjectName(_fromUtf8("symmetry_cb"))
        self.symmetry_cb.addItem(_fromUtf8(""))
        self.symmetry_cb.addItem(_fromUtf8(""))
        self.symmetry_cb.addItem(_fromUtf8(""))
        self.symmetry_cb.addItem(_fromUtf8(""))
        self.symmetry_cb.addItem(_fromUtf8(""))
        self.symmetry_cb.addItem(_fromUtf8(""))
        self.horizontalLayout_2.addWidget(self.symmetry_cb)
        spacerItem1 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem1)
        self.verticalLayout_2.addLayout(self.horizontalLayout_2)
        self.gridLayout = QtGui.QGridLayout()
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.label = QtGui.QLabel(self.groupBox)
        self.label.setObjectName(_fromUtf8("label"))
        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)
        self.lattice_a_txt = QtGui.QLineEdit(self.groupBox)
        self.lattice_a_txt.setObjectName(_fromUtf8("lattice_a_txt"))
        self.gridLayout.addWidget(self.lattice_a_txt, 0, 1, 1, 1)
        self.label_12 = QtGui.QLabel(self.groupBox)
        self.label_12.setObjectName(_fromUtf8("label_12"))
        self.gridLayout.addWidget(self.label_12, 0, 2, 1, 1)
        spacerItem2 = QtGui.QSpacerItem(10, 20, QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Minimum)
        self.gridLayout.addItem(spacerItem2, 0, 3, 1, 1)
        self.label_2 = QtGui.QLabel(self.groupBox)
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.gridLayout.addWidget(self.label_2, 0, 4, 1, 1)
        self.lattice_b_txt = QtGui.QLineEdit(self.groupBox)
        self.lattice_b_txt.setObjectName(_fromUtf8("lattice_b_txt"))
        self.gridLayout.addWidget(self.lattice_b_txt, 0, 5, 1, 1)
        self.label_13 = QtGui.QLabel(self.groupBox)
        self.label_13.setObjectName(_fromUtf8("label_13"))
        self.gridLayout.addWidget(self.label_13, 0, 6, 1, 1)
        spacerItem3 = QtGui.QSpacerItem(10, 20, QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Minimum)
        self.gridLayout.addItem(spacerItem3, 0, 7, 1, 1)
        self.label_4 = QtGui.QLabel(self.groupBox)
        self.label_4.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.label_4.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_4.setObjectName(_fromUtf8("label_4"))
        self.gridLayout.addWidget(self.label_4, 0, 8, 1, 1)
        self.lattice_c_txt = QtGui.QLineEdit(self.groupBox)
        self.lattice_c_txt.setObjectName(_fromUtf8("lattice_c_txt"))
        self.gridLayout.addWidget(self.lattice_c_txt, 0, 9, 1, 1)
        self.label_14 = QtGui.QLabel(self.groupBox)
        self.label_14.setObjectName(_fromUtf8("label_14"))
        self.gridLayout.addWidget(self.label_14, 0, 10, 1, 1)
        spacerItem4 = QtGui.QSpacerItem(10, 20, QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Minimum)
        self.gridLayout.addItem(spacerItem4, 0, 11, 1, 1)
        self.label_43 = QtGui.QLabel(self.groupBox)
        self.label_43.setObjectName(_fromUtf8("label_43"))
        self.gridLayout.addWidget(self.label_43, 0, 12, 1, 1)
        self.lattice_volume_txt = QtGui.QLineEdit(self.groupBox)
        self.lattice_volume_txt.setObjectName(_fromUtf8("lattice_volume_txt"))
        self.gridLayout.addWidget(self.lattice_volume_txt, 0, 13, 1, 1)
        self.label_44 = QtGui.QLabel(self.groupBox)
        self.label_44.setObjectName(_fromUtf8("label_44"))
        self.gridLayout.addWidget(self.label_44, 0, 14, 1, 1)
        self.label_3 = QtGui.QLabel(self.groupBox)
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.gridLayout.addWidget(self.label_3, 1, 0, 1, 1)
        self.lattice_alpha_txt = QtGui.QLineEdit(self.groupBox)
        self.lattice_alpha_txt.setObjectName(_fromUtf8("lattice_alpha_txt"))
        self.gridLayout.addWidget(self.lattice_alpha_txt, 1, 1, 1, 1)
        self.label_9 = QtGui.QLabel(self.groupBox)
        self.label_9.setObjectName(_fromUtf8("label_9"))
        self.gridLayout.addWidget(self.label_9, 1, 2, 1, 1)
        spacerItem5 = QtGui.QSpacerItem(10, 20, QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Minimum)
        self.gridLayout.addItem(spacerItem5, 1, 3, 1, 1)
        self.label_5 = QtGui.QLabel(self.groupBox)
        self.label_5.setObjectName(_fromUtf8("label_5"))
        self.gridLayout.addWidget(self.label_5, 1, 4, 1, 1)
        self.lattice_beta_txt = QtGui.QLineEdit(self.groupBox)
        self.lattice_beta_txt.setObjectName(_fromUtf8("lattice_beta_txt"))
        self.gridLayout.addWidget(self.lattice_beta_txt, 1, 5, 1, 1)
        self.label_10 = QtGui.QLabel(self.groupBox)
        self.label_10.setObjectName(_fromUtf8("label_10"))
        self.gridLayout.addWidget(self.label_10, 1, 6, 1, 1)
        spacerItem6 = QtGui.QSpacerItem(10, 20, QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Minimum)
        self.gridLayout.addItem(spacerItem6, 1, 7, 1, 1)
        self.label_7 = QtGui.QLabel(self.groupBox)
        self.label_7.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.label_7.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_7.setObjectName(_fromUtf8("label_7"))
        self.gridLayout.addWidget(self.label_7, 1, 8, 1, 1)
        self.lattice_gamma_txt = QtGui.QLineEdit(self.groupBox)
        self.lattice_gamma_txt.setObjectName(_fromUtf8("lattice_gamma_txt"))
        self.gridLayout.addWidget(self.lattice_gamma_txt, 1, 9, 1, 1)
        self.label_11 = QtGui.QLabel(self.groupBox)
        self.label_11.setObjectName(_fromUtf8("label_11"))
        self.gridLayout.addWidget(self.label_11, 1, 10, 1, 1)
        spacerItem7 = QtGui.QSpacerItem(138, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.gridLayout.addItem(spacerItem7, 1, 11, 1, 3)
        self.verticalLayout_2.addLayout(self.gridLayout)
        self.line = QtGui.QFrame(self.groupBox)
        self.line.setFrameShape(QtGui.QFrame.HLine)
        self.line.setFrameShadow(QtGui.QFrame.Sunken)
        self.line.setObjectName(_fromUtf8("line"))
        self.verticalLayout_2.addWidget(self.line)
        self.horizontalLayout_3 = QtGui.QHBoxLayout()
        self.horizontalLayout_3.setObjectName(_fromUtf8("horizontalLayout_3"))
        self.label_45 = QtGui.QLabel(self.groupBox)
        self.label_45.setObjectName(_fromUtf8("label_45"))
        self.horizontalLayout_3.addWidget(self.label_45)
        self.lattice_ab_txt = QtGui.QLineEdit(self.groupBox)
        self.lattice_ab_txt.setObjectName(_fromUtf8("lattice_ab_txt"))
        self.horizontalLayout_3.addWidget(self.lattice_ab_txt)
        spacerItem8 = QtGui.QSpacerItem(10, 20, QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_3.addItem(spacerItem8)
        self.label_15 = QtGui.QLabel(self.groupBox)
        self.label_15.setObjectName(_fromUtf8("label_15"))
        self.horizontalLayout_3.addWidget(self.label_15)
        self.lattice_ca_txt = QtGui.QLineEdit(self.groupBox)
        self.lattice_ca_txt.setObjectName(_fromUtf8("lattice_ca_txt"))
        self.horizontalLayout_3.addWidget(self.lattice_ca_txt)
        spacerItem9 = QtGui.QSpacerItem(10, 20, QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_3.addItem(spacerItem9)
        self.label_16 = QtGui.QLabel(self.groupBox)
        self.label_16.setObjectName(_fromUtf8("label_16"))
        self.horizontalLayout_3.addWidget(self.label_16)
        self.lattice_cb_txt = QtGui.QLineEdit(self.groupBox)
        self.lattice_cb_txt.setObjectName(_fromUtf8("lattice_cb_txt"))
        self.horizontalLayout_3.addWidget(self.lattice_cb_txt)
        spacerItem10 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_3.addItem(spacerItem10)
        spacerItem11 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_3.addItem(spacerItem11)
        self.verticalLayout_2.addLayout(self.horizontalLayout_3)
        self.verticalLayout_3.addWidget(self.groupBox)
        self.gridLayout_4 = QtGui.QGridLayout()
        self.gridLayout_4.setObjectName(_fromUtf8("gridLayout_4"))
        self.groupBox_2 = QtGui.QGroupBox(JcpdsEditorWidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy)
        self.groupBox_2.setMinimumSize(QtCore.QSize(220, 0))
        self.groupBox_2.setMaximumSize(QtCore.QSize(220, 16777215))
        self.groupBox_2.setObjectName(_fromUtf8("groupBox_2"))
        self.gridLayout_2 = QtGui.QGridLayout(self.groupBox_2)
        self.gridLayout_2.setObjectName(_fromUtf8("gridLayout_2"))
        self.label_25 = QtGui.QLabel(self.groupBox_2)
        self.label_25.setObjectName(_fromUtf8("label_25"))
        self.gridLayout_2.addWidget(self.label_25, 3, 2, 1, 1)
        self.label_26 = QtGui.QLabel(self.groupBox_2)
        self.label_26.setObjectName(_fromUtf8("label_26"))
        self.gridLayout_2.addWidget(self.label_26, 4, 2, 1, 1)
        self.label_18 = QtGui.QLabel(self.groupBox_2)
        self.label_18.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_18.setObjectName(_fromUtf8("label_18"))
        self.gridLayout_2.addWidget(self.label_18, 1, 0, 1, 1)
        self.label_20 = QtGui.QLabel(self.groupBox_2)
        self.label_20.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_20.setObjectName(_fromUtf8("label_20"))
        self.gridLayout_2.addWidget(self.label_20, 5, 0, 1, 1)
        self.label_19 = QtGui.QLabel(self.groupBox_2)
        self.label_19.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_19.setObjectName(_fromUtf8("label_19"))
        self.gridLayout_2.addWidget(self.label_19, 4, 0, 1, 1)
        self.eos_K_txt = QtGui.QLineEdit(self.groupBox_2)
        self.eos_K_txt.setObjectName(_fromUtf8("eos_K_txt"))
        self.gridLayout_2.addWidget(self.eos_K_txt, 0, 1, 1, 1)
        self.label_23 = QtGui.QLabel(self.groupBox_2)
        self.label_23.setObjectName(_fromUtf8("label_23"))
        self.gridLayout_2.addWidget(self.label_23, 0, 2, 1, 1)
        self.label_24 = QtGui.QLabel(self.groupBox_2)
        self.label_24.setObjectName(_fromUtf8("label_24"))
        self.gridLayout_2.addWidget(self.label_24, 2, 2, 1, 1)
        self.eos_dKdT_txt = QtGui.QLineEdit(self.groupBox_2)
        self.eos_dKdT_txt.setObjectName(_fromUtf8("eos_dKdT_txt"))
        self.gridLayout_2.addWidget(self.eos_dKdT_txt, 4, 1, 1, 1)
        self.label_21 = QtGui.QLabel(self.groupBox_2)
        self.label_21.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_21.setObjectName(_fromUtf8("label_21"))
        self.gridLayout_2.addWidget(self.label_21, 2, 0, 1, 1)
        self.eos_Kp_txt = QtGui.QLineEdit(self.groupBox_2)
        self.eos_Kp_txt.setObjectName(_fromUtf8("eos_Kp_txt"))
        self.gridLayout_2.addWidget(self.eos_Kp_txt, 1, 1, 1, 1)
        self.eos_alphaT_txt = QtGui.QLineEdit(self.groupBox_2)
        self.eos_alphaT_txt.setObjectName(_fromUtf8("eos_alphaT_txt"))
        self.gridLayout_2.addWidget(self.eos_alphaT_txt, 2, 1, 1, 1)
        self.eos_dKpdT_txt = QtGui.QLineEdit(self.groupBox_2)
        self.eos_dKpdT_txt.setObjectName(_fromUtf8("eos_dKpdT_txt"))
        self.gridLayout_2.addWidget(self.eos_dKpdT_txt, 5, 1, 1, 1)
        self.label_17 = QtGui.QLabel(self.groupBox_2)
        self.label_17.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_17.setObjectName(_fromUtf8("label_17"))
        self.gridLayout_2.addWidget(self.label_17, 0, 0, 1, 1)
        self.label_22 = QtGui.QLabel(self.groupBox_2)
        self.label_22.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_22.setObjectName(_fromUtf8("label_22"))
        self.gridLayout_2.addWidget(self.label_22, 3, 0, 1, 1)
        self.label_27 = QtGui.QLabel(self.groupBox_2)
        self.label_27.setObjectName(_fromUtf8("label_27"))
        self.gridLayout_2.addWidget(self.label_27, 5, 2, 1, 1)
        self.eos_dalphadT_txt = QtGui.QLineEdit(self.groupBox_2)
        self.eos_dalphadT_txt.setObjectName(_fromUtf8("eos_dalphadT_txt"))
        self.gridLayout_2.addWidget(self.eos_dalphadT_txt, 3, 1, 1, 1)
        self.gridLayout_4.addWidget(self.groupBox_2, 0, 0, 1, 1)
        self.groupBox_3 = QtGui.QGroupBox(JcpdsEditorWidget)
        self.groupBox_3.setObjectName(_fromUtf8("groupBox_3"))
        self.verticalLayout = QtGui.QVBoxLayout(self.groupBox_3)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
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
        self.reflaction_table = QtGui.QTableWidget(self.groupBox_3)
        self.reflaction_table.setFrameShape(QtGui.QFrame.NoFrame)
        self.reflaction_table.setFrameShadow(QtGui.QFrame.Raised)
        self.reflaction_table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.reflaction_table.setGridStyle(QtCore.Qt.NoPen)
        self.reflaction_table.setObjectName(_fromUtf8("reflaction_table"))
        self.reflaction_table.setColumnCount(5)
        self.reflaction_table.setRowCount(9)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setVerticalHeaderItem(0, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setVerticalHeaderItem(1, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setVerticalHeaderItem(2, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setVerticalHeaderItem(3, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setVerticalHeaderItem(4, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setVerticalHeaderItem(5, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setVerticalHeaderItem(6, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setVerticalHeaderItem(7, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setVerticalHeaderItem(8, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setHorizontalHeaderItem(0, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setHorizontalHeaderItem(1, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setHorizontalHeaderItem(2, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setHorizontalHeaderItem(3, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setHorizontalHeaderItem(4, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setItem(0, 0, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setItem(0, 1, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setItem(0, 2, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setItem(1, 0, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setItem(1, 1, item)
        item = QtGui.QTableWidgetItem()
        self.reflaction_table.setItem(1, 2, item)
        self.reflaction_table.horizontalHeader().setCascadingSectionResizes(True)
        self.reflaction_table.horizontalHeader().setDefaultSectionSize(40)
        self.reflaction_table.verticalHeader().setVisible(False)
        self.verticalLayout.addWidget(self.reflaction_table)
        self.gridLayout_4.addWidget(self.groupBox_3, 0, 1, 2, 1)
        spacerItem12 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.gridLayout_4.addItem(spacerItem12, 1, 0, 1, 1)
        self.verticalLayout_3.addLayout(self.gridLayout_4)
        self.horizontalLayout_5 = QtGui.QHBoxLayout()
        self.horizontalLayout_5.setObjectName(_fromUtf8("horizontalLayout_5"))
        self.save_btn = QtGui.QPushButton(JcpdsEditorWidget)
        self.save_btn.setObjectName(_fromUtf8("save_btn"))
        self.horizontalLayout_5.addWidget(self.save_btn)
        self.save_as_btn = QtGui.QPushButton(JcpdsEditorWidget)
        self.save_as_btn.setObjectName(_fromUtf8("save_as_btn"))
        self.horizontalLayout_5.addWidget(self.save_as_btn)
        spacerItem13 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_5.addItem(spacerItem13)
        self.ok_btn = QtGui.QPushButton(JcpdsEditorWidget)
        self.ok_btn.setObjectName(_fromUtf8("ok_btn"))
        self.horizontalLayout_5.addWidget(self.ok_btn)
        self.cancel_btn = QtGui.QPushButton(JcpdsEditorWidget)
        self.cancel_btn.setObjectName(_fromUtf8("cancel_btn"))
        self.horizontalLayout_5.addWidget(self.cancel_btn)
        self.verticalLayout_3.addLayout(self.horizontalLayout_5)
        self.verticalLayout_3.setStretch(3, 1)

        self.retranslateUi(JcpdsEditorWidget)
        QtCore.QMetaObject.connectSlotsByName(JcpdsEditorWidget)

    def retranslateUi(self, JcpdsEditorWidget):
        JcpdsEditorWidget.setWindowTitle(_translate("JcpdsEditorWidget", "Form", None))
        self.label_6.setText(_translate("JcpdsEditorWidget", "Filename:", None))
        self.label_8.setText(_translate("JcpdsEditorWidget", "Comment:", None))
        self.groupBox.setTitle(_translate("JcpdsEditorWidget", "Lattice Parameters", None))
        self.label_42.setText(_translate("JcpdsEditorWidget", "Symmetry: ", None))
        self.symmetry_cb.setItemText(0, _translate("JcpdsEditorWidget", "cubic", None))
        self.symmetry_cb.setItemText(1, _translate("JcpdsEditorWidget", "tetragonal", None))
        self.symmetry_cb.setItemText(2, _translate("JcpdsEditorWidget", "rhombohedral", None))
        self.symmetry_cb.setItemText(3, _translate("JcpdsEditorWidget", "orthorhombic", None))
        self.symmetry_cb.setItemText(4, _translate("JcpdsEditorWidget", "monoclinic", None))
        self.symmetry_cb.setItemText(5, _translate("JcpdsEditorWidget", "triclinic", None))
        self.label.setText(_translate("JcpdsEditorWidget", "a:", None))
        self.label_12.setText(_translate("JcpdsEditorWidget", "Å", None))
        self.label_2.setText(_translate("JcpdsEditorWidget", "b:", None))
        self.label_13.setText(_translate("JcpdsEditorWidget", "Å", None))
        self.label_4.setText(_translate("JcpdsEditorWidget", "c:", None))
        self.label_14.setText(_translate("JcpdsEditorWidget", "Å", None))
        self.label_43.setText(_translate("JcpdsEditorWidget", "V:", None))
        self.label_44.setText(_translate("JcpdsEditorWidget", "Å<sup>3</sup>", None))
        self.label_3.setText(_translate("JcpdsEditorWidget", "α:", None))
        self.label_9.setText(_translate("JcpdsEditorWidget", "°", None))
        self.label_5.setText(_translate("JcpdsEditorWidget", "β:", None))
        self.label_10.setText(_translate("JcpdsEditorWidget", "°", None))
        self.label_7.setText(_translate("JcpdsEditorWidget", "γ:", None))
        self.label_11.setText(_translate("JcpdsEditorWidget", "°", None))
        self.label_45.setText(_translate("JcpdsEditorWidget", "a/b:", None))
        self.label_15.setText(_translate("JcpdsEditorWidget", "c/a:", None))
        self.label_16.setText(_translate("JcpdsEditorWidget", "c/b:", None))
        self.groupBox_2.setTitle(_translate("JcpdsEditorWidget", "Equation of State", None))
        self.label_25.setText(_translate("JcpdsEditorWidget", "1/K<sup>2</sup>", None))
        self.label_26.setText(_translate("JcpdsEditorWidget", "<html><head/><body><p>GPa/K</p></body></html>", None))
        self.label_18.setText(_translate("JcpdsEditorWidget", "K\':", None))
        self.label_20.setText(_translate("JcpdsEditorWidget", "dK\'/dT:", None))
        self.label_19.setText(_translate("JcpdsEditorWidget", "dK/dT:", None))
        self.label_23.setText(_translate("JcpdsEditorWidget", "GPa", None))
        self.label_24.setText(_translate("JcpdsEditorWidget", "1/K", None))
        self.label_21.setText(_translate("JcpdsEditorWidget", "<html><head/><body><p>α<span style=\" vertical-align:sub;\">T</span>:</p></body></html>", None))
        self.label_17.setText(_translate("JcpdsEditorWidget", "K:", None))
        self.label_22.setText(_translate("JcpdsEditorWidget", "dα<sub>T</sub>/dT:", None))
        self.label_27.setText(_translate("JcpdsEditorWidget", "<html><head/><body><p>1/K</p></body></html>", None))
        self.groupBox_3.setTitle(_translate("JcpdsEditorWidget", "Reflections", None))
        self.reflections_add_btn.setText(_translate("JcpdsEditorWidget", "Add", None))
        self.reflections_delete_btn.setText(_translate("JcpdsEditorWidget", "Delete", None))
        self.reflections_clear_btn.setText(_translate("JcpdsEditorWidget", "Clear", None))
        self.reflaction_table.setSortingEnabled(True)
        item = self.reflaction_table.verticalHeaderItem(0)
        item.setText(_translate("JcpdsEditorWidget", "New Row", None))
        item = self.reflaction_table.verticalHeaderItem(1)
        item.setText(_translate("JcpdsEditorWidget", "New Row", None))
        item = self.reflaction_table.verticalHeaderItem(2)
        item.setText(_translate("JcpdsEditorWidget", "New Row", None))
        item = self.reflaction_table.verticalHeaderItem(3)
        item.setText(_translate("JcpdsEditorWidget", "New Row", None))
        item = self.reflaction_table.verticalHeaderItem(4)
        item.setText(_translate("JcpdsEditorWidget", "New Row", None))
        item = self.reflaction_table.verticalHeaderItem(5)
        item.setText(_translate("JcpdsEditorWidget", "New Row", None))
        item = self.reflaction_table.verticalHeaderItem(6)
        item.setText(_translate("JcpdsEditorWidget", "New Row", None))
        item = self.reflaction_table.verticalHeaderItem(7)
        item.setText(_translate("JcpdsEditorWidget", "New Row", None))
        item = self.reflaction_table.verticalHeaderItem(8)
        item.setText(_translate("JcpdsEditorWidget", "New Row", None))
        item = self.reflaction_table.horizontalHeaderItem(0)
        item.setText(_translate("JcpdsEditorWidget", "h", None))
        item = self.reflaction_table.horizontalHeaderItem(1)
        item.setText(_translate("JcpdsEditorWidget", "k", None))
        item = self.reflaction_table.horizontalHeaderItem(2)
        item.setText(_translate("JcpdsEditorWidget", "l", None))
        item = self.reflaction_table.horizontalHeaderItem(3)
        item.setText(_translate("JcpdsEditorWidget", "d", None))
        item = self.reflaction_table.horizontalHeaderItem(4)
        item.setText(_translate("JcpdsEditorWidget", "I", None))
        __sortingEnabled = self.reflaction_table.isSortingEnabled()
        self.reflaction_table.setSortingEnabled(False)
        item = self.reflaction_table.item(0, 0)
        item.setText(_translate("JcpdsEditorWidget", "1", None))
        item = self.reflaction_table.item(0, 1)
        item.setText(_translate("JcpdsEditorWidget", "2", None))
        item = self.reflaction_table.item(0, 2)
        item.setText(_translate("JcpdsEditorWidget", "3", None))
        item = self.reflaction_table.item(1, 0)
        item.setText(_translate("JcpdsEditorWidget", "2", None))
        item = self.reflaction_table.item(1, 1)
        item.setText(_translate("JcpdsEditorWidget", "3", None))
        item = self.reflaction_table.item(1, 2)
        item.setText(_translate("JcpdsEditorWidget", "4", None))
        self.reflaction_table.setSortingEnabled(__sortingEnabled)
        self.save_btn.setText(_translate("JcpdsEditorWidget", "Save", None))
        self.save_as_btn.setText(_translate("JcpdsEditorWidget", "Save As", None))
        self.ok_btn.setText(_translate("JcpdsEditorWidget", "Ok", None))
        self.cancel_btn.setText(_translate("JcpdsEditorWidget", "Cancel", None))

