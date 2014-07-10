import sys

from PyQt4 import QtGui
import matplotlib as mpl

from UiFiles.XRS_Main import Ui_XRS_Main


mpl.rcParams['font.size'] = 10
mpl.rcParams['lines.linewidth'] = 0.5
mpl.rcParams['lines.color'] = 'g'
mpl.rcParams['text.color'] = 'white'
mpl.rc('axes', facecolor='#1E1E1E', edgecolor='white', lw=1, labelcolor='white')
mpl.rc('xtick', color='white')
mpl.rc('ytick', color='white')
mpl.rc('figure', facecolor='#1E1E1E', edgecolor='black')
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class XRS_MainView(QtGui.QWidget, Ui_XRS_Main):
    def __init__(self, parent=None):
        super(XRS_MainView, self).__init__(parent)
        self.setupUi(self)
        self.create_axes()

    def create_axes(self):
        self.image_axes = ImageAxes(self.image_frame)
        self.graph_axes = GraphAxes(self.graph_frame)

    def plot_image(self, img_data):
        self.image_axes.show_image(img_data)


class MplAxes(object):
    def __init__(self, parent):
        self._parent = parent
        self._parent.resizeEvent = self.resize_graph
        self.create_axes()
        self.redraw_figure()

    def create_axes(self):
        self.figure = Figure(None, dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(self._parent)

        axes_layout = QtGui.QVBoxLayout(self._parent)
        axes_layout.setContentsMargins(0, 0, 0, 0)
        axes_layout.setSpacing(0)
        axes_layout.setMargin(0)
        axes_layout.addWidget(self.canvas)
        self.canvas.setSizePolicy(QtGui.QSizePolicy.Expanding,
                                  QtGui.QSizePolicy.Expanding)
        self.canvas.updateGeometry()
        self.axes = self.figure.add_subplot(111)

    def resize_graph(self, event):
        new_size = event.size()
        self.figure.set_size_inches([new_size.width() / 100.0, new_size.height() / 100.0])
        self.redraw_figure()

    def redraw_figure(self):
        self.figure.tight_layout(None, 0.8, None, None)
        self.canvas.draw()


class ImageAxes(MplAxes):
    def __init__(self, parent):
        super(ImageAxes, self).__init__(parent)
        self.axes.yaxis.set_visible(False)
        self.axes.xaxis.set_visible(False)

    def show_image(self, img_data):
        self.axes.cla()
        self.img_data = img_data
        self.image = self.axes.imshow(self.img_data, aspect='auto', cmap='hot')
        self.axes.set_ylim([0, len(self.img_data) - 1])
        self.axes.set_xlim([0, len(self.img_data[0]) - 1])
        self.axes.invert_yaxis()
        self.redraw_figure()


class GraphAxes(MplAxes):
    def __init__(self, parent):
        MplAxes.__init__(self, parent)

    def plot_graph(self, spectrum):
        self.axes.cla()
        self.spectrum = spectrum
        self.graph = self.axes.plot(spectrum.x, spectrum.y)
        self.redraw_figure()


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    view = XRS_MainView()
    view.show()
    app.exec_()