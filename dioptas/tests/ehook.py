# SPDX-License-Identifier: MIT
from io import StringIO
import sys
import traceback

from qtpy import QtWidgets


def excepthook(exc_type, exc_value, traceback_obj):
    """
    Global function to catch unhandled exceptions. This function will result in an error dialog which displays the
    error information.

    :param exc_type: exception type
    :param exc_value: exception value
    :param traceback_obj: traceback object
    :return:
    """

    separator = '-' * 80

    tb_info_file = StringIO()
    traceback.print_tb(traceback_obj, None, tb_info_file)
    tb_info_file.seek(0)
    tb_info = tb_info_file.read()
    errmsg = '%s: \n%s' % (str(exc_type), str(exc_value))
    sections = [separator, separator, errmsg, separator, tb_info]
    msg = '\n'.join(sections)
    print(msg)
    # raise Exception


def main():
    app = QtWidgets.QApplication([])
    sys.excepthook = excepthook
    from sys import platform as _platform
    from ..controller.MainController import MainController

    if _platform == "linux" or _platform == "linux2" or _platform == "win32" or _platform == 'cygwin':
        app.setStyle('plastique')

    controller = MainController()
    controller.show_window()
    app.exec_()
    del app
