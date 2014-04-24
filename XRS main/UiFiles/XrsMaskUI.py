# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'XrsMask.ui'
#
# Created: Thu Apr 24 12:53:12 2014
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

class Ui_xrs_mask_widget(object):
    def setupUi(self, xrs_mask_widget):
        xrs_mask_widget.setObjectName(_fromUtf8("xrs_mask_widget"))
        xrs_mask_widget.resize(801, 519)
        self.horizontalLayout_2 = QtGui.QHBoxLayout(xrs_mask_widget)
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        self.splitter = QtGui.QSplitter(xrs_mask_widget)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName(_fromUtf8("splitter"))
        self.widget = QtGui.QWidget(self.splitter)
        self.widget.setObjectName(_fromUtf8("widget"))
        self.verticalLayout = QtGui.QVBoxLayout(self.widget)
        self.verticalLayout.setMargin(0)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.graphicsView = QtGui.QGraphicsView(self.widget)
        self.graphicsView.setObjectName(_fromUtf8("graphicsView"))
        self.verticalLayout.addWidget(self.graphicsView)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        spacerItem = QtGui.QSpacerItem(118, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.label = QtGui.QLabel(self.widget)
        self.label.setObjectName(_fromUtf8("label"))
        self.horizontalLayout.addWidget(self.label)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.widget1 = QtGui.QWidget(self.splitter)
        self.widget1.setObjectName(_fromUtf8("widget1"))
        self.gridLayout = QtGui.QGridLayout(self.widget1)
        self.gridLayout.setMargin(0)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.pushButton = QtGui.QPushButton(self.widget1)
        self.pushButton.setObjectName(_fromUtf8("pushButton"))
        self.gridLayout.addWidget(self.pushButton, 0, 0, 1, 1)
        self.pushButton_3 = QtGui.QPushButton(self.widget1)
        self.pushButton_3.setObjectName(_fromUtf8("pushButton_3"))
        self.gridLayout.addWidget(self.pushButton_3, 0, 1, 1, 2)
        self.pushButton_4 = QtGui.QPushButton(self.widget1)
        self.pushButton_4.setObjectName(_fromUtf8("pushButton_4"))
        self.gridLayout.addWidget(self.pushButton_4, 1, 0, 1, 1)
        self.pushButton_2 = QtGui.QPushButton(self.widget1)
        self.pushButton_2.setObjectName(_fromUtf8("pushButton_2"))
        self.gridLayout.addWidget(self.pushButton_2, 1, 1, 1, 2)
        self.pushButton_5 = QtGui.QPushButton(self.widget1)
        self.pushButton_5.setObjectName(_fromUtf8("pushButton_5"))
        self.gridLayout.addWidget(self.pushButton_5, 2, 0, 1, 1)
        self.spinBox = QtGui.QSpinBox(self.widget1)
        self.spinBox.setObjectName(_fromUtf8("spinBox"))
        self.gridLayout.addWidget(self.spinBox, 2, 2, 1, 1)
        self.pushButton_6 = QtGui.QPushButton(self.widget1)
        self.pushButton_6.setObjectName(_fromUtf8("pushButton_6"))
        self.gridLayout.addWidget(self.pushButton_6, 3, 0, 1, 1)
        self.lineEdit = QtGui.QLineEdit(self.widget1)
        self.lineEdit.setObjectName(_fromUtf8("lineEdit"))
        self.gridLayout.addWidget(self.lineEdit, 3, 2, 1, 1)
        self.pushButton_10 = QtGui.QPushButton(self.widget1)
        self.pushButton_10.setObjectName(_fromUtf8("pushButton_10"))
        self.gridLayout.addWidget(self.pushButton_10, 4, 0, 1, 1)
        self.lineEdit_2 = QtGui.QLineEdit(self.widget1)
        self.lineEdit_2.setObjectName(_fromUtf8("lineEdit_2"))
        self.gridLayout.addWidget(self.lineEdit_2, 4, 2, 1, 1)
        self.pushButton_9 = QtGui.QPushButton(self.widget1)
        self.pushButton_9.setObjectName(_fromUtf8("pushButton_9"))
        self.gridLayout.addWidget(self.pushButton_9, 5, 0, 1, 3)
        spacerItem1 = QtGui.QSpacerItem(228, 224, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.gridLayout.addItem(spacerItem1, 6, 0, 1, 3)
        self.pushButton_7 = QtGui.QPushButton(self.widget1)
        self.pushButton_7.setObjectName(_fromUtf8("pushButton_7"))
        self.gridLayout.addWidget(self.pushButton_7, 7, 0, 1, 2)
        self.pushButton_8 = QtGui.QPushButton(self.widget1)
        self.pushButton_8.setObjectName(_fromUtf8("pushButton_8"))
        self.gridLayout.addWidget(self.pushButton_8, 7, 2, 1, 1)
        self.horizontalLayout_2.addWidget(self.splitter)

        self.retranslateUi(xrs_mask_widget)
        QtCore.QMetaObject.connectSlotsByName(xrs_mask_widget)

    def retranslateUi(self, xrs_mask_widget):
        xrs_mask_widget.setWindowTitle(_translate("xrs_mask_widget", "Form", None))
        self.label.setText(_translate("xrs_mask_widget", "TextLabel", None))
        self.pushButton.setText(_translate("xrs_mask_widget", "Circle", None))
        self.pushButton_3.setText(_translate("xrs_mask_widget", "Ellipse", None))
        self.pushButton_4.setText(_translate("xrs_mask_widget", "Rectangle", None))
        self.pushButton_2.setText(_translate("xrs_mask_widget", "Polygon", None))
        self.pushButton_5.setText(_translate("xrs_mask_widget", "Point", None))
        self.pushButton_6.setText(_translate("xrs_mask_widget", "Above Thresh", None))
        self.pushButton_10.setText(_translate("xrs_mask_widget", "Below Thresh", None))
        self.pushButton_9.setText(_translate("xrs_mask_widget", "Cosmic Removal", None))
        self.pushButton_7.setText(_translate("xrs_mask_widget", "Back", None))
        self.pushButton_8.setText(_translate("xrs_mask_widget", "Forward", None))

