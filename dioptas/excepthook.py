# SPDX-License-Identifier: MIT

import logging
import traceback

from io import StringIO

from .widgets.UtilityWidgets import ErrorMessageBox
from . import __version__
from .log import get_recent_log

logger = logging.getLogger(__name__)


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
    notice = (
        "An unhandled exception occurred. Please report the bug under:\n"
        "\thttps://github.com/Dioptas/Dioptas/issues\n"
        "or via email to:\n"
        "\t<clemens.prescher@gmail.com>.\n\n"
        "Please include the information below when reporting.\n\n"
    )

    # --- Error details ---
    tb_info_file = StringIO()
    traceback.print_tb(traceback_obj, None, tb_info_file)
    tb_info_file.seek(0)
    tb_info = tb_info_file.read()
    errmsg = '%s: \n%s' % (str(exc_type), str(exc_value))

    sections = [
        "Dioptas Version: %s" % __version__,
        separator,
        "Error:",
        errmsg,
        separator,
        "Traceback:",
        tb_info,
    ]

    # --- Recent activity log (from in-memory ring buffer) ---
    recent = get_recent_log(50)
    if recent:
        sections.append(separator)
        sections.append("Recent activity log:")
        sections.extend(recent)

    msg = '\n'.join(sections)

    # Also log to the logging system
    logger.critical(
        "Unhandled exception (Dioptas %s)\n%s", __version__, errmsg,
        exc_info=(exc_type, exc_value, traceback_obj),
    )

    errorbox = ErrorMessageBox()
    errorbox.setText(str(notice) + str(msg))
    errorbox.exec_()
