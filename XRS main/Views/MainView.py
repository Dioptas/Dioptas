__author__ = 'Doomgoroth'

import sys

from PyQt4 import QtGui, QtCore
from UiFiles.Main import Ui_XRS_widget
import pyqtgraph as pg
import numpy as np


class MainView(QtGui.QWidget, Ui_XRS_widget):
    def __init__(self):
        super(MainView, self).__init__(None)
        self.setupUi(self)
        self.create_img_view()
        self.plot_curve = self.plot.plot()
        self.connect_mouse_movement()
        self.modify_mouse_behavior()

    def create_img_view(self):
        #create basic image view
        self.img_view_box = self.img_pg_layout.addViewBox(0, 0)
        self.img_view_box.setAspectLocked(True)

        #create the item handling the Data img
        self.data_img_item = pg.ImageItem()
        self.img_view_box.addItem(self.data_img_item)

        #creating the item handling the mask image
        self.mask_img_item = pg.ImageItem()
        self.img_view_box.addItem(self.mask_img_item)

        #creating plot item for possible overlays
        self.img_plot_item = pg.PlotCurveItem(pen='r')
        self.img_view_box.addItem(self.img_plot_item)

        #creating the histogram with colorbar-chooser
        self.img_histogram_LUT = pg.HistogramLUTItem(self.data_img_item)
        self.img_histogram_LUT.axis.hide()
        self.img_pg_layout.addItem(self.img_histogram_LUT, 0, 1)


    def connect_mouse_movement(self):
        def mouseMoved(pos):
            pos = self.data_img_item.mapFromScene(pos)
            try:
                if pos.x() > 0 and pos.y() > 0:
                    str = "x: %.1f y: %.1f I: %.0f" % (pos.x(), pos.y(),
                                                       self.img_data[np.round(pos.x()), np.round(pos.y())])
                else:
                    str = "x: %.1f y: %.1f" % (pos.x(), pos.y())
            except IndexError:
                str = "x: %.1f y: %.1f" % (pos.x(), pos.y())
            self.pos_lbl.setText(str)

        self.img_pg_layout.scene().sigMouseMoved.connect(mouseMoved)


    def modify_mouse_behavior(self):
        #different mouse handlers
        def myMouseClickEvent(ev):
            if ev.button() == QtCore.Qt.RightButton:
                view_range = np.array(self.img_view_box.viewRange()) * 2
                if (view_range[0][1] - view_range[0][0]) > self.img_data.shape[1] and \
                                (view_range[1][1] - view_range[1][0]) > self.img_data.shape[0]:
                    self.img_view_box.autoRange()
                else:
                    self.img_view_box.scaleBy(2)

        def myMouseDoubleClickEvent(ev):
            if ev.button() == QtCore.Qt.RightButton:
                self.img_view_box.autoRange()

        def myMouseDragEvent(ev, axis=None):
            #most of this code is copied behavior of left click mouse drag from the original code
            ev.accept()
            pos = ev.pos()
            lastPos = ev.lastPos()
            dif = pos - lastPos
            dif *= -1
            ## Ignore axes if mouse is disabled
            mouseEnabled = np.array(self.img_view_box.state['mouseEnabled'], dtype=np.float)
            mask = mouseEnabled.copy()
            if axis is not None:
                mask[1 - axis] = 0.0

            if ev.button() == QtCore.Qt.RightButton:
                #determine the amount of translation
                tr = dif * mask
                tr = self.img_view_box.mapToView(tr) - self.img_view_box.mapToView(pg.Point(0, 0))
                x = tr.x()
                y = tr.y()

                #check if already at border of image:
                view_range = self.img_view_box.viewRange()

                #if ((view_range[0][0] >= 0 and x <= 0) and \
                #    (view_range[0][1] <= self.img_data.shape[1] and x>= 0)) and \
                #        ((view_range[1][0] >= 0 and y <= 0) and \
                #        (view_range[1][1] <= self.img_data.shape[0] and y> 0)):
                #    self.img_view_box.translateBy(x=x, y=y)
                #elif (view_range[0][0] >= 0 and x < 0) or \
                #        (view_range[0][1] <= self.img_data.shape[1] and x > 0):
                #    self.img_view_box.translateBy(x=x)
                #elif (view_range[1][0] >= 0 and y < 0) or \
                #        (view_range[1][1] <= self.img_data.shape[0] and y > 0):
                #    self.img_view_box.translateBy(y=y)
                #
                #alternative Version:
                if (((view_range[0][0] + x) > 0) and \
                            ((view_range[0][1] + x) < self.img_data.shape[1])) and \
                        (((view_range[1][0] + y) > 0) and \
                                 ((view_range[1][1] + y) < self.img_data.shape[0])):
                    print x + view_range[0][0]
                    self.img_view_box.translateBy(x=x, y=y)
                    print '1'
                elif (view_range[0][0] + x) > 0 and \
                                (view_range[0][1] + x) < self.img_data.shape[1]:
                    self.img_view_box.translateBy(x=x)
                elif (view_range[1][0] + y) > 0 and \
                                (view_range[1][1] + y) < self.img_data.shape[0]:
                    self.img_view_box.translateBy(y=y)

                self.img_view_box.sigRangeChangedManually.emit(self.img_view_box.state['mouseEnabled'])
            else:
                pg.ViewBox.mouseDragEvent(self.img_view_box, ev)

        def myWheelEvent(ev):
            if ev.delta() > 0:
                pg.ViewBox.wheelEvent(self.img_view_box, ev)
            else:
                view_range = np.array(self.img_view_box.viewRange())
                if (view_range[0][1] - view_range[0][0]) > self.img_data.shape[1] and \
                                (view_range[1][1] - view_range[1][0]) > self.img_data.shape[0]:
                    self.img_view_box.autoRange()
                else:
                    pg.ViewBox.wheelEvent(self.img_view_box, ev)

        self.img_view_box.setMouseMode(self.img_view_box.RectMode)
        self.img_view_box.mouseClickEvent = myMouseClickEvent
        self.img_view_box.mouseDragEvent = myMouseDragEvent
        self.img_view_box.mouseDoubleClickEvent = myMouseDoubleClickEvent
        self.img_view_box.wheelEvent = myWheelEvent

    def set_img_filename(self, filename):
        self.filename_lbl.setText(filename)

    def plot_image(self, img_data, autoRange=False):
        self.img_data = img_data
        self.data_img_item.setImage(img_data)
        if autoRange:
            self.img_histogram_LUT.setLevels(np.min(np.min(img_data)), np.max(np.max(img_data)))

    def plot_graph(self, x, y):
        self.plot_curve.setData(x, y)



