# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'XRS_Main.ui'
#
# Created: Tue Nov 19 12:41:18 2013
#      by: PyQt4 UI code generator 4.9.6
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

class Ui_XRS_Main(object):
    def setupUi(self, XRS_Main):
        XRS_Main.setObjectName(_fromUtf8("XRS_Main"))
        XRS_Main.resize(1107, 668)
        self.horizontalLayou = QtGui.QHBoxLayout(XRS_Main)
        self.horizontalLayou.setObjectName(_fromUtf8("horizontalLayou"))
        self.verticalLayout_2 = QtGui.QVBoxLayout()
        self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
        self.image_frame = QtGui.QFrame(XRS_Main)
        self.image_frame.setFrameShape(QtGui.QFrame.StyledPanel)
        self.image_frame.setFrameShadow(QtGui.QFrame.Raised)
        self.image_frame.setObjectName(_fromUtf8("image_frame"))
        self.verticalLayout_2.addWidget(self.image_frame)
        self.widget = QtGui.QWidget(XRS_Main)
        self.widget.setMaximumSize(QtCore.QSize(16777215, 100))
        self.widget.setObjectName(_fromUtf8("widget"))
        self.verticalLayout = QtGui.QVBoxLayout(self.widget)
        self.verticalLayout.setMargin(0)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.load_image_btn = QtGui.QPushButton(self.widget)
        self.load_image_btn.setObjectName(_fromUtf8("load_image_btn"))
        self.horizontalLayout.addWidget(self.load_image_btn)
        self.load_previous_image_btn = QtGui.QPushButton(self.widget)
        self.load_previous_image_btn.setObjectName(_fromUtf8("load_previous_image_btn"))
        self.horizontalLayout.addWidget(self.load_previous_image_btn)
        self.load_next_image_btn = QtGui.QPushButton(self.widget)
        self.load_next_image_btn.setObjectName(_fromUtf8("load_next_image_btn"))
        self.horizontalLayout.addWidget(self.load_next_image_btn)
        self.integrate_btn = QtGui.QPushButton(self.widget)
        self.integrate_btn.setObjectName(_fromUtf8("integrate_btn"))
        self.horizontalLayout.addWidget(self.integrate_btn)
        self.auto_integrate_btn = QtGui.QCheckBox(self.widget)
        self.auto_integrate_btn.setObjectName(_fromUtf8("auto_integrate_btn"))
        self.horizontalLayout.addWidget(self.auto_integrate_btn)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.image_file_name_lbl = QtGui.QLabel(self.widget)
        self.image_file_name_lbl.setObjectName(_fromUtf8("image_file_name_lbl"))
        self.verticalLayout.addWidget(self.image_file_name_lbl)
        self.verticalLayout_2.addWidget(self.widget)
        self.horizontalLayou.addLayout(self.verticalLayout_2)
        self.verticalLayout_3 = QtGui.QVBoxLayout()
        self.verticalLayout_3.setObjectName(_fromUtf8("verticalLayout_3"))
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        spacerItem = QtGui.QSpacerItem(20, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem)
        self.label_2 = QtGui.QLabel(XRS_Main)
        font = QtGui.QFont()
        font.setFamily(_fromUtf8("Calibri"))
        font.setPointSize(36)
        font.setBold(True)
        font.setItalic(True)
        font.setWeight(75)
        self.label_2.setFont(font)
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.horizontalLayout_2.addWidget(self.label_2)
        self.verticalLayout_3.addLayout(self.horizontalLayout_2)
        self.graph_frame = QtGui.QFrame(XRS_Main)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(5)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.graph_frame.sizePolicy().hasHeightForWidth())
        self.graph_frame.setSizePolicy(sizePolicy)
        self.graph_frame.setObjectName(_fromUtf8("graph_frame"))
        self.verticalLayout_3.addWidget(self.graph_frame)
        self.bottom_lbl = QtGui.QLabel(XRS_Main)
        self.bottom_lbl.setObjectName(_fromUtf8("bottom_lbl"))
        self.verticalLayout_3.addWidget(self.bottom_lbl)
        self.horizontalLayou.addLayout(self.verticalLayout_3)

        self.retranslateUi(XRS_Main)
        QtCore.QMetaObject.connectSlotsByName(XRS_Main)

    def retranslateUi(self, XRS_Main):
        XRS_Main.setWindowTitle(_translate("XRS_Main", "Form", None))
        self.load_image_btn.setText(_translate("XRS_Main", "Load", None))
        self.load_previous_image_btn.setText(_translate("XRS_Main", "<", None))
        self.load_next_image_btn.setText(_translate("XRS_Main", ">", None))
        self.integrate_btn.setText(_translate("XRS_Main", "Integrate", None))
        self.auto_integrate_btn.setText(_translate("XRS_Main", "auto", None))
        self.image_file_name_lbl.setText(_translate("XRS_Main", "TextLabel", None))
        self.label_2.setText(_translate("XRS_Main", "X-ray Suite", None))
        self.bottom_lbl.setText(_translate("XRS_Main", "TextLabel", None))

