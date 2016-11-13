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

no_bg_image_selected = {
    'icon': 'QtWidgets.QMessageBox.Information',
    'detailed_msg': 'Please make sure to select an image when prompted to, and press "Open"',
    'short_msg': 'No background image selected',
    'informative_text': 'See additional info...',
    'window_title': 'Error: No background image selected',
}

map_positions_bad = {
    'icon': 'QtWidgets.QMessageBox.Information',
    'detailed_msg': 'Either not all map files ahve been loaded or, metadata does not contain map positions.\nPlease'
                    ' set up the map positions manually by clicking "Setup Map"',
    'short_msg': 'Map positions missing',
    'informative_text': 'See additional info...',
    'window_title': 'Warning: Map positions missing',
}
