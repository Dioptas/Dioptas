from qtpy import QtWidgets


class MapError(object):
    def __init__(self, msg):
        err_msg = QtWidgets.QMessageBox()
        err_msg.setIcon(eval(msg['icon']))
        err_msg.setText(msg['short_msg'])
        err_msg.setInformativeText(msg['informative_text'])
        err_msg.setWindowTitle(msg['window_title'])
        err_msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        err_msg.setDetailedText(msg['detailed_msg'])
        err_msg.exec_()

no_map_loaded = {
    'icon': 'QtWidgets.QMessageBox.Information',
    'detailed_msg': 'Please follow these steps first:\n1. Load a map\n2. Click "Update Map"',
    'short_msg': 'Map not fully loaded',
    'informative_text': 'See additional info...',
    'window_title': 'Error: No Map Shown',
}
