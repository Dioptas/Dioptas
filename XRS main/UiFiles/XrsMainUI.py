# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'XrsMain.ui'
#
# Created: Thu Apr 24 13:55:51 2014
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

class Ui_XRS_widget(object):
    def setupUi(self, XRS_widget):
        XRS_widget.setObjectName(_fromUtf8("XRS_widget"))
        XRS_widget.resize(739, 353)
        self.horizontalLayout_3 = QtGui.QHBoxLayout(XRS_widget)
        self.horizontalLayout_3.setObjectName(_fromUtf8("horizontalLayout_3"))
        self.splitter = QtGui.QSplitter(XRS_widget)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setHandleWidth(7)
        self.splitter.setObjectName(_fromUtf8("splitter"))
        self.layoutWidget = QtGui.QWidget(self.splitter)
        self.layoutWidget.setObjectName(_fromUtf8("layoutWidget"))
        self.verticalLayout = QtGui.QVBoxLayout(self.layoutWidget)
        self.verticalLayout.setMargin(0)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.img_pg_layout = GraphicsLayoutWidget(self.layoutWidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.img_pg_layout.sizePolicy().hasHeightForWidth())
        self.img_pg_layout.setSizePolicy(sizePolicy)
        self.img_pg_layout.setMinimumSize(QtCore.QSize(200, 0))
        self.img_pg_layout.setBaseSize(QtCore.QSize(300, 0))
        self.img_pg_layout.setFrameShape(QtGui.QFrame.StyledPanel)
        self.img_pg_layout.setObjectName(_fromUtf8("img_pg_layout"))
        self.verticalLayout.addWidget(self.img_pg_layout)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.filename_lbl = QtGui.QLabel(self.layoutWidget)
        self.filename_lbl.setObjectName(_fromUtf8("filename_lbl"))
        self.horizontalLayout.addWidget(self.filename_lbl)
        spacerItem = QtGui.QSpacerItem(10, 17, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.pos_lbl = QtGui.QLabel(self.layoutWidget)
        self.pos_lbl.setObjectName(_fromUtf8("pos_lbl"))
        self.horizontalLayout.addWidget(self.pos_lbl)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        self.load_file_btn = QtGui.QPushButton(self.layoutWidget)
        self.load_file_btn.setObjectName(_fromUtf8("load_file_btn"))
        self.horizontalLayout_2.addWidget(self.load_file_btn)
        self.previous_file_btn = QtGui.QPushButton(self.layoutWidget)
        self.previous_file_btn.setObjectName(_fromUtf8("previous_file_btn"))
        self.horizontalLayout_2.addWidget(self.previous_file_btn)
        self.next_file_btn = QtGui.QPushButton(self.layoutWidget)
        self.next_file_btn.setObjectName(_fromUtf8("next_file_btn"))
        self.horizontalLayout_2.addWidget(self.next_file_btn)
        self.autoproces_cb = QtGui.QCheckBox(self.layoutWidget)
        self.autoproces_cb.setObjectName(_fromUtf8("autoproces_cb"))
        self.horizontalLayout_2.addWidget(self.autoproces_cb)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.plot = PlotWidget(self.splitter)
        self.plot.setSizeIncrement(QtCore.QSize(1, 2))
        self.plot.setBaseSize(QtCore.QSize(300, 300))
        self.plot.setFrameShape(QtGui.QFrame.StyledPanel)
        self.plot.setFrameShadow(QtGui.QFrame.Sunken)
        self.plot.setObjectName(_fromUtf8("plot"))
        self.horizontalLayout_3.addWidget(self.splitter)

        self.retranslateUi(XRS_widget)
        QtCore.QMetaObject.connectSlotsByName(XRS_widget)

    def retranslateUi(self, XRS_widget):
        XRS_widget.setWindowTitle(_translate("XRS_widget", "Form", None))
        self.filename_lbl.setText(_translate("XRS_widget", "filename", None))
        self.pos_lbl.setText(_translate("XRS_widget", "Pos", None))
        self.load_file_btn.setText(_translate("XRS_widget", "Load", None))
        self.previous_file_btn.setText(_translate("XRS_widget", "<", None))
        self.next_file_btn.setText(_translate("XRS_widget", ">", None))
        self.autoproces_cb.setText(_translate("XRS_widget", "autoprocess", None))

from pyqtgraph import GraphicsLayoutWidget, PlotWidget
