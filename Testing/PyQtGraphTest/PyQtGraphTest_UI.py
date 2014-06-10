# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'PyQtGraphTest.ui'
#
# Created: Sat Apr  5 11:52:18 2014
# by: PySide UI code generator 4.10.4
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

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


class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName(_fromUtf8("Form"))
        Form.resize(648, 335)
        Form.setStyleSheet(_fromUtf8("#Form {\n"
                                     "    background-color: rgb(0,0,0)\n"
                                     "}\n"
                                     "\n"
                                     "QLabel{\n"
                                     "    color: white\n"
                                     "}"))
        self.verticalLayout = QtGui.QVBoxLayout(Form)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.pg_layout = GraphicsLayoutWidget(Form)
        self.pg_layout.setObjectName(_fromUtf8("pg_layout"))
        self.horizontalLayout.addWidget(self.pg_layout)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        self.bench_btn = QtGui.QPushButton(Form)
        self.bench_btn.setObjectName(_fromUtf8("bench_btn"))
        self.horizontalLayout_2.addWidget(self.bench_btn)
        self.pos_lbl = QtGui.QLabel(Form)
        self.pos_lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        self.pos_lbl.setObjectName(_fromUtf8("pos_lbl"))
        self.horizontalLayout_2.addWidget(self.pos_lbl)
        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(_translate("Form", "PyQtGraphTest", None))
        self.bench_btn.setText(_translate("Form", "PushButton", None))
        self.pos_lbl.setText(_translate("Form", "HUAHSUGAHUGAS", None))


from pyqtgraph import GraphicsLayoutWidget
