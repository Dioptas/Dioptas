# SPDX-License-Identifier: MIT
"""Run the startup smoke test with a verified non-UTF-8 file encoding.

Example (the locale must be installed first):
    LC_ALL=zh_CN.GBK PYTHONUTF8=0 PYTHONCOERCECLOCALE=0 \
        QT_QPA_PLATFORM=offscreen python -m scripts.check_locale_startup gbk

Qt resets Unix LC_CTYPE to UTF-8 during QApplication initialization. Restore
the requested locale afterward to exercise the same legacy file decoding as
Windows, where Python's ANSI code page is independent of Qt's locale setup.
No file-reading functions are mocked.
"""

import codecs
import locale
import os
import sys
from unittest.mock import patch


def main():
    expected_encoding = codecs.lookup(sys.argv[1]).name
    requested_locale = os.environ["LC_ALL"]

    def check_encoding():
        assert sys.flags.utf8_mode == 0, "UTF-8 mode would mask locale bugs"
        assert codecs.lookup(locale.getencoding()).name == expected_encoding
        with open(__file__) as stream:
            assert codecs.lookup(stream.encoding).name == expected_encoding
        print(f"Confirmed default file encoding: {expected_encoding}", flush=True)

    check_encoding()

    import dioptas

    class LocaleApplication(dioptas.QtWidgets.QApplication):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            locale.setlocale(locale.LC_CTYPE, requested_locale)
            check_encoding()

    with (
        patch.object(dioptas.QtWidgets, "QApplication", LocaleApplication),
        patch.object(sys, "argv", ["dioptas", "test"]),
        # Report failures to CI instead of opening the GUI error dialog.
        patch.object(dioptas, "excepthook", sys.__excepthook__),
        patch.object(sys, "excepthook", sys.__excepthook__),
    ):
        dioptas.main()


if __name__ == "__main__":
    main()
