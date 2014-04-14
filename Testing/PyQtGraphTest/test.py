__author__ = 'Doomgoroth'

import pyqtgraph as pg

pg.mkQApp()

win = pg.GraphicsLayoutWidget()
vb = win.addViewBox()
vb.setAspectLocked()
grad = pg.GradientEditorItem(orientation='right')
win.addItem(grad, 0, 1)
img = pg.ImageItem()
vb.addItem(img)
win.show()


def update():
    lut = grad.getLookupTable(512)
    img.setLookupTable(lut)


grad.sigGradientChanged.connect(update)

import numpy as np

img.setImage(np.random.normal(size=(100, 100)))