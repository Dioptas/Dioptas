# SPDX-License-Identifier: MIT
from __future__ import absolute_import

import sys
import os
import time

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO
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
    traceback.print_exception(exc_type, exc_value, traceback_obj)
    tb_info_file.seek(0)
    tb_info = tb_info_file.read()
    errmsg = '%s: \n%s' % (str(exc_type), str(exc_value))
    sections = [separator, errmsg, separator, tb_info]
    msg = '\n'.join(sections)

    print(msg)


def main():
    sys.excepthook = excepthook