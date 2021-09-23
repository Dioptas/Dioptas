# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import time
import traceback

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

from .widgets.UtilityWidgets import ErrorMessageBox
from . import __version__


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
    log_path = f"{os.path.expanduser('~')}/dioptas_error.log"
    notice = \
        """An unhandled exception occurred. Please report the bug under:\n """ \
        """\t%s\n""" \
        """or via email to:\n\t <%s>.\n\n""" \
        """Please make sure to report the steps to reproduce the error. Otherwise it will be hard to fix it. \n\n""" \
        """A log has been written to "%s".\n\nError information:\n""" % \
        ("https://github.com/Dioptas/Dioptas/issues",
         "clemens.prescher@gmail.com", log_path)
    version_info = '\n'.join((separator, "Dioptas Version: %s" % __version__))
    time_string = time.strftime("%Y-%m-%d, %H:%M:%S")
    tb_info_file = StringIO()
    traceback.print_tb(traceback_obj, None, tb_info_file)
    tb_info_file.seek(0)
    tb_info = tb_info_file.read()
    errmsg = '%s: \n%s' % (str(exc_type), str(exc_value))
    sections = [separator, time_string, separator, errmsg, separator, tb_info]
    msg = '\n'.join(sections)
    try:
        f = open(log_path, "a")
        f.write(msg)
        f.write(version_info)
        f.close()
    except IOError:
        pass
    errorbox = ErrorMessageBox()
    errorbox.setText(str(notice) + str(msg) + str(version_info))
    errorbox.exec_()
