# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Main.ui'
#
# Created: Wed May 21 10:47:00 2014
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


class Ui_mainView(object):
    def setupUi(self, mainView):
        mainView.setObjectName(_fromUtf8("mainView"))
        mainView.resize(1063, 669)
        self.gridLayout = QtGui.QGridLayout(mainView)
        self.gridLayout.setMargin(5)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.tabWidget = QtGui.QTabWidget(mainView)
        self.tabWidget.setTabPosition(QtGui.QTabWidget.West)
        self.tabWidget.setTabShape(QtGui.QTabWidget.Rounded)
        self.tabWidget.setElideMode(QtCore.Qt.ElideLeft)
        self.tabWidget.setObjectName(_fromUtf8("tabWidget"))
        self.calibration_tab = QtGui.QWidget()
        self.calibration_tab.setObjectName(_fromUtf8("calibration_tab"))
        self.tabWidget.addTab(self.calibration_tab, _fromUtf8(""))
        self.mask_tab = QtGui.QWidget()
        self.mask_tab.setObjectName(_fromUtf8("mask_tab"))
        self.tabWidget.addTab(self.mask_tab, _fromUtf8(""))
        self.integration_tab = QtGui.QWidget()
        self.integration_tab.setObjectName(_fromUtf8("integration_tab"))
        self.tabWidget.addTab(self.integration_tab, _fromUtf8(""))
        self.gridLayout.addWidget(self.tabWidget, 0, 0, 1, 1)

        self.retranslateUi(mainView)
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(mainView)

    def retranslateUi(self, mainView):
        mainView.setWindowTitle(_translate("mainView", "Form", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.calibration_tab),
                                  _translate("mainView", "Calibration", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.mask_tab), _translate("mainView", "Mask", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.integration_tab),
                                  _translate("mainView", "Integration", None))

