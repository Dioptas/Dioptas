# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'XrsMask.ui'
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

class Ui_xrs_mask_widget(object):
    def setupUi(self, xrs_mask_widget):
        xrs_mask_widget.setObjectName(_fromUtf8("xrs_mask_widget"))
        xrs_mask_widget.resize(801, 519)
        self.horizontalLayout_2 = QtGui.QHBoxLayout(xrs_mask_widget)
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        self.splitter = QtGui.QSplitter(xrs_mask_widget)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName(_fromUtf8("splitter"))
        self.layoutWidget = QtGui.QWidget(self.splitter)
        self.layoutWidget.setObjectName(_fromUtf8("layoutWidget"))
        self.verticalLayout = QtGui.QVBoxLayout(self.layoutWidget)
        self.verticalLayout.setMargin(0)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.img_pg_layout = GraphicsLayoutWidget(self.layoutWidget)
        self.img_pg_layout.setObjectName(_fromUtf8("img_pg_layout"))
        self.verticalLayout.addWidget(self.img_pg_layout)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        spacerItem = QtGui.QSpacerItem(118, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.pos_lbl = QtGui.QLabel(self.layoutWidget)
        self.pos_lbl.setObjectName(_fromUtf8("pos_lbl"))
        self.horizontalLayout.addWidget(self.pos_lbl)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.widget = QtGui.QWidget(self.splitter)
        self.widget.setObjectName(_fromUtf8("widget"))
        self.gridLayout = QtGui.QGridLayout(self.widget)
        self.gridLayout.setMargin(0)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.circle_btn = QtGui.QPushButton(self.widget)
        self.circle_btn.setCheckable(True)
        self.circle_btn.setObjectName(_fromUtf8("circle_btn"))
        self.gridLayout.addWidget(self.circle_btn, 0, 0, 1, 1)
        self.ellipse_btn = QtGui.QPushButton(self.widget)
        self.ellipse_btn.setCheckable(True)
        self.ellipse_btn.setObjectName(_fromUtf8("ellipse_btn"))
        self.gridLayout.addWidget(self.ellipse_btn, 0, 1, 1, 2)
        self.rectangle_btn = QtGui.QPushButton(self.widget)
        self.rectangle_btn.setCheckable(True)
        self.rectangle_btn.setObjectName(_fromUtf8("rectangle_btn"))
        self.gridLayout.addWidget(self.rectangle_btn, 1, 0, 1, 1)
        self.polygon_btn = QtGui.QPushButton(self.widget)
        self.polygon_btn.setCheckable(True)
        self.polygon_btn.setObjectName(_fromUtf8("polygon_btn"))
        self.gridLayout.addWidget(self.polygon_btn, 1, 1, 1, 2)
        self.point_btn = QtGui.QPushButton(self.widget)
        self.point_btn.setCheckable(True)
        self.point_btn.setObjectName(_fromUtf8("point_btn"))
        self.gridLayout.addWidget(self.point_btn, 2, 0, 1, 1)
        self.spinBox = QtGui.QSpinBox(self.widget)
        self.spinBox.setObjectName(_fromUtf8("spinBox"))
        self.gridLayout.addWidget(self.spinBox, 2, 2, 1, 1)
        self.above_thresh_btn = QtGui.QPushButton(self.widget)
        self.above_thresh_btn.setObjectName(_fromUtf8("above_thresh_btn"))
        self.gridLayout.addWidget(self.above_thresh_btn, 3, 0, 1, 1)
        self.above_thresh_txt = QtGui.QLineEdit(self.widget)
        self.above_thresh_txt.setObjectName(_fromUtf8("above_thresh_txt"))
        self.gridLayout.addWidget(self.above_thresh_txt, 3, 2, 1, 1)
        self.below_thresh_btn = QtGui.QPushButton(self.widget)
        self.below_thresh_btn.setObjectName(_fromUtf8("below_thresh_btn"))
        self.gridLayout.addWidget(self.below_thresh_btn, 4, 0, 1, 1)
        self.below_thresh_txt = QtGui.QLineEdit(self.widget)
        self.below_thresh_txt.setObjectName(_fromUtf8("below_thresh_txt"))
        self.gridLayout.addWidget(self.below_thresh_txt, 4, 2, 1, 1)
        self.cosmic_btn = QtGui.QPushButton(self.widget)
        self.cosmic_btn.setObjectName(_fromUtf8("cosmic_btn"))
        self.gridLayout.addWidget(self.cosmic_btn, 5, 0, 1, 3)
        spacerItem1 = QtGui.QSpacerItem(228, 224, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.gridLayout.addItem(spacerItem1, 6, 0, 1, 3)
        self.back_btn = QtGui.QPushButton(self.widget)
        self.back_btn.setObjectName(_fromUtf8("back_btn"))
        self.gridLayout.addWidget(self.back_btn, 7, 0, 1, 2)
        self.forward_btn = QtGui.QPushButton(self.widget)
        self.forward_btn.setObjectName(_fromUtf8("forward_btn"))
        self.gridLayout.addWidget(self.forward_btn, 7, 2, 1, 1)
        self.horizontalLayout_2.addWidget(self.splitter)

        self.retranslateUi(xrs_mask_widget)
        QtCore.QMetaObject.connectSlotsByName(xrs_mask_widget)

    def retranslateUi(self, xrs_mask_widget):
        xrs_mask_widget.setWindowTitle(_translate("xrs_mask_widget", "Form", None))
        self.pos_lbl.setText(_translate("xrs_mask_widget", "TextLabel", None))
        self.circle_btn.setText(_translate("xrs_mask_widget", "Circle", None))
        self.ellipse_btn.setText(_translate("xrs_mask_widget", "Ellipse", None))
        self.rectangle_btn.setText(_translate("xrs_mask_widget", "Rectangle", None))
        self.polygon_btn.setText(_translate("xrs_mask_widget", "Polygon", None))
        self.point_btn.setText(_translate("xrs_mask_widget", "Point", None))
        self.above_thresh_btn.setText(_translate("xrs_mask_widget", "Above Thresh", None))
        self.below_thresh_btn.setText(_translate("xrs_mask_widget", "Below Thresh", None))
        self.cosmic_btn.setText(_translate("xrs_mask_widget", "Cosmic Removal", None))
        self.back_btn.setText(_translate("xrs_mask_widget", "Back", None))
        self.forward_btn.setText(_translate("xrs_mask_widget", "Forward", None))

from pyqtgraph import GraphicsLayoutWidget
